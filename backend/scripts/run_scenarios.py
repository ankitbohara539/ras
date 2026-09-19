"""End-to-end scenario test against the real database, services and APIs.

Drives the API the way the app does -- as real demo accounts -- through every
main flow, checks each outcome, and deletes everything it created at the end
(tickets, comments, complaints, SOS, alerts, notifications, uploaded photos),
even if a check fails midway.

    python -m scripts.run_scenarios

Authentication is the one thing bypassed: requests run as a chosen profile
directly, since the demo accounts' passwords are not known here. Login itself
is exercised separately with a wrong password.

Unlike the unit tests this needs the network: Supabase (database, storage),
Nominatim (place names, ward routing) and the routing service.
"""

from __future__ import annotations

import io
import json
import sys
import time
import traceback
import warnings
from datetime import UTC, datetime
from uuid import UUID

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import delete, event, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.geo import haversine_m  # noqa: E402
from app.core.security import get_current_profile  # noqa: E402
from app.core.supabase import get_supabase  # noqa: E402
from app.db.session import get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models.civic import CivicComplaint  # noqa: E402
from app.models.emergency import Alert, SosRequest  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.geography import Ward  # noqa: E402
from app.models.notification import Notification  # noqa: E402
from app.models.profile import Profile  # noqa: E402
from app.models.ticket import Ticket, TicketPhoto  # noqa: E402

# ------------------------------------------------------------ harness

results: list[tuple[str, bool, str]] = []
current_section = ""


def section(name: str) -> None:
    global current_section
    current_section = name
    print(f"\n== {name}")


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((f"{current_section}: {name}", bool(ok), detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail and not ok else ""))
    return bool(ok)


actor: list[Profile | None] = [None]
app.dependency_overrides[get_current_profile] = lambda: actor[0]
client = TestClient(app)


def as_(profile: Profile) -> TestClient:
    actor[0] = profile
    return client


def jpeg(color=(120, 90, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, "JPEG")
    return buf.getvalue()


created_tickets: list[UUID] = []
created_civic: list[UUID] = []
created_sos: list[UUID] = []
created_alerts: list[UUID] = []
started_at = datetime.now(UTC)


def create_ticket(who, description, category_key, lat, lon, photo=False):
    payload = {
        "description": description,
        "latitude": lat,
        "longitude": lon,
        "category_id": categories[category_key],
    }
    files = [("photos", ("p.jpg", jpeg(), "image/jpeg"))] if photo else []
    r = as_(who).post("/api/tickets", data={"payload": json.dumps(payload)}, files=files)
    if r.status_code == 201:
        created_tickets.append(UUID(r.json()["ticket"]["id"]))
    return r


def ticket(who, tid):
    return as_(who).get(f"/api/tickets/{tid}").json()


# ------------------------------------------------------------ setup

db = get_session_factory()()
profiles = {p.email: p for p in db.scalars(select(Profile))}
for p in profiles.values():
    db.expunge(p)

citizen1 = profiles["sita@example.com"]
citizen2 = profiles["ram@example.com"]
citizen3 = profiles["gita@example.com"]
citizen4 = profiles["ankit@gmail.com"]
citizen5 = profiles["ward9user1@gmail.com"]
lalitpur_citizen = profiles["hari@example.com"]
ward8_officer = profiles["ward8@gmail.com"]
ward5_officer = profiles["kmc.ward5@sahayatri.np"]
city_desk = profiles["kmc.city@sahayatri.np"]
admin = profiles["admin@sahayatri.np"]

categories = {}
all_open = db.scalars(select(Ticket).where(Ticket.parent_id.is_(None))).all()
ward8 = next(
    w for w in db.scalars(select(Ward)) if w.municipality.code == "KMC" and w.number == 8
)
# A clear spot in ward 8: its centre, nudged until no real ticket is within
# 400 m, so test reports can never auto-merge into anyone's real report.
P = (ward8.centroid_lat, ward8.centroid_lon)
for step in range(12):
    if all(haversine_m(*P, t.latitude, t.longitude) > 400 for t in all_open):
        break
    P = (P[0] + 0.0012, P[1] + 0.0008)
FAR = (P[0] + 0.02, P[1] + 0.02)  # ~3 km away
db.close()

print(f"Test spot: {P[0]:.5f}, {P[1]:.5f}")

n_queries = [0]
event.listen(get_engine(), "before_cursor_execute", lambda *a: n_queries.__setitem__(0, n_queries[0] + 1))


# ------------------------------------------------------------ scenarios


def reference_data():
    section("Reference data")
    r = client.get("/api/categories")
    cats = r.json()
    check("categories load", r.status_code == 200 and len(cats) >= 15, f"{r.status_code} {len(cats)}")
    for c in cats:
        categories[c["key"]] = c["id"]
    check(
        "hazard categories exist",
        {"road_blocked", "footpath_damage", "accessibility_barrier"} <= set(categories),
    )

    n_queries[0] = 0
    client.get("/api/categories")
    check("categories served from server cache", n_queries[0] == 0, f"{n_queries[0]} queries")

    munis = client.get("/api/municipalities").json()
    kmc = next(m for m in munis if m["code"] == "KMC")
    detail = client.get(f"/api/municipalities/{kmc['id']}").json()
    names = {w["number"]: w["name_en"] for w in detail["wards"]}
    check("KMC has 32 named wards", len(names) == 32 and all(names.values()))
    check("KMC ward 9 is Gaushala", names.get(9) == "Gaushala", str(names.get(9)))

    as_(citizen1)
    r = client.get(f"/api/wards/nearest?latitude={P[0]}&longitude={P[1]}")
    check("test spot routes to ward 8", r.json().get("number") == 8, str(r.json()))
    r = client.get(f"/api/geo/reverse?latitude={P[0]}&longitude={P[1]}")
    body = r.json()
    check("reverse geocode gives place + ward", bool(body.get("place_name")) and body["ward"]["number"] == 8, str(body)[:200])
    n_queries[0] = 0
    client.get(f"/api/geo/reverse?latitude={P[0]}&longitude={P[1]}")
    check("reverse geocode needs no ward query (cached)", n_queries[0] <= 1, f"{n_queries[0]} queries")
    r = client.get("/api/geo/search?q=Ratna Park")
    check("place search", r.status_code == 200 and len(r.json()) > 0)


def tickets_flow():
    section("Tickets: create, multi-report, auto-merge")
    r = create_ticket(citizen1, "Large pothole in the middle of the road near the temple gate", "pothole", *P, photo=True)
    ok = check("create with photo", r.status_code == 201, r.text[:200])
    if not ok:
        return {}
    t1 = r.json()["ticket"]
    check("routed to ward 8", t1["ward_number"] == 8)
    check("photo stored with signed url", len(t1["photos"]) == 1 and bool(t1["photos"][0]["url"]))
    check("address auto-filled from map", bool(t1["address_text"]), str(t1["address_text"]))

    # The citizen's multi-report: several problems at the same spot.
    r2 = create_ticket(citizen1, "Garbage pile dumped beside the temple wall, smells bad", "garbage", *P)
    r3 = create_ticket(citizen1, "Large pothole in the middle of the road near the temple gate", "pothole", *P)
    t2, t3 = r2.json(), r3.json()
    check("2nd report of the batch not merged", t2.get("auto_merged_into") is None and t2["ticket"]["status"] == "reported")
    check(
        "same person's repeat is not auto-merged into their own",
        t3.get("auto_merged_into") is None,
        str(t3.get("auto_merged_into")),
    )
    check("...but it is still suggested to the officer", len(t3.get("possible_duplicates", [])) > 0)

    r4 = create_ticket(citizen2, "Big pothole in the middle of the road near the temple gate", "pothole", *P)
    t4 = r4.json()
    merged = t4.get("auto_merged_into")
    check("another citizen's duplicate auto-merges (>=80%)", merged is not None and merged["id"] == t1["id"], f"score={t4.get('auto_merge_score')}")
    parent = ticket(citizen1, t1["id"])
    check("parent now has 2 reporters", parent["child_count"] == 1)

    section("Tickets: lists and visibility")
    mine = as_(citizen1).get("/api/tickets?mine=true&limit=100").json()
    ids = {t["id"] for t in mine["items"]}
    check("my reports lists all three", {t1["id"], t2["ticket"]["id"], t3["ticket"]["id"]} <= ids)
    check("total matches rows (no count query needed)", mine["total"] == len(mine["items"]))
    listing = as_(citizen3).get("/api/tickets?limit=100").json()
    check("merged child hidden from main list", t4["ticket"]["id"] not in {t["id"] for t in listing["items"]})
    near = as_(citizen3).get(f"/api/tickets/nearby?latitude={P[0]}&longitude={P[1]}&radius_m=500").json()
    check("nearby finds it", t1["id"] in {t["id"] for t in near["items"]})
    r = as_(lalitpur_citizen).get(f"/api/tickets/{t1['id']}")
    check("Lalitpur citizen cannot open a Kathmandu ticket", r.status_code == 403, str(r.status_code))
    d = ticket(ward8_officer, t3["ticket"]["id"])
    check("officer sees duplicate suggestion on the repeat", len(d["duplicate_candidates"]) > 0)
    q = as_(ward8_officer).get("/api/tickets/review/queue").json()
    check("review queue has the suggestion", any(c["ticket_id"] == t3["ticket"]["id"] for c in q))
    d = ticket(citizen1, t1["id"])
    check("detail: children, history, reporter", len(d["children"]) == 1 and len(d["history"]) >= 1 and d["reporter_name"] == citizen1.full_name)

    return {"t1": t1["id"], "t2": t2["ticket"]["id"], "t3": t3["ticket"]["id"], "t4": t4["ticket"]["id"]}


def comments_flow(ids):
    section("Comments raise and lower priority")
    t1 = ids["t1"]
    before = ticket(citizen1, t1)["priority"]
    check("starts medium (pothole + 1 extra reporter)", before == "medium", before)

    as_(citizen3).post(f"/api/tickets/{t1}/comments", json={"body": "I saw this too"})
    c2 = as_(citizen2).post(f"/api/tickets/{t1}/comments", json={"body": "fix this, it has been quite a headache"}).json()
    as_(citizen3).post(f"/api/tickets/{t1}/comments", json={"body": "please repair it, someone will get hurt"})
    check("2 urgent commenters: still medium", ticket(citizen1, t1)["priority"] == "medium")
    as_(ward8_officer).post(f"/api/tickets/{t1}/comments", json={"body": "We will fix this immediately"})
    check("an officer's 'immediately' does not count", ticket(citizen1, t1)["urgent_commenter_count"] == 2)
    as_(citizen4).post(f"/api/tickets/{t1}/comments", json={"body": "When will this be fixed?"})
    d = ticket(citizen1, t1)
    check("3rd person asking for a fix -> high", d["priority"] == "high" and d["urgent_commenter_count"] == 3, f"{d['priority']} {d['urgent_commenter_count']}")
    check("history explains why", any("asked in the comments" in (h["note"] or "") for h in d["history"]))
    comments = as_(citizen1).get(f"/api/tickets/{t1}/comments").json()
    check("urgent comments are flagged", sum(c["is_urgent"] for c in comments["items"]) == 4)
    as_(citizen2).delete(f"/api/tickets/{t1}/comments/{c2['id']}")
    check("deleting one lowers it back to medium", ticket(citizen1, t1)["priority"] == "medium")
    r = as_(citizen3).post(f"/api/tickets/{ids['t4']}/comments", json={"body": "hello"})
    check("cannot comment on a merged duplicate", r.status_code == 409)


def corroboration_flow(ids):
    section("Corroboration")
    t1 = ids["t1"]
    r = as_(citizen1).post(f"/api/tickets/{t1}/corroborate", json={"is_confirmed": True, "latitude": P[0], "longitude": P[1]})
    check("cannot confirm own report", r.status_code == 409)
    r = as_(citizen3).post(f"/api/tickets/{t1}/corroborate", json={"is_confirmed": True, "latitude": FAR[0], "longitude": FAR[1]})
    check("must be nearby", r.status_code == 403)
    r = as_(citizen3).post(f"/api/tickets/{t1}/corroborate", json={"is_confirmed": True, "latitude": P[0], "longitude": P[1]})
    check("nearby citizen confirms", r.status_code == 200 and r.json()["corroboration_count"] == 1)
    r = as_(citizen3).post(f"/api/tickets/{t1}/corroborate", json={"is_confirmed": True, "latitude": P[0], "longitude": P[1]})
    check("only once", r.status_code == 409)


def authority_flow(ids):
    section("Officer actions")
    t1, t2, t3, t4 = ids["t1"], ids["t2"], ids["t3"], ids["t4"]
    r = as_(ward5_officer).patch(f"/api/tickets/{t1}/status", json={"status": "verified"})
    check("another ward's officer is refused", r.status_code == 403, str(r.status_code))
    r = as_(ward8_officer).patch(f"/api/tickets/{t1}/status", json={"status": "verified", "note": "Seen on site"})
    check("verify", r.status_code == 200 and r.json()["status"] == "verified")
    r = as_(ward8_officer).patch(f"/api/tickets/{t1}/status", json={"status": "reported"})
    check("illegal transition refused", r.status_code == 409)

    r = as_(ward8_officer).patch(f"/api/tickets/{t1}/priority", json={"priority": "critical", "note": "school route"})
    check("manual priority locks", r.status_code == 200 and r.json()["priority_locked"] and r.json()["priority"] == "critical")
    for who in (citizen2, citizen4, citizen5):
        as_(who).post(f"/api/tickets/{t1}/comments", json={"body": "urgent please fix"})
    check("locked priority ignores comments", ticket(citizen1, t1)["priority"] == "critical")
    r = as_(ward8_officer).patch(f"/api/tickets/{t1}/priority", json={"priority": None})
    check("unlocking recomputes", r.status_code == 200 and not r.json()["priority_locked"] and r.json()["priority"] == "high", r.json().get("priority"))

    r = as_(ward8_officer).post(f"/api/tickets/{t4}/split")
    check("split the merged duplicate out", r.status_code == 200 and r.json()["status"] == "reported")
    check("parent back to 1 reporter", ticket(citizen1, t1)["child_count"] == 0)
    r = as_(ward8_officer).post(f"/api/tickets/{t4}/merge", json={"parent_ticket_id": t1})
    check("officer merges it back", r.status_code == 200 and r.json()["child_count"] == 1)
    r = as_(ward8_officer).post(f"/api/tickets/{t3}/merge", json={"parent_ticket_id": t1})
    check("officer merges the citizen's own repeat", r.status_code == 200 and r.json()["child_count"] == 2)

    r = as_(ward8_officer).patch(f"/api/tickets/{t1}/status", json={"status": "in_progress"})
    check("in progress", r.status_code == 200)
    r = as_(ward8_officer).patch(f"/api/tickets/{t1}/status", json={"status": "resolved", "resolution_note": "Filled and resurfaced"})
    check("resolve", r.status_code == 200 and r.json()["status"] == "resolved")
    check("duplicates resolve with it", ticket(citizen2, t4)["status"] == "resolved")

    r = as_(ward8_officer).get(f"/api/municipalities/{ticket(ward8_officer, t2)['municipality_id']}")
    ward9 = next(w for w in r.json()["wards"] if w["number"] == 9)
    r = as_(ward8_officer).patch(f"/api/tickets/{t2}/ward", json={"ward_id": ward9["id"]})
    check("reassign to another ward", r.status_code == 200 and r.json()["ward_number"] == 9)
    r = as_(ward8_officer).patch(f"/api/tickets/{t2}/status", json={"status": "verified"})
    check("...after which ward 8 can no longer act on it", r.status_code == 403)
    r = as_(city_desk).patch(f"/api/tickets/{t2}/status", json={"status": "verified"})
    check("municipality-wide desk still can", r.status_code == 200)


def notifications_flow():
    section("Notifications and the unread badge")
    c = as_(citizen1)
    before = c.get("/api/notifications?unread_only=true").json()
    check("citizen has unread notifications from the flows above", before["unread"] > 0, str(before["unread"]))
    full = c.get("/api/notifications").json()
    one = next(n for n in full["items"] if n["read_at"] is None)
    r = c.post("/api/notifications/read", json=[one["id"]])
    after_one = c.get("/api/notifications?unread_only=true").json()["unread"]
    check("opening one marks just that one read", r.status_code == 200 and after_one == before["unread"] - 1, f"{before['unread']} -> {after_one}")
    r = c.post("/api/notifications/read")
    check("mark all read returns 0 unread", r.status_code == 200 and r.json()["unread"] == 0, str(r.json().get("unread")))
    badge = c.get("/api/notifications?unread_only=true").json()
    check("the badge's own query then says 0", badge["unread"] == 0 and badge["items"] == [])


def civic_flow():
    section("Civic complaints")
    payload = {"category": "littering", "description": "Threw a bag of rubbish into the drain", "latitude": P[0], "longitude": P[1]}
    r = as_(citizen1).post("/api/civic", data={"payload": json.dumps(payload)})
    check("photo required", r.status_code == 422)
    r = as_(citizen1).post("/api/civic", data={"payload": json.dumps(payload)}, files=[("photos", ("a.jpg", jpeg(), "image/jpeg"))])
    ok = check("file with photo", r.status_code == 201, r.text[:200])
    if not ok:
        return
    cid = r.json()["id"]
    created_civic.append(UUID(cid))
    check("routed to ward 8 with a photo", r.json()["ward_number"] == 8 and bool(r.json()["photos"][0]["url"]))
    check("other citizen cannot see it", as_(citizen2).get(f"/api/civic/{cid}").status_code == 404)
    check("another ward cannot see it", as_(ward5_officer).get(f"/api/civic/{cid}").status_code == 404)
    q = as_(ward8_officer).get("/api/civic").json()
    check("ward office queue has it, with reporter", any(i["id"] == cid and i["reporter_name"] for i in q["items"]))
    check("closing needs a note", as_(ward8_officer).patch(f"/api/civic/{cid}/status", json={"status": "dismissed"}).status_code == 422)
    r = as_(ward8_officer).patch(f"/api/civic/{cid}/status", json={"status": "action_taken", "note": "Warned; fined Rs 500"})
    check("action taken", r.status_code == 200)
    mine = as_(citizen1).get(f"/api/civic/{cid}").json()
    check("reporter sees the outcome", mine["status"] == "action_taken" and "fined" in mine["action_note"])
    n = as_(citizen1).get("/api/notifications?unread_only=true").json()
    check("reporter notified", any("civic complaint" in x["title_en"] for x in n["items"]))


def hazards_flow():
    section("Hazard map and safer route")
    h = (P[0] - 0.004, P[1] - 0.004)
    r = create_ticket(citizen5, "Road completely flooded after the rain, water knee deep", "waterlogging", *h)
    check("flood report", r.status_code == 201)
    box = f"min_lat={h[0]-0.01}&min_lon={h[1]-0.01}&max_lat={h[0]+0.01}&max_lon={h[1]+0.01}"
    hz = as_(citizen1).get(f"/api/hazards?{box}&night=false").json()
    flood = [x for x in hz["items"] if x["kind"] == "flooding" and abs(x["latitude"] - h[0]) < 1e-6]
    check("flood appears on the hazard map", len(flood) == 1)
    r = as_(citizen1).post(
        "/api/hazards/route",
        json={"start": {"latitude": h[0], "longitude": h[1] - 0.005}, "end": {"latitude": h[0], "longitude": h[1] + 0.005}, "mode": "walk", "night": False},
    )
    ok = check("route planned", r.status_code == 200, r.text[:200])
    if ok:
        plan = r.json()
        on_usual = flood[0]["id"] in plan["fastest"]["hazard_ids"] if flood else False
        if on_usual:
            check("suggests a detour around the flood", plan["recommended"] == "safer" and flood[0]["id"] not in plan["safer"]["hazard_ids"], json.dumps(plan["notes"]))
        else:
            check("usual route already clear of the flood", True)
        check("always carries the disclaimer", "Conditions" in plan["disclaimer"])
    check("zoomed-out map refused", as_(citizen1).get("/api/hazards?min_lat=26&min_lon=84&max_lat=28&max_lon=86").status_code == 422)


def sos_and_alerts():
    section("SOS")
    r = as_(citizen1).post("/api/sos", json={"emergency_type": "medical", "latitude": P[0], "longitude": P[1], "note": "scenario test"})
    ok = check("raise SOS", r.status_code == 201, r.text[:200])
    if ok:
        sid = r.json()["sos"]["id"]
        created_sos.append(UUID(sid))
        check("emergency contacts returned", len(r.json()["emergency_contacts"]) > 0)
        queue = as_(ward8_officer).get("/api/sos?status=open").json()
        check("ward office sees it", any(s["id"] == sid for s in queue))
        r = as_(ward8_officer).patch(f"/api/sos/{sid}", json={"status": "acknowledged"})
        check("acknowledge", r.status_code == 200 and r.json()["status"] == "acknowledged")

    section("Alerts")
    muni = ticket(citizen1, created_tickets[0])["municipality_id"]
    r = as_(ward8_officer).post(
        "/api/alerts",
        json={
            "municipality_id": muni,
            "title_en": "Scenario test: road collapse",
            "body_en": "Test alert, please ignore",
            "severity": "critical",
            "target_type": "radius",
            "center_lat": P[0],
            "center_lon": P[1],
            "radius_m": 200,
        },
    )
    ok = check("publish critical alert", r.status_code == 201, r.text[:300])
    if ok:
        aid = r.json()["id"]
        created_alerts.append(UUID(aid))
        alerts = as_(citizen1).get("/api/alerts").json()
        check("citizens see it", any(a["id"] == aid for a in alerts))
        box = f"min_lat={P[0]-0.01}&min_lon={P[1]-0.01}&max_lat={P[0]+0.01}&max_lon={P[1]+0.01}"
        hz = as_(citizen1).get(f"/api/hazards?{box}").json()
        check("it becomes an avoided hazard area", any(x["alert_id"] == aid and x["avoid"] for x in hz["items"]))
        r = as_(ward8_officer).patch(f"/api/alerts/{aid}/deactivate")
        check("deactivate", r.status_code == 200)
        hz = as_(citizen1).get(f"/api/hazards?{box}").json()
        check("gone from the hazard map", not any(x["alert_id"] == aid for x in hz["items"]))


def public_and_auth():
    section("Public stats and auth")
    r = client.get("/api/public/stats")
    check("transparency stats", r.status_code == 200 and r.json()["total_tickets"] >= 1)
    n_queries[0] = 0
    client.get("/api/public/stats")
    check("stats cached for 30 s", n_queries[0] == 0, f"{n_queries[0]} queries")
    actor[0] = None
    r = client.post("/api/auth/login", json={"email": "sita@example.com", "password": "definitely-wrong"})
    check("wrong password is 401, not 500", r.status_code == 401, str(r.status_code))


# ------------------------------------------------------------ run + cleanup


def cleanup():
    print("\n== Cleanup")
    s = get_session_factory()()
    try:
        photo_paths = [
            p.storage_path
            for p in s.scalars(select(TicketPhoto).where(TicketPhoto.ticket_id.in_(created_tickets)))
        ]
        for cid in created_civic:
            c = s.get(CivicComplaint, cid)
            if c:
                photo_paths += [p.storage_path for p in c.photos]
                s.delete(c)
        # Children before parents (parent_id is SET NULL, but be tidy).
        for tid in reversed(created_tickets):
            t = s.get(Ticket, tid)
            if t:
                s.delete(t)
        for sid in created_sos:
            x = s.get(SosRequest, sid)
            if x:
                s.delete(x)
        for aid in created_alerts:
            x = s.get(Alert, aid)
            if x:
                s.delete(x)
        # Notifications with no ticket/alert/SOS link (civic, alert fan-out).
        test_users = [p.id for p in (citizen1, citizen2, citizen3, citizen4, citizen5, ward8_officer)]
        s.execute(
            delete(Notification).where(
                Notification.user_id.in_(test_users),
                Notification.created_at >= started_at,
                Notification.ticket_id.is_(None),
                Notification.sos_request_id.is_(None),
                Notification.alert_id.is_(None),
            )
        )
        s.commit()
        if photo_paths:
            get_supabase().storage.from_(get_settings().supabase_photo_bucket).remove(photo_paths)
        left = s.scalars(select(Ticket.id).where(Ticket.id.in_(created_tickets))).all() if created_tickets else []
        print(f"  removed {len(created_tickets)} tickets, {len(created_civic)} complaints, "
              f"{len(created_sos)} SOS, {len(created_alerts)} alerts, {len(photo_paths)} photos; "
              f"{len(left)} left behind")
    finally:
        s.close()


def main() -> int:
    t0 = time.perf_counter()
    try:
        reference_data()
        ids = tickets_flow()
        if ids:
            comments_flow(ids)
            corroboration_flow(ids)
            authority_flow(ids)
        notifications_flow()
        civic_flow()
        hazards_flow()
        sos_and_alerts()
        public_and_auth()
    except Exception:
        traceback.print_exc()
        check("scenario run finished without crashing", False, "exception above")
    finally:
        cleanup()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed in {time.perf_counter() - t0:.0f}s")
    for name, _, detail in failed:
        print(f"  FAILED: {name}  {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
