"""Populate realistic content so the app is not empty during a demo.

    python -m scripts.demo_data
    python -m scripts.demo_data --reset   # delete existing demo tickets first

Creates tickets across several wards, deliberately including duplicate
clusters that land in the authority review queue unmerged -- that queue is the
thing worth showing, so it must not be empty.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.category import Category
from app.models.emergency import Alert, SosRequest
from app.models.enums import (
    AlertSeverity,
    AlertTargetType,
    EmergencyType,
    SosStatus,
    TicketStatus,
    UserRole,
)
from app.models.geography import Municipality, Ward
from app.models.notification import Notification
from app.models.profile import Profile
from app.models.ticket import (
    DuplicateCandidate,
    Ticket,
    TicketCorroboration,
    TicketPhoto,
    TicketStatusHistory,
)
from app.schema.ticket import TicketCreateRequest
from app.services.ticket_service import corroborate, create_ticket, update_status

rng = random.Random(7)

# (category key, English text, Nepali text). Pairs marked as a cluster below
# describe the same incident and should surface as duplicate suggestions.
SCENARIOS: list[dict] = [
    {
        "category": "pothole",
        "cluster": [
            ("en", "There is a deep pothole on the road near the bus stop. Motorcycles fall into it every evening."),
            ("ne", "बस स्टप नजिक सडकमा गहिरो खाल्डो छ। साँझमा मोटरसाइकल लड्छन्।"),
            ("en", "Big hole in the middle of the road by the bus stop, someone will get hurt."),
        ],
    },
    {
        "category": "garbage",
        "cluster": [
            ("ne", "स्कूलको अगाडि गत हप्तादेखि फोहोर थुप्रिएको छ। दुर्गन्ध आइरहेको छ।"),
            ("en", "Garbage has been piling up in front of the school since last week, nobody collects it."),
        ],
    },
    {
        "category": "street_light",
        "cluster": [
            ("en", "The street light beside the temple has not been working for two weeks. It is pitch dark at night."),
        ],
    },
    {
        "category": "drainage",
        "cluster": [
            ("ne", "मुख्य चोकमा ढल पूरै जाम भएको छ र फोहोर पानी सडकमा बगेको छ।"),
            ("en", "The drain at the main chowk is blocked and sewage is overflowing onto the road."),
        ],
    },
    {
        "category": "water_supply",
        "cluster": [
            ("en", "There has been no drinking water supply in our area for over a week. We are buying tanker water."),
        ],
    },
    {
        "category": "electricity",
        "cluster": [
            ("ne", "बिजुलीको तार होचो झुन्डिएको छ, बच्चाहरू तलबाट हिँड्छन्। जोखिमपूर्ण छ।"),
        ],
    },
    {
        "category": "stray_animals",
        "cluster": [
            ("en", "A pack of stray dogs near the college gate has been chasing people for days."),
        ],
    },
    {
        "category": "waterlogging",
        "cluster": [
            ("en", "The whole road floods after every rain. Yesterday it was knee deep."),
            ("ne", "पानी परेपिच्छे सडक डुब्छ। हिजो घुँडासम्म पानी थियो।"),
        ],
    },
]

TITLES = {
    "pothole": "Pothole on the road",
    "garbage": "Garbage not collected",
    "street_light": "Street light not working",
    "drainage": "Drain blocked",
    "water_supply": "No water supply",
    "electricity": "Hanging electric wire",
    "stray_animals": "Stray dogs",
    "waterlogging": "Road floods after rain",
}


def ring_point(
    lat: float, lon: float, metres: float, bearing: float
) -> tuple[float, float]:
    """Deterministic point at a fixed distance and bearing."""
    d_lat = (metres * math.cos(bearing)) / 110_574.0
    d_lon = (metres * math.sin(bearing)) / (
        111_320.0 * max(math.cos(math.radians(lat)), 1e-6)
    )
    return round(lat + d_lat, 6), round(lon + d_lon, 6)


def offset(lat: float, lon: float, metres: float) -> tuple[float, float]:
    bearing = rng.uniform(0, 2 * math.pi)
    d_lat = (metres * math.cos(bearing)) / 110_574.0
    d_lon = (metres * math.sin(bearing)) / (
        111_320.0 * max(math.cos(math.radians(lat)), 1e-6)
    )
    return round(lat + d_lat, 6), round(lon + d_lon, 6)


def reset(db: Session) -> None:
    """Delete every ticket and its dependents. Reference data is untouched."""
    for model in (
        DuplicateCandidate,
        TicketCorroboration,
        TicketStatusHistory,
        TicketPhoto,
        Notification,
        SosRequest,
        Alert,
    ):
        db.execute(delete(model))
    db.flush()

    # Children first: parent_id is ON DELETE SET NULL, not cascade.
    db.execute(delete(Ticket).where(Ticket.parent_id.isnot(None)))
    db.flush()
    db.execute(delete(Ticket))
    db.flush()
    print("  cleared existing tickets, alerts and SOS requests")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create demo content.")
    parser.add_argument("--reset", action="store_true", help="delete existing first")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        if args.reset:
            reset(session)

        citizens = list(
            session.scalars(
                select(Profile).where(Profile.role == UserRole.CITIZEN)
            ).all()
        )
        authority = session.scalar(
            select(Profile).where(
                Profile.role == UserRole.AUTHORITY, Profile.ward_id.isnot(None)
            )
        )

        if not citizens or authority is None:
            print("No demo accounts found. Run: python -m scripts.seed")
            return 1

        categories = {c.key: c for c in session.scalars(select(Category)).all()}
        ward = session.get(Ward, authority.ward_id)
        if ward is None:
            print("The demo authority has no ward.")
            return 1

        print(f"Creating demo content in ward {ward.number} ...")

        created: list[Ticket] = []
        for index, scenario in enumerate(SCENARIOS):
            category = categories.get(scenario["category"])
            if category is None:
                continue

            # Scenarios sit on a ring around the ward centroid: close enough
            # that every one stays inside this ward (generated ward centroids
            # are only ~800m apart), far enough apart that two unrelated
            # issues never fall inside each other's match radius.
            angle = (2 * math.pi * index) / len(SCENARIOS)
            base_lat, base_lon = ring_point(
                ward.centroid_lat, ward.centroid_lon, 380, angle
            )

            for position, (lang, text) in enumerate(scenario["cluster"]):
                reporter = citizens[(index + position) % len(citizens)]
                lat, lon = (
                    (base_lat, base_lon)
                    if position == 0
                    else offset(base_lat, base_lon, rng.uniform(5, category.match_radius_m * 0.6))
                )

                ticket, _ = create_ticket(
                    session,
                    reporter,
                    TicketCreateRequest(
                        title=TITLES.get(scenario["category"]),
                        description=text,
                        category_id=category.id,
                        latitude=lat,
                        longitude=lon,
                        address_text="Near the main road",
                        description_lang=lang,
                    ),
                )
                created.append(ticket)

        session.flush()
        print(f"  tickets                {len(created):>4}")

        pending = session.scalars(select(DuplicateCandidate)).all()
        print(f"  duplicate suggestions  {len(pending):>4}  (left unmerged for the review queue)")

        # Move a few through the workflow so the dashboard is not all "reported".
        parents = [t for t in created if t.parent_id is None]
        for ticket in parents[:2]:
            update_status(session, authority, ticket, TicketStatus.VERIFIED, "Inspected on site")
        for ticket in parents[2:3]:
            update_status(session, authority, ticket, TicketStatus.VERIFIED, "Inspected")
            update_status(session, authority, ticket, TicketStatus.IN_PROGRESS, "Crew assigned")

        # A couple of corroborations, from a citizen who did not report it.
        confirmed = 0
        for ticket in parents[:4]:
            for citizen in citizens:
                if citizen.id == ticket.reporter_id:
                    continue
                try:
                    corroborate(
                        session,
                        citizen,
                        ticket,
                        is_confirmed=True,
                        latitude=ticket.latitude,
                        longitude=ticket.longitude,
                    )
                    confirmed += 1
                except Exception:
                    # Already voted, or too far: skip silently, this is demo data.
                    session.rollback()
                    break
        print(f"  corroborations         {confirmed:>4}")

        # An open SOS and an active alert, so those screens have content.
        session.add(
            SosRequest(
                citizen_id=citizens[0].id,
                emergency_type=EmergencyType.MEDICAL,
                latitude=ward.centroid_lat,
                longitude=ward.centroid_lon,
                ward_id=ward.id,
                municipality_id=ward.municipality_id,
                note="Road accident near the chowk, one person injured.",
                contact_phone=citizens[0].phone or "9800000000",
                status=SosStatus.OPEN,
            )
        )

        municipality = session.get(Municipality, ward.municipality_id)
        session.add(
            Alert(
                created_by_id=authority.id,
                municipality_id=municipality.id if municipality else ward.municipality_id,
                title_en="Heavy rainfall warning",
                title_ne="भारी वर्षाको चेतावनी",
                body_en=(
                    "Heavy rainfall is forecast for the next 48 hours. Low-lying "
                    "areas may flood."
                ),
                body_ne=(
                    "आगामी ४८ घण्टा भारी वर्षाको पूर्वानुमान छ। होचो क्षेत्रमा "
                    "डुबान हुन सक्छ।"
                ),
                instructions_en=(
                    "Avoid crossing flooded roads. Keep emergency numbers handy. "
                    "Move vehicles to higher ground."
                ),
                instructions_ne=(
                    "डुबेको सडक नतर्नुहोस्। आपतकालीन नम्बर तयार राख्नुहोस्। "
                    "सवारी अग्लो ठाउँमा सार्नुहोस्।"
                ),
                severity=AlertSeverity.WARNING,
                target_type=AlertTargetType.WARD,
                ward_ids=[ward.id],
                starts_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=2),
                is_active=True,
            )
        )

        session.commit()
        print("  1 open SOS request, 1 active alert")
        print("\nSign in as kmc.ward5@sahayatri.np to work the queue.")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
