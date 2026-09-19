# Sahayatri — civic issue reporting for Nepal

Citizens report local problems with a photo and GPS. Reports of the same
incident are detected and folded under one ticket, so twelve people reporting
one pothole produce one ticket with eleven children rather than twelve tickets
nobody links up. Authorities work a ward-scoped queue; citizens standing near a
report can corroborate that it is real.

- `frontend/` — React 19, TypeScript, Vite, Tailwind 4
- `backend/` — FastAPI, SQLAlchemy, Alembic, scikit-learn
- Supabase provides Postgres, Auth and Storage

**[docs/GUIDE.md](docs/GUIDE.md)** is the full walkthrough: roles and scoping,
how priority is computed, the ticket lifecycle, the matcher pipeline, the
security model, and a demo script.

## Quick start

```powershell
# One-time Supabase setup: see "Supabase checklist" below.

cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python -m alembic upgrade head    # schema + pgvector + RLS lockdown
python -m scripts.seed            # categories, wards, services, demo accounts
python -m scripts.train_model     # generate data, train, evaluate, save
python -m scripts.demo_data       # tickets, duplicates, alerts, an open SOS

uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. API docs at <http://localhost:8000/docs>.

On Windows, set `PYTHONIOENCODING=utf-8` before any script that prints Nepali,
or the console dies on cp1252.

### Demo accounts

Password for all of them: `Sahayatri@2025`

| Account | Role | Scope |
| --- | --- | --- |
| `admin@sahayatri.np` | admin | everything |
| `kmc.city@sahayatri.np` | authority | all KMC wards |
| `kmc.ward5@sahayatri.np` | authority | KMC ward 5 only — **has the demo content** |
| `kmc.ward10@sahayatri.np` | authority | KMC ward 10 — proves ward isolation |
| `pending.authority@sahayatri.np` | authority | awaiting approval, cannot sign in |
| `sita@example.com` | citizen | KMC ward 5, Nepali UI |
| `ram@example.com` | citizen | KMC ward 5 |

## Supabase checklist

Everything below is done once, in the Supabase dashboard.

1. **Connection string** → Project Settings → Database → Connection string
   (URI). Put it in `backend/.env` as `DATABASE_URL`.
2. **API keys** → Project Settings → API. `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` go in `backend/.env`. The anon key goes in
   `frontend/.env` — never the service-role key.
3. **Storage bucket** → Storage → New bucket, named `ticket-photos`,
   **not public**. Photos are served through short-lived signed URLs. Without
   this bucket, submitting a report with a photo returns a clear 503; reports
   without photos still work.
4. **Extensions** — the migration runs `CREATE EXTENSION vector` itself, so
   there is nothing to click. PostGIS is deliberately not used.
5. **Email confirmation** — not required. Accounts are created through the
   admin API with `email_confirm: true`, so demo sign-ups work with no inbox.

## Installable app (PWA)

The frontend is an installable Progressive Web App, not a wrapper around a
native build. On Android/Chrome an install banner appears in the app; on iOS
use Share -> Add to Home Screen. Once installed it launches standalone with no
browser chrome, and long-pressing the icon offers **Report**, **SOS** and
**Services** shortcuts.

```powershell
cd frontend
npm run build      # emits dist/sw.js + dist/manifest.webmanifest
npm run preview    # serves the production build on 4173, /api proxied
```

The service worker is only fully meaningful in a production build, so test
install and offline behaviour through `npm run preview`, not `npm run dev`
(dev mode does register a worker, but the caching differs).

### What is cached, and what deliberately is not

| Request | Strategy | Why |
| --- | --- | --- |
| App shell (JS/CSS/HTML/icons) | Precache | Opens instantly, works offline |
| `/api/services` | StaleWhileRevalidate | **Emergency numbers must survive a dead network** — that is exactly when someone needs a hospital number |
| `/api/categories`, `/api/municipalities` | StaleWhileRevalidate | Near-static; the report form is unusable without them |
| Everything else under `/api` | **NetworkOnly** | Tickets, notifications, SOS and alerts are authenticated and per-user. Caching them risks serving one user another user's data from disk, or showing a resolved ticket as still open |

That last row is the important one. It is tempting to cache everything for a
better offline demo, but a civic app that shows a stale "still open" status on
a resolved emergency is worse than one that admits it is offline.

The app shows an offline banner when the network drops, and a "new version
ready" prompt rather than silently swapping code under the user.

### Icons

`frontend/public/*.png` are generated, not designed:

```powershell
cd frontend
python scripts/make-icons.py
```

Replace them with real artwork when there is any. The maskable variant keeps
its glyph inside the middle 80% so Android launchers can crop it to any shape.

## Architecture notes

**Supabase is used for auth and storage only.** All application tables are
reached through SQLAlchemy with Alembic migrations, using the service-role key.
That key bypasses Row Level Security, so every access rule lives in
`app/core/security.py` and `app/services/ticket_service.py`.

**Every table has RLS enabled with no policies.** This is not optional. A table
with RLS *disabled* is readable by the browser anon key through PostgREST, and
the frontend ships that key. With RLS on and no policies, PostgREST denies
everything and only the service-role backend can read. The lockdown is in the
first migration.

**PostGIS is deliberately not used.** Candidates are narrowed by ward and an
indexed bounding box, then exact distances are computed in Python
(`app/core/geo.py`). At this scale a spatial index buys nothing and costs
GeoAlchemy2 plus geometry types in every migration. pgvector *is* used, for the
256-dimension description embedding.

**Priority is computed, and a human can overrule it.** Category severity plus
how many people reported it plus how long it has gone unresolved. An open
ticket climbs the ladder on its own — low to medium after 7 days, medium to
high after 3 more — so a minor complaint cannot be ignored forever. An officer
or admin can set priority by hand, which locks the ticket so neither scoring
nor escalation overwrites their judgement; sending `priority: null` hands it
back. See [docs/GUIDE.md](docs/GUIDE.md) §3.

**Notifications are polled, not pushed.** Supabase Realtime authorises through
RLS, and the tables are deliberately locked. Opening policies just for Realtime
would mean re-implementing the ward-scoping rules in SQL alongside the Python
ones — two copies of the authorisation logic, which is how they drift apart.
The client polls a scoped endpoint every 30 seconds (15 for the SOS queue).

**A ticket's discussion thread is as visible as the ticket itself.** Whoever
can already view a ticket — every citizen in its municipality, its ward's
authority, any admin — can read and post on it. `can_view_ticket` is the
single-row twin of `scope_filter`, checked by both the single-ticket read and
the comment endpoints, which closed a real gap along the way: `GET
/tickets/{id}` previously had no scope check at all. See
[docs/GUIDE.md](docs/GUIDE.md) §6a.

**The public transparency page publishes numbers, never tickets.** No login,
and no title, description, photo or coordinate ever leaves the aggregate —
only counts and medians, by category and by ward. See
[docs/GUIDE.md](docs/GUIDE.md) §6b.

## The duplicate matcher

Four signals blend into one score, weighted by `DEDUPE_WEIGHT_*` in `.env`:

| Signal | Weight | Source |
| --- | --- | --- |
| Category match | 0.35 | logistic regression over the text encoder |
| Description similarity | 0.30 | cosine over char-ngram TF-IDF → SVD(256) |
| Photo similarity | 0.20 | perceptual hash, Hamming distance (see below) |
| Geographic proximity | 0.15 | Haversine, scaled by the category radius |

Two rules matter more than the weights:

**Distance is a gate, not a weight.** Beyond the category's `match_radius_m` a
candidate is discarded outright. Everyone describes a pothole the same way, so
without this, text similarity alone clears any threshold and the matcher
suggests merging every pothole in the municipality. Adding the gate took the
false-suggestion rate from 66% to 0.6%.

**Weights renormalise over the signals present.** Most reports have no photo;
leaving the image weight in the denominator caps a photo-less pair at 0.80 and
makes genuine cross-language duplicates unreachable.

**Nothing is merged automatically.** The matcher only writes rows to
`duplicate_candidates`. An authority merges during the `reported → verified`
step and can always split a child back out.

### What the photo signal really does

Measured by `python -m scripts.test_photos`:

| Case | Hamming distance | Similarity |
| --- | --- | --- |
| Same photo, re-sent | 0 | 1.00 |
| Recompressed to q=45 | 0 | 1.00 |
| Resized to 400×300 | 0 | 1.00 |
| Same scene, camera moved 6px | 26 | 0.00 |
| A completely different scene | 28 | 0.00 |

So the hash recognises **the same photograph** again — re-sent, recompressed,
resized — and does **not** recognise two photographs taken independently of the
same object: "camera moved" scores no better than "different scene".

That still catches a real pattern, one photo circulating in a ward WhatsApp
group and attached by several people. It does not catch two neighbours each
photographing the same pothole. Recognising the object rather than the file
needs an image embedding (CLIP, ~1.5GB of torch), a deliberate non-goal. This
is why the weight is only 0.20 and why the blend renormalises when photos are
absent — the signal must never be load-bearing.

Measured on held-out synthetic clusters: **100% duplicate recall, 2.8%
false-suggest rate.**

```powershell
python -m scripts.try_matcher   # worked example with score breakdown
python -m scripts.demo_flow     # full loop: report -> match -> merge -> resolve
```

### On the accuracy numbers

The model is trained on data this repository generates (`app/ml/dataset.py`);
no corpus of Nepali civic complaints exists to train on. The reported accuracy
describes the generator, not Kathmandu. It demonstrates that the pipeline runs
end to end — quote it with that caveat attached.

The character-n-gram encoder scores **zero** text similarity between a Nepali
and an English description of the same issue: the two share no character
n-grams. Such pairs are still matched, on category and distance. Closing that
gap means swapping `TextEncoder` in `app/ml/encoder.py` for a multilingual
sentence-transformer — the interface exists for exactly that, and nothing
downstream changes. It costs ~2.5GB of torch, which is why it is not the
default.

## Feature map

| # | Feature | Where |
| --- | --- | --- |
| 1 | Auth & RBAC | `core/security.py`, `api/auth.py`, `api/admin.py` |
| 2 | Reporting & tracking | `services/ticket_service.py`, `api/tickets.py` |
| 3 | Civic service directory | `api/reference.py`, `seeds/services.py` |
| 4 | SOS & public alerts | `api/emergency.py` |
| 5 | Accessibility | `lib/i18n.tsx`, `lib/prefs.tsx`, `index.css` |
| 6 | Authority dashboard | `pages/authority/*` |
| + | Priority: scoring, age ladder, manual override | `services/ticket_service.py` (`compute_priority`, `escalate_for_age`, `set_priority`) |
| + | Ticket comments | `services/ticket_service.py` (`add_comment`, `can_view_ticket`), `api/tickets.py` |
| + | Public transparency page (no login) | `services/stats_service.py`, `api/reference.py` (`/public/stats`), `pages/Transparency.tsx` |

Accessibility is driven by two attributes on `<html>` that redefine CSS tokens,
so every component picks up large-text and high-contrast without knowing they
exist. Language, large text and high contrast are all available *before*
sign-in, because someone who needs large text needs it on the login screen.

## Checks

```powershell
cd backend
python -m pytest        # 62 tests

cd frontend
npm run lint
npm run build
```
