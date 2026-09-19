# Sahayatri — project guide

A walkthrough of how the whole system works: the domain, the rules, the
algorithm, and where each rule lives in the code. The README covers setup and
commands; this covers *why the thing behaves the way it does*.

---

## 1. What the product is

A citizen sees a broken streetlight, opens the app, takes a photo, and submits.
The report is routed by GPS to the ward that actually owns that location. A
ward officer sees it, verifies it, works it, resolves it. The citizen gets
notified at every step.

Two things make it more than a form:

1. **Duplicates collapse.** When twelve people report the same pothole, the
   ward office should see *one* ticket with twelve reporters behind it — not
   twelve tickets. A classifier plus a geo/text/photo matcher proposes the
   merge; a human confirms it.
2. **Neighbours corroborate.** A second citizen standing near the same spot can
   confirm "yes, I see it too" instead of filing a second report. Three
   confirmations mark the ticket community-verified, which raises its priority.

---

## 2. Roles and who sees what

| Role | Created by | Sees |
|---|---|---|
| `citizen` | Self-registration, active immediately | Every ticket in their **municipality** |
| `authority` | Self-registration → **pending** until an admin approves | Their **ward** if they have one; the whole municipality if `ward_id` is NULL |
| `admin` | Seeded / promoted | Everything |

An authority account signs up with `account_status = pending` and cannot do
anything until an admin approves it at `/admin/approvals`. That approval is also
where the admin sets or corrects the officer's ward.

The single source of truth for visibility is `scope_filter` in
[backend/app/services/ticket_service.py](../backend/app/services/ticket_service.py) —
every ticket query starts from it:

```python
if role is ADMIN:      return []                                   # no filter
if role is AUTHORITY:  return [Ticket.ward_id == profile.ward_id]  # or municipality
else:                  return [Ticket.municipality_id == profile.municipality_id]
```

Write access is narrower than read access: `assert_can_access_ward(profile,
ward_id)` gates every mutation, so a ward-9 officer can read their ward and only
act on their ward.

> **Citizens are scoped to the municipality, not the ward, on purpose.** They
> need to find and corroborate a neighbour's report, and a pothole 30 m away can
> easily sit across a ward line.

### Seeing your own ward from somewhere else

People leave their ward all day — work, college, a trip — and still want to
follow what was reported at home. So `/nearby` has two tabs:

- **Around me** — GPS-driven, radius 1500 m, open tickets only. This is the
  corroboration surface: it exists so you can confirm what is physically in
  front of you.
- **My ward** — ignores GPS entirely. It calls
  `GET /api/tickets?ward_id=<your ward>` and lists everything your neighbours
  reported at home, wherever your phone happens to be. If your profile has no
  ward set it falls back to the whole municipality (the API scopes it anyway).

Your ward comes from what you picked at registration
([frontend/src/pages/Register.tsx](../frontend/src/pages/Register.tsx)), which is
separate from the ward a given *ticket* lands in — that one is decided by GPS at
submission time. A ticket therefore always displays its own `ward_number`,
because the two can legitimately differ.

---

## 3. How a report gets its priority

Priority is **derived, never chosen by the reporter**. A reporter's own sense of
urgency is not evidence; how many people independently reported the same thing
is. The formula lives in `compute_priority` in
[backend/app/services/ticket_service.py](../backend/app/services/ticket_service.py):

```
score  = category.base_severity                  # what kind of problem it is
score += min(0.30, 0.06 x child_count)           # other people reported the same thing
score += min(0.20, 0.05 x corroboration_count)   # neighbours confirmed it
score += 0.10  if community_verified             # 3 or more confirmations
score -= min(0.20, 0.07 x dispute_count)         # neighbours said it is not there
```

Then thresholds:

| Score | Priority |
|---|---|
| >= 1.00 | `critical` |
| >= 0.75 | `high` |
| >= 0.50 | `medium` |
| < 0.50 | `low` |

**Why each term is there**

- **`base_severity`** is the floor: a live power line starts at 0.80, a
  streetlight at 0.40. Category alone decides the baseline because some problems
  are dangerous even when only one person notices.
- **Fan-in with diminishing returns.** Each merged duplicate adds 0.06 but the
  whole term caps at 0.30. Twelve reports of a pothole should outrank one; a
  hundred should not outrank a gas leak. The cap is what keeps a popular
  complaint from drowning a rare dangerous one.
- **Corroborations are worth less than duplicates** (0.05, capped at 0.20)
  because confirming is cheaper than reporting.
- **Disputes subtract.** They are the only downward pressure, and they are why a
  citizen can say "no, this isn't there" as well as yes.

Age is handled separately, by the ladder below, rather than as another term in
the score — a named step an officer can predict and a citizen can be told about
("nobody touched it for a week, so it moved up") is worth more than a soft nudge
buried in a number.

### The age ladder

An open ticket climbs on its own, so a low-severity complaint cannot be ignored
indefinitely:

| From | After | To |
|---|---|---|
| `low` | 7 days open | `medium` |
| `medium` | 3 further days (day 10) | `high` |
| `medium` from birth | 3 days open | `high` |
| `high` | — | stays `high` |

The ladder starts from whatever the score says, so a mid-severity problem left
alone reaches `high` in 3 days while a minor one takes 10. **Escalation stops at
high**: critical means dangerous, and age is not danger. Only a human promotes
to critical.

Resolved, rejected and merged tickets never escalate. Both intervals are
configurable — `escalate_low_to_medium_days` and `escalate_medium_to_high_days`
in [core/config.py](../backend/app/core/config.py).

There is no scheduler. `sweep_escalations` runs whenever a ticket list is loaded
(throttled to once every five minutes per process), which means a stale ticket
has already moved by the time anyone opens a queue to look at it. An admin can
force it immediately with `POST /api/admin/escalations/run`. A cron or a worker
would be the right answer in production; on one box, recomputing on read is
correct the moment anyone looks and costs nothing when nobody does.

### The manual override

An authority or admin can overrule all of it:
`PATCH /api/tickets/{id}/priority` with `{"priority": "critical", "note": "..."}`.
Ward isolation still applies — an officer can re-prioritise their own ward's
tickets, an admin anyone's, and a child ticket redirects you to its parent.

Setting priority by hand **locks** the ticket: `priority_locked` goes true and
neither the score nor the ladder writes to it again. Someone standing in front of
the problem knows things the formula does not, and having their judgement
silently overwritten by the next corroboration is worse than having no override
at all.

Sending `{"priority": null}` clears the lock and recomputes. An override with no
exit is a trap, so the way back always exists. Both actions are written to
`ticket_status_history`, so the timeline shows who changed it and why.

To demo the ladder without waiting a week:

```bash
python -m scripts.age_ticket KMC-05-000006 8     # -> medium
python -m scripts.age_ticket KMC-05-000006 11    # -> high
python -m scripts.age_ticket KMC-05-000006 --restore
```

**Seeded severities**

| Category | base | match radius | dedupe window |
|---|---|---|---|
| Waterlogging / flooding | 0.85 | 250 m | 14 d |
| Electricity / power line | 0.80 | 100 m | 30 d |
| Drainage & sewage | 0.75 | 120 m | 30 d |
| Water supply | 0.70 | 150 m | 30 d |
| Pothole / road damage | 0.60 | 60 m | 45 d |
| Illegal construction | 0.60 | 80 m | 120 d |
| Pollution | 0.55 | 300 m | 21 d |
| Garbage & waste | 0.50 | 80 m | 21 d |
| Public sanitation | 0.50 | 60 m | 30 d |
| Stray animals | 0.45 | 200 m | 14 d |
| Street light | 0.40 | 40 m | 60 d |
| Other | 0.40 | 100 m | 30 d |

Priority is recomputed on every event that changes an input: creation, merge,
corroboration, dispute — plus the escalation sweep described above.

**Radius and window are per-category, and that matters.** Two potholes 80 m
apart are two potholes; waterlogging reported 80 m apart is one flood. Garbage
recurs weekly so its window is short; illegal construction persists for months
so its window is long.

---

## 4. The ticket lifecycle

```
                 ┌──────────┐
                 │ reported │◄──────────────┐
                 └────┬─────┘               │
        ┌─────────────┼─────────────┐       │
        ▼             ▼             ▼       │
  ┌──────────┐  ┌─────────────┐  ┌──────────┴─┐
  │ verified │─►│ in_progress │  │  rejected  │
  └────┬─────┘  └──────┬──────┘  └────────────┘
       │               │
       └──────►┌───────▼──┐
               │ resolved │──► (can reopen to in_progress)
               └──────────┘

  merged — a child; it has no transitions of its own and follows its parent
```

Enforced by `ALLOWED_TRANSITIONS` in `ticket_service.py`. Two rules worth
knowing:

- **A child ticket cannot be updated directly.** Try it and the API returns 409
  telling you to update the parent. Otherwise a merged duplicate could show
  "resolved" while its parent is still open.
- **Resolving a parent cascades.** Every child is resolved with it, and *every*
  reporter — parent and children — gets a notification. That is the payoff of
  merging: one action closes twelve complaints and twelve people hear about it.

Every transition is appended to `ticket_status_history`, which is what the
timeline on the ticket detail page renders.

---

## 5. The duplicate matcher

This is the distinguishing feature. The README's *The duplicate matcher*
section has the measured numbers; this is the shape of it.

### Pipeline

```
new report
   │
   ├─ 1. classify       TF-IDF(char 3-5) -> SVD(256) -> LogisticRegression
   │                    -> predicted_category_key + a 256-d embedding
   │
   ├─ 2. fetch candidates
   │       same municipality
   │       status in (reported, verified, in_progress)
   │       created within category.dedupe_window_days
   │       inside a lat/lon bounding box   <- cheap SQL prefilter
   │
   ├─ 3. score each candidate
   │       distance  = haversine(new, candidate)
   │       IF distance > category.match_radius_m: DROP IT ENTIRELY
   │       category  = 1.0 if same predicted category else 0.0
   │       text      = cosine(embeddings)
   │       image     = pHash similarity, if both sides have photos
   │       geo       = 1 - distance / radius
   │
   ├─ 4. weighted blend, renormalised over the signals that exist
   │       category .35   text .30   image .20   geo .15
   │
   └─ 5. keep the top 5 scoring >= 0.45 -> rows in duplicate_candidates (pending)
```

### The two rules that make it work

**Distance is a gate, not a weight.** Originally distance was just another
weighted term, and two potholes 3 km apart scored 0.59 — because 0.35 (same
category) + 0.30 (similar text) clears any sane threshold on its own. The
false-suggest rate was 66%. Making the radius a hard drop took recall from 51%
to 70% and false suggestions from 66% to 0.6%.

**Weights renormalise over present signals.** When neither report has a photo,
the 0.20 image weight is dead mass that every pair loses, so genuine duplicates
scored below threshold — 44 cross-language duplicates were being missed. Now the
denominator only counts the signals actually available:

```python
active = category + text + geo
total  = w_cat*cat + w_text*text + w_geo*geo
if both sides have photos:
    active += w_image;  total += w_image * image
score = total / active
```

Final measured behaviour on the generated evaluation set: **100% recall, 2.8%
false-suggest.**

### Nothing merges itself

The matcher only ever writes rows to `duplicate_candidates` with status
`pending`. `parent_id` is set in exactly one function — `merge_tickets` — which
is reachable only from `POST /api/tickets/{id}/merge`, behind
`require_authority`. An officer works the queue at `/authority/duplicates`, sees
the two tickets side by side with a plain-language explanation ("48m apart, same
category, descriptions 82% similar"), and confirms or rejects.
`POST /api/tickets/{id}/split` undoes it.

This was a product decision, not a technical limitation: a wrong auto-merge
silently buries a citizen's complaint, and they have no way to tell that it
happened.

### Honest limitations

- The classifier's ~100% accuracy on held-out data is a property of the
  **generated** dataset, not evidence it will hold on real Nepali complaints.
  There was no real training data; the generator is in `app/ml/dataset.py`.
- The char-n-gram encoder scores **zero** text similarity between a Nepali
  description and an English one describing the same thing. Cross-language
  duplicates are caught by category + geo alone. The fix is a multilingual
  sentence transformer; `TextEncoder` in `app/ml/encoder.py` is an abstract base
  class specifically so it can be swapped without touching the matcher.
- pHash recognises **the same photograph re-sent**, not two photos of the same
  object from different angles. Measured: same scene with the camera moved = 26
  bits apart; a completely different scene = 28. That is noise, not signal. The
  image term is real only for a re-uploaded or forwarded image.

---

## 6. Corroboration

`POST /api/tickets/{id}/corroborate` with `{is_confirmed, latitude, longitude}`.
Three guards, all in `ticket_service.corroborate`:

1. You cannot corroborate your own report.
2. One vote per person per ticket.
3. You must be within `max(category.match_radius_m * 2, 150)` metres of the
   ticket. Confirming from across town is not a confirmation.

At `corroboration_threshold` (3) confirmations the ticket flips
`community_verified = true`, which is worth +0.10 priority and shows as a badge.
Disputes subtract instead.

---

## 6a. Ticket comments

Each ticket has a discussion thread: `GET/POST /api/tickets/{id}/comments`,
`DELETE /api/tickets/{id}/comments/{comment_id}`.

**Visibility mirrors the ticket itself.** Whoever can already view the ticket
-- every citizen in its municipality, its ward's authority, any admin -- can
read and post. That is deliberate: "when will this be fixed?" asked where a
neighbour and the ward office both see it is the point of a public thread,
not a private support ticket that puts no pressure on anyone.

`can_view_ticket` in `ticket_service.py` is the single-row twin of
`scope_filter` -- the same rule, checked against one row instead of built into
a WHERE clause. The single-ticket `GET /api/tickets/{id}` uses it too, which
closed a real gap: that endpoint previously fetched by ID with no scope check
at all, so any authenticated citizen or authority could read any ticket by
guessing or leaking a UUID, regardless of municipality or ward. Comments
inherit whatever that endpoint enforces, so fixing it was part of building
this feature correctly, not a separate detour.

A comment on a child (merged) ticket is rejected with a 409 pointing at the
parent, same as a direct status update -- one discussion per real incident,
not one per duplicate report of it.

Posting notifies the people actually responsible for the ticket -- its
reporter and its assigned authority, whichever one is not the comment's
author -- not everyone in the municipality who happens to be able to see the
thread. The thread is public; the notification is not spam.

Deleting a comment is allowed for its own author, or for the ward authority
moderating it (ward isolation still applies via `assert_can_access_ward`).

## 6b. Public transparency page

`GET /api/public/stats` -- no authentication, no per-ticket data. It is
mounted in `api/reference.py`, which is already the unauthenticated router
(the civic service directory lives there for the same reason: some things
have to be reachable before anyone logs in).

**The boundary that makes it safe to leave unauthenticated:** the response
carries counts and medians only -- total/open/resolved tickets, resolved this
month, a municipality-wide median time-to-resolve, and a breakdown by category
and by ward. Nothing in it is a title, a description, a photo, or an exact
coordinate. An anonymous visitor can see that ward 5 has a backlog without
reading what any one citizen wrote or where they live. There is no map with
pins -- a ward-level bar comparison instead, which needed no new mapping
library and exposes nothing more precise than "this many reports in this
ward."

Every count filters `parent_id IS NULL`: a merged duplicate's resolution time
belongs to its parent, so counting both would double the total and drag the
median toward whichever category attracts the most duplicates.

The page covers one municipality (`public_stats_municipality_code` in
`config.py`, default `KMC`) rather than every seeded municipality --
a picker across all of them is a real feature, this is the demo shape. It
takes an optional `?municipality_code=` to preview others without touching
config.

Linked from the login screen and reachable directly at `/transparency` --
the one page in the frontend that is intentionally not behind `RequireAuth`.

## 7. Emergency SOS and alerts

- **SOS** (`POST /api/sos`) is one button. It takes type, GPS and an optional
  note and lands in the ward's queue at `/authority/emergencies` with statuses
  `open -> acknowledged -> dispatched -> closed`.
- **Alerts** (`POST /api/alerts`) are published by an authority and targeted
  either by **ward** (a list of ward ids) or by **radius** (a centre point plus
  metres). A schema validator rejects a ward-targeted alert with no wards, so a
  misconfigured alert cannot silently reach nobody.
- **Civic services** (`GET /api/services`) is the directory: hospitals,
  ambulances, police, fire, ward offices, shelters, pharmacies — with phone
  numbers. It is the one data endpoint cached for offline use (see §10).

---

## 8. Layout of the code

```
backend/app/
  core/      config, security (RBAC), geo (haversine + bbox), supabase clients
  models/    SQLAlchemy: geography, category, profile, ticket, emergency, notification
  schema/    Pydantic request/response models  <- the API contract IS the enforcement
  services/  ticket_service, auth_service, storage_service, stats_service  <- business rules
  ml/        encoder, classifier, matcher, imaging, dataset, templates, registry
  api/       thin routers; validate, delegate to services, map to schema
  seeds/     geography, categories, civic services

backend/scripts/
  seed.py         load reference data
  train_model.py  generate the dataset, train, save to ml/artifacts
  try_matcher.py  score two ad-hoc reports against each other
  demo_flow.py    drive the entire loop end to end against a running API
  demo_data.py    populate a demo municipality
  age_ticket.py   backdate a ticket to demonstrate age escalation

frontend/src/
  lib/        api client, auth, i18n, prefs (a11y), geo, types
  components/ ui primitives, Layout, TicketCard, PwaPrompts
  pages/      citizen/*, authority/*, admin/*, plus Login/Register/TicketDetail/Transparency
```

**Where to change things**

| To change… | Edit |
|---|---|
| Who can see which tickets | `ticket_service.scope_filter` |
| Who can see/comment on one ticket | `ticket_service.can_view_ticket` |
| Who can act on a ticket | `core/security.assert_can_access_ward` |
| How priority is computed | `ticket_service.compute_priority` |
| The age ladder | `ticket_service.escalate_for_age` + `escalate_*_days` in `config.py` |
| Whether a human override sticks | `ticket_service.apply_priority` (the `priority_locked` check) |
| Which transitions are legal | `ticket_service.ALLOWED_TRANSITIONS` |
| Dedup weights / threshold | `core/config.py` (`dedupe_*` settings) |
| Per-category radius / window | `seeds/categories.py`, then reseed |
| Any user-facing string | `frontend/src/lib/i18n.tsx` (en + ne side by side) |

---

## 9. Security model

These are load-bearing. Breaking one of them silently exposes data.

- **The service-role key never reaches the browser.** It is not in any `VITE_`
  variable. `frontend/src/lib/supabase.ts` was deleted on purpose — do not
  reintroduce a browser-side Supabase client.
- **Every table has RLS enabled with no policies.** A table with RLS *disabled*
  is readable by the anon key through PostgREST; the FastAPI service role
  bypasses RLS, so the app still works while the browser gets nothing.
- **The `ticket-photos` bucket is private.** Photos are served only as
  short-lived signed URLs minted per request.
- **Never sign a user in on the shared cached Supabase client.**
  `sign_in_with_password` stores the session *on the client object*, which
  downgrades the whole process to that one citizen — this caused a real 403 on
  storage uploads. `get_supabase()` is the service-role singleton;
  `new_auth_client()` is a throwaway for anything that signs someone in.
- **`ProfileUpdateRequest` deliberately omits `role`, `account_status` and
  `municipality_id`.** The schema is the enforcement: a field that does not
  exist cannot be smuggled in. Role changes go through the admin router.
- **The frontend's `RequireAuth` is convenience, not security.** Anything in a
  browser can be edited; the API re-checks every rule.

---

## 10. The PWA

Installable, works offline, and deliberately picky about what it caches.

| Request | Strategy | Why |
|---|---|---|
| App shell (JS/CSS/HTML/icons) | Precache | It must open with no network |
| `GET /api/services` | StaleWhileRevalidate | Emergency numbers must survive a dead network — that is exactly when someone needs a hospital |
| `GET /api/categories`, `/api/municipalities` | StaleWhileRevalidate | Reference data; the report form is unusable without it |
| **Everything else under `/api`** | **NetworkOnly** | Tickets, notifications, SOS, alerts, duplicate suggestions |

Caching authenticated data would let the app serve one user's tickets to another
from disk, or show a resolved emergency as still open. An app that admits it is
offline is better than one that lies confidently.

Updates use `registerType: 'prompt'`, not `autoUpdate` — code must not swap out
from under someone halfway through filing a report. When offline, the offline
banner takes the slot over the install prompt, because it changes what is
trustworthy on screen.

---

## 11. Accessibility

Built in, not bolted on:

- **Nepali and English** throughout, one flat key table with both strings side
  by side in `i18n.tsx`. Seed data carries `_en` and `_ne` columns, so category
  and service names translate too.
- **Large text** and **high contrast** toggles. `index.css` is token-based;
  `[data-large-text]` and `[data-high-contrast]` redefine the tokens, so every
  component follows without per-component work.
- **Text-to-speech** via the Web Speech API on alerts and ticket descriptions,
  for anyone who cannot read the screen.
- Touch targets at least 44 px, `role="status"` on live banners, `aria-selected`
  on the scope tabs.

---

## 12. Running it

```bash
# backend
cd backend
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload     # :8000
../.venv/Scripts/python.exe -m scripts.seed                      # reference data
../.venv/Scripts/python.exe -m scripts.train_model               # classifier
../.venv/Scripts/python.exe -m pytest                            # 62 tests

# frontend
cd frontend
npm run dev                          # :5173, proxies /api
npm run build && npm run preview     # production PWA with a real service worker
```

If port 8000 is held by a stale uvicorn (Windows lets two processes bind it and
the old one can win — it shows up as 404s on endpoints you just added), set
`VITE_API_PROXY_TARGET=http://localhost:8001` in `frontend/.env` and run the
backend on 8001.

---

## 13. A five-minute demo script

1. **Citizen A** logs in, reports a pothole with a photo and GPS. Show the
   generated public code and the ticket landing in a specific ward.
2. **Citizen B** reports the same pothole ~40 m away, in Nepali. The report goes
   through, and nothing visibly merges — that is the point.
3. **Ward officer** opens `/authority/duplicates`. The suggestion is waiting with
   its explanation: "41m apart, same category, descriptions 78% similar."
   Confirm the merge. B's ticket becomes a child; A's priority rises.
4. **Citizen C**, standing near the spot, opens `/nearby` → *Around me* and taps
   "Yes, I can see it". Third confirmation → community-verified badge →
   priority rises again.
5. **Citizen A** opens the ticket and posts "When will this be fixed?" in the
   discussion thread. **Officer** replies "Scheduled for Thursday" from the
   same ticket — point out the thread is public, so citizen C sees the reply
   too, not just A.
6. **Officer** overrules the computed priority — sets it to Critical with a
   reason. The badge locks; point out that the next corroboration will not undo
   it. Then clear it back to automatic.
7. Run `python -m scripts.age_ticket <code> 11` in a terminal and reload: the
   ticket has climbed to High on its own, with "escalated after 11 days
   unresolved" in its timeline.
8. **Officer** moves the parent to In Progress, then Resolved. Both A and B are
   notified; the child resolves with the parent.
9. Open `/transparency` with no login — the same municipality's median
   time-to-resolve and per-ward backlog, updated by what you just did, and
   nothing in it traces back to A, B or C by name or location.
10. Switch to **My ward** on `/nearby` to show that a citizen away from home
    still follows their own ward.
11. Toggle **नेपाली**, **large text**, **high contrast**, and play a ticket aloud.
12. Go offline in DevTools: the shell still loads, Services still lists hospital
    numbers, and the offline banner appears.

`backend/scripts/demo_flow.py` drives steps 1–4 against a running API if you
would rather have it seeded before you present.
