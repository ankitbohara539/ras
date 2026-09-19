"""End-to-end walkthrough of the core product loop.

    python -m scripts.demo_flow

Two citizens report the same pothole in different languages. A third
corroborates. An authority reviews the suggestion, merges, and resolves --
and everyone who reported it gets notified.
"""

from __future__ import annotations

import json
import sys

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "Sahayatri@2025"

client = TestClient(app)


def ward_five_centre(token: str) -> tuple[float, float]:
    """Find the real centroid of the demo authority's ward.

    Hardcoded coordinates are brittle: ward centroids are generated, so a
    reseed moves them and the reports land in a ward the demo authority
    cannot touch. Ask the API where the ward actually is.
    """
    me = client.get("/api/users/me", headers=auth(token)).json()
    municipality = client.get(
        f"/api/municipalities/{me['municipality_id']}"
    ).json()

    for ward in municipality["wards"]:
        if ward["id"] == me["ward_id"]:
            return ward["centroid_lat"], ward["centroid_lon"]

    raise RuntimeError("Could not locate the demo ward.")


def offset(point: tuple[float, float], north_m: float, east_m: float):
    """Shift a point by a few metres, for 'same spot, slightly different'."""
    import math

    lat = point[0] + north_m / 110_574.0
    lon = point[1] + east_m / (111_320.0 * math.cos(math.radians(point[0])))
    return round(lat, 6), round(lon, 6)


def login(email: str) -> str:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def report(token: str, description: str, point: tuple[float, float], lang: str) -> dict:
    payload = {
        "description": description,
        "latitude": point[0],
        "longitude": point[1],
        "description_lang": lang,
        "address_text": "Near the bus stop",
    }
    response = client.post(
        "/api/tickets",
        data={"payload": json.dumps(payload)},
        headers=auth(token),
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    print("=" * 72)
    print("1. SITA REPORTS A POTHOLE (English)")
    print("=" * 72)

    sita = login("sita@example.com")

    # Report at the centre of Sita's own ward, so the ward-5 authority owns it.
    spot_a = ward_five_centre(sita)
    spot_b = offset(spot_a, north_m=12, east_m=9)
    spot_nearby = offset(spot_a, north_m=6, east_m=4)
    first = report(
        sita,
        "There is a big pothole on the road near the bus stop. "
        "Motorcycles are falling into it every day.",
        spot_a,
        "en",
    )
    ticket_a = first["ticket"]
    print(f"  {ticket_a['public_code']}  status={ticket_a['status']}")
    print(
        f"  auto-classified as '{ticket_a['predicted_category_key']}' "
        f"({(ticket_a['category_confidence'] or 0):.0%} confidence)"
    )
    print(f"  duplicates suggested: {len(first['possible_duplicates'])}")

    print()
    print("=" * 72)
    print("2. RAM REPORTS THE SAME POTHOLE 15m AWAY (Nepali)")
    print("=" * 72)

    ram = login("ram@example.com")
    second = report(
        ram,
        "बस स्टप नजिक सडकमा ठूलो खाल्डो छ। मोटरसाइकल दैनिक लड्छन्। कृपया हेरिदिनुहोस्।",
        spot_b,
        "ne",
    )
    ticket_b = second["ticket"]
    print(f"  {ticket_b['public_code']}  status={ticket_b['status']}")
    print(f"  auto-classified as '{ticket_b['predicted_category_key']}'")
    print(f"\n  MATCHER SUGGESTS {len(second['possible_duplicates'])} duplicate(s):")

    for candidate in second["possible_duplicates"]:
        other = candidate["candidate"]
        print(f"    -> {other['public_code']}  score {candidate['score']:.2f}")
        print(f"       {candidate['explanation']}")
        print(
            f"       category {candidate['category_score']:.2f} | "
            f"text {candidate['text_score']:.2f} | "
            f"image {candidate['image_score']:.2f} | "
            f"geo {candidate['geo_score']:.2f}"
        )
    print("\n  Nothing merged yet -- both are still independent tickets.")

    print()
    print("=" * 72)
    print("3. GITA CORROBORATES FROM THE SAME SPOT")
    print("=" * 72)

    gita = login("gita@example.com")
    response = client.post(
        f"/api/tickets/{ticket_a['id']}/corroborate",
        json={
            "is_confirmed": True,
            "latitude": spot_nearby[0],
            "longitude": spot_nearby[1],
        },
        headers=auth(gita),
    )
    print(f"  {response.status_code}  {response.json().get('message')}")

    far = client.post(
        f"/api/tickets/{ticket_a['id']}/corroborate",
        json={"is_confirmed": True, "latitude": 27.6588, "longitude": 85.3247},
        headers=auth(login("hari@example.com")),
    )
    print(f"  someone 8km away tries to confirm: {far.status_code}")
    print(f"    {far.json().get('detail')}")

    own = client.post(
        f"/api/tickets/{ticket_a['id']}/corroborate",
        json={
            "is_confirmed": True,
            "latitude": spot_a[0],
            "longitude": spot_a[1],
        },
        headers=auth(sita),
    )
    print(f"  Sita tries to confirm her own report: {own.status_code}")
    print(f"    {own.json().get('detail')}")

    print()
    print("=" * 72)
    print("4. AUTHORITY REVIEWS THE MERGE QUEUE")
    print("=" * 72)

    authority = login("kmc.ward5@sahayatri.np")
    queue = client.get("/api/tickets/review/queue", headers=auth(authority))
    print(f"  pending suggestions in ward 5: {len(queue.json())}")

    merged = client.post(
        f"/api/tickets/{ticket_b['id']}/merge",
        json={"parent_ticket_id": ticket_a["id"], "note": "Same pothole"},
        headers=auth(authority),
    )
    if merged.status_code != 200:
        print(f"  merge failed: {merged.status_code} {merged.json()}")
        return 1

    parent = merged.json()
    print(f"  merged {ticket_b['public_code']} into {parent['public_code']}")
    print(f"  parent now has {parent['child_count']} child, priority={parent['priority']}")
    print(f"  children: {[c['public_code'] for c in parent['children']]}")

    print()
    print("=" * 72)
    print("5. WARD 10 AUTHORITY TRIES TO TOUCH A WARD 5 TICKET")
    print("=" * 72)

    other_ward = login("kmc.ward10@sahayatri.np")
    blocked = client.patch(
        f"/api/tickets/{ticket_a['id']}/status",
        json={"status": "verified"},
        headers=auth(other_ward),
    )
    print(f"  {blocked.status_code}  {blocked.json().get('detail')}")

    print()
    print("=" * 72)
    print("6. AUTHORITY VERIFIES, STARTS WORK, RESOLVES")
    print("=" * 72)

    for new_status, note in (
        ("verified", "Inspected on site"),
        ("in_progress", "Repair crew assigned"),
        ("resolved", "Pothole filled and compacted"),
    ):
        response = client.patch(
            f"/api/tickets/{ticket_a['id']}/status",
            json={"status": new_status, "note": note},
            headers=auth(authority),
        )
        body = response.json()
        print(f"  -> {new_status:12} {response.status_code}  ({note})")
        if response.status_code != 200:
            print(f"     {body.get('detail')}")

    illegal = client.patch(
        f"/api/tickets/{ticket_a['id']}/status",
        json={"status": "reported"},
        headers=auth(authority),
    )
    print(f"\n  illegal transition resolved -> reported: {illegal.status_code}")
    print(f"    {illegal.json().get('detail')}")

    print()
    print("=" * 72)
    print("7. BOTH REPORTERS WERE NOTIFIED")
    print("=" * 72)

    for name, token in (("Sita", sita), ("Ram", ram)):
        feed = client.get("/api/notifications", headers=auth(token)).json()
        print(f"\n  {name}: {feed['unread']} unread")
        for item in feed["items"][:3]:
            print(f"    - {item['title_en']}")

    child = client.get(f"/api/tickets/{ticket_b['id']}", headers=auth(ram)).json()
    print(
        f"\n  Ram's merged ticket {child['public_code']} is now "
        f"'{child['status']}' -- it followed its parent."
    )

    print()
    print("=" * 72)
    print("8. SOS")
    print("=" * 72)

    sos = client.post(
        "/api/sos",
        json={
            "emergency_type": "medical",
            "latitude": spot_a[0],
            "longitude": spot_a[1],
            "note": "Road accident, one person injured",
        },
        headers=auth(sita),
    ).json()
    print(f"  raised: {sos['sos']['status']}")
    print("  emergency contacts returned inline:")
    for contact in sos["emergency_contacts"][:4]:
        print(f"    {contact['phone']:14} {contact['name_en']}")

    queue = client.get("/api/sos", headers=auth(authority)).json()
    print(f"\n  ward authority sees {len(queue)} SOS request(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
