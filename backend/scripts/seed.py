"""Seed reference data and demo accounts.

Idempotent: re-running updates existing rows rather than duplicating them, so
it is safe to run after every schema change.

    python -m scripts.seed
    python -m scripts.seed --skip-accounts   # reference data only
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.geo import haversine_m
from app.core.supabase import get_supabase
from app.db.session import get_session_factory
from app.models.category import Category
from app.models.emergency import CivicService
from app.models.enums import AccountStatus, Language, ServiceType, UserRole
from app.models.geography import Municipality, Ward
from app.models.profile import Profile
from app.seeds import (
    CATEGORY_SEEDS,
    LOCATED_SERVICES,
    MUNICIPALITY_SEEDS,
    NATIONAL_HOTLINES,
    build_wards,
)

DEMO_PASSWORD = "Sahayatri@2025"

DEMO_ACCOUNTS: list[dict] = [
    {
        "email": "admin@sahayatri.np",
        "full_name": "System Administrator",
        "role": UserRole.ADMIN,
        "municipality_code": None,
        "ward_number": None,
    },
    {
        "email": "kmc.city@sahayatri.np",
        "full_name": "KMC City Desk",
        "role": UserRole.AUTHORITY,
        "municipality_code": "KMC",
        "ward_number": None,  # municipality-wide: sees every KMC ward
    },
    {
        "email": "kmc.ward5@sahayatri.np",
        "full_name": "KMC Ward 5 Office",
        "role": UserRole.AUTHORITY,
        "municipality_code": "KMC",
        "ward_number": 5,
    },
    {
        "email": "kmc.ward10@sahayatri.np",
        "full_name": "KMC Ward 10 Office",
        "role": UserRole.AUTHORITY,
        "municipality_code": "KMC",
        "ward_number": 10,
    },
    {
        "email": "lmc.ward4@sahayatri.np",
        "full_name": "Lalitpur Ward 4 Office",
        "role": UserRole.AUTHORITY,
        "municipality_code": "LMC",
        "ward_number": 4,
    },
    {
        "email": "pending.authority@sahayatri.np",
        "full_name": "Bhaktapur Ward 1 Office",
        "role": UserRole.AUTHORITY,
        "municipality_code": "BKT",
        "ward_number": 1,
        "account_status": AccountStatus.PENDING,  # demonstrates the approval queue
    },
    {
        "email": "sita@example.com",
        "full_name": "Sita Sharma",
        "role": UserRole.CITIZEN,
        "municipality_code": "KMC",
        "ward_number": 5,
        "preferred_language": Language.NE,
    },
    {
        "email": "ram@example.com",
        "full_name": "Ram Bahadur Thapa",
        "role": UserRole.CITIZEN,
        "municipality_code": "KMC",
        "ward_number": 5,
    },
    {
        "email": "gita@example.com",
        "full_name": "Gita Maharjan",
        "role": UserRole.CITIZEN,
        "municipality_code": "KMC",
        "ward_number": 10,
        "preferred_language": Language.NE,
    },
    {
        "email": "hari@example.com",
        "full_name": "Hari Prasad Adhikari",
        "role": UserRole.CITIZEN,
        "municipality_code": "LMC",
        "ward_number": 4,
    },
]


def seed_categories(db: Session) -> dict[str, Category]:
    existing = {c.key: c for c in db.scalars(select(Category))}

    for payload in CATEGORY_SEEDS:
        category = existing.get(payload["key"])
        if category is None:
            category = Category(**payload)
            db.add(category)
            existing[payload["key"]] = category
        else:
            for field, value in payload.items():
                setattr(category, field, value)

    db.flush()
    print(f"  categories        {len(existing):>4}")
    return existing


def seed_geography(db: Session) -> tuple[dict[str, Municipality], dict[tuple, Ward]]:
    municipalities = {m.code: m for m in db.scalars(select(Municipality))}
    wards: dict[tuple, Ward] = {
        (w.municipality_id, w.number): w for w in db.scalars(select(Ward))
    }

    ward_total = 0
    for payload in MUNICIPALITY_SEEDS:
        code = payload["code"]
        fields = {
            "code": code,
            "name_en": payload["name_en"],
            "name_ne": payload["name_ne"],
            "district": payload["district"],
            "province": payload["province"],
            "type": payload["type"],
        }

        municipality = municipalities.get(code)
        if municipality is None:
            municipality = Municipality(**fields)
            db.add(municipality)
            db.flush()
            municipalities[code] = municipality
        else:
            for field, value in fields.items():
                setattr(municipality, field, value)

        for ward_payload in build_wards(payload):
            key = (municipality.id, ward_payload["number"])
            ward = wards.get(key)
            if ward is None:
                ward = Ward(municipality_id=municipality.id, **ward_payload)
                db.add(ward)
                wards[key] = ward
            else:
                for field, value in ward_payload.items():
                    setattr(ward, field, value)
            ward_total += 1

    db.flush()
    print(f"  municipalities    {len(municipalities):>4}")
    print(f"  wards             {ward_total:>4}")
    return municipalities, wards


def _nearest_ward(wards: list[Ward], lat: float, lon: float) -> Ward | None:
    """Attach a located service to whichever ward centroid is closest."""
    if not wards:
        return None
    return min(
        wards,
        key=lambda w: haversine_m(lat, lon, w.centroid_lat, w.centroid_lon),
    )


def seed_services(db: Session, municipalities: dict[str, Municipality]) -> None:
    existing = {
        (s.name_en, s.service_type): s for s in db.scalars(select(CivicService))
    }
    count = 0

    for payload in NATIONAL_HOTLINES:
        fields = dict(payload)
        fields["service_type"] = ServiceType(fields["service_type"])
        key = (fields["name_en"], fields["service_type"])

        service = existing.get(key)
        if service is None:
            db.add(CivicService(**fields))
        else:
            for field, value in fields.items():
                setattr(service, field, value)
        count += 1

    for payload in LOCATED_SERVICES:
        fields = dict(payload)
        code = fields.pop("municipality_code", None)
        fields["service_type"] = ServiceType(fields["service_type"])

        municipality = municipalities.get(code) if code else None
        if municipality is not None:
            fields["municipality_id"] = municipality.id
            ward = _nearest_ward(
                list(municipality.wards), fields["latitude"], fields["longitude"]
            )
            if ward is not None:
                fields["ward_id"] = ward.id

        key = (fields["name_en"], fields["service_type"])
        service = existing.get(key)
        if service is None:
            db.add(CivicService(**fields))
        else:
            for field, value in fields.items():
                setattr(service, field, value)
        count += 1

    db.flush()
    print(f"  civic services    {count:>4}")


def _ensure_auth_user(email: str, full_name: str) -> UUID:
    """Create the Supabase auth user, or find it if it already exists."""
    supabase = get_supabase()

    try:
        result = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": DEMO_PASSWORD,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            }
        )
        if result.user is not None:
            return UUID(str(result.user.id))
    except Exception as exc:
        message = (getattr(exc, "message", None) or str(exc)).lower()
        if "already" not in message and "registered" not in message:
            raise

    # Already present -- page through the user list to recover the id.
    page = 1
    while page <= 20:
        users = supabase.auth.admin.list_users(page=page, per_page=100)
        if not users:
            break
        for user in users:
            if (user.email or "").lower() == email.lower():
                return UUID(str(user.id))
        page += 1

    raise RuntimeError(f"Could not create or find the auth user for {email}.")


def seed_accounts(
    db: Session,
    municipalities: dict[str, Municipality],
    wards: dict[tuple, Ward],
) -> None:
    created = 0

    for spec in DEMO_ACCOUNTS:
        municipality = municipalities.get(spec["municipality_code"] or "")
        ward = None
        if municipality is not None and spec["ward_number"] is not None:
            ward = wards.get((municipality.id, spec["ward_number"]))

        user_id = _ensure_auth_user(spec["email"], spec["full_name"])

        profile = db.get(Profile, user_id)
        fields = {
            "email": spec["email"],
            "full_name": spec["full_name"],
            "role": spec["role"],
            "account_status": spec.get("account_status", AccountStatus.ACTIVE),
            "municipality_id": municipality.id if municipality else None,
            "ward_id": ward.id if ward else None,
            "preferred_language": spec.get("preferred_language", Language.EN),
        }

        if profile is None:
            db.add(Profile(id=user_id, **fields))
            created += 1
        else:
            for field, value in fields.items():
                setattr(profile, field, value)

    db.flush()
    print(f"  demo accounts     {len(DEMO_ACCOUNTS):>4}  ({created} new)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed reference and demo data.")
    parser.add_argument(
        "--skip-accounts",
        action="store_true",
        help="Seed reference data only, leaving Supabase Auth untouched.",
    )
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        print("Seeding:")
        seed_categories(session)
        municipalities, wards = seed_geography(session)
        seed_services(session, municipalities)

        if args.skip_accounts:
            print("  demo accounts     skipped")
        else:
            seed_accounts(session, municipalities, wards)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if not args.skip_accounts:
        print(f"\nAll demo accounts use the password: {DEMO_PASSWORD}")
        print("  admin@sahayatri.np          admin")
        print("  kmc.city@sahayatri.np       authority, all KMC wards")
        print("  kmc.ward5@sahayatri.np      authority, KMC ward 5 only")
        print("  sita@example.com            citizen, KMC ward 5")

    return 0


if __name__ == "__main__":
    sys.exit(main())
