"""Seed 100 deterministic Kathmandu demo records across role workflows.

Primary records: 45 issues, 20 civic services, 10 alerts, 15 SOS cases,
and 10 notifications. Related history, assignment, and recipient rows are
created as needed. The script is idempotent and development/test only.
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.shared.infrastructure.geo import mysql_point
from app.shared.infrastructure.models import (
    AdministrativeArea,
    CivicService,
    CivicServiceCategory,
    EmergencyAlert,
    EmergencySOS,
    EmergencySOSStatusHistory,
    EmergencyStatus,
    Issue,
    IssueAssignment,
    IssueCategory,
    IssueStatus,
    IssueStatusHistory,
    Notification,
    NotificationRecipient,
    User,
    utcnow,
)


DEMO_EMAILS = {
    "admin": "admin@demo.civicgrid.dev",
    "authority": "authority@demo.civicgrid.dev",
    "responder": "responder@demo.civicgrid.dev",
    "citizen": "citizen@demo.civicgrid.dev",
}

ISSUE_TITLES = (
    "Pothole affecting two-wheelers",
    "Uncollected roadside waste",
    "Street light not working",
    "Blocked roadside drain",
    "Damaged pedestrian footpath",
    "Water leakage near junction",
    "Unsafe exposed utility cable",
    "Road surface requires repair",
    "Accessibility ramp obstructed",
    "Public space needs maintenance",
)

SERVICE_NAMES = (
    "Ward Citizen Help Desk",
    "Community Health Support Point",
    "Municipal Service Counter",
    "Emergency Coordination Desk",
    "Public Safety Contact Point",
)


def demo_id(kind: str, number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"civicgrid-kathmandu-demo:{kind}:{number}"))


def ward_point(number: int, offset: int = 0) -> tuple[float, float]:
    """Return deterministic test coordinates within the Kathmandu map extent."""
    column = (number - 1) % 8
    row = (number - 1) // 8
    latitude = 27.674 + row * 0.018 + (offset % 3) * 0.0014
    longitude = 85.278 + column * 0.0135 + (offset % 2) * 0.0012
    return latitude, longitude


async def seed_demo_data() -> None:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise RuntimeError("Demo data cannot be seeded outside development or test.")

    created = {"issues": 0, "services": 0, "alerts": 0, "emergencies": 0, "notifications": 0}
    now = utcnow()

    async with AsyncSessionFactory() as db:
        users: dict[str, User] = {}
        for key, email in DEMO_EMAILS.items():
            user = await db.scalar(select(User).where(User.email_normalized == email))
            if user is None:
                raise RuntimeError(
                    f"Missing {email}. Run scripts/seed_development_users.py first."
                )
            users[key] = user

        wards = list(
            (
                await db.scalars(
                    select(AdministrativeArea)
                    .where(AdministrativeArea.code.like("KMC-WARD-%"))
                    .order_by(AdministrativeArea.code)
                )
            ).all()
        )
        issue_categories = list((await db.scalars(select(IssueCategory).order_by(IssueCategory.code))).all())
        service_categories = list(
            (await db.scalars(select(CivicServiceCategory).order_by(CivicServiceCategory.code))).all()
        )
        if len(wards) != 32 or not issue_categories or not service_categories:
            raise RuntimeError("Run alembic upgrade head before seeding demo data.")

        issue_statuses = (
            IssueStatus.REPORTED,
            IssueStatus.VERIFIED,
            IssueStatus.ASSIGNED,
            IssueStatus.IN_PROGRESS,
            IssueStatus.RESOLVED,
            IssueStatus.REJECTED,
            IssueStatus.DUPLICATE,
        )
        severities = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        for index in range(1, 46):
            record_id = demo_id("issue", index)
            if await db.get(Issue, record_id) is not None:
                continue
            ward = wards[(index - 1) % len(wards)]
            latitude, longitude = ward_point(index, index)
            status = issue_statuses[(index - 1) % len(issue_statuses)]
            created_at = now - timedelta(hours=index * 3)
            issue = Issue(
                id=record_id,
                reporter_id=users["citizen"].id,
                category_id=issue_categories[(index - 1) % len(issue_categories)].id,
                administrative_area_id=ward.id,
                title=f"{ISSUE_TITLES[(index - 1) % len(ISSUE_TITLES)]} · Ward {index % 32 or 32}",
                description="Kathmandu demonstration report with a ward, landmark context, severity, and workflow state for role-based testing.",
                status=status,
                severity=severities[(index - 1) % len(severities)],
                location=mysql_point(longitude, latitude),
                address_text=f"Near a public landmark, {ward.name}",
                anonymous_public_display=index % 6 == 0,
                client_request_id=demo_id("issue-request", index),
                version=1 + (index % 4),
                created_at=created_at,
                updated_at=created_at + timedelta(hours=index % 8),
                resolved_at=created_at + timedelta(hours=18) if status == IssueStatus.RESOLVED else None,
            )
            db.add(issue)
            db.add(
                IssueStatusHistory(
                    id=demo_id("issue-history", index),
                    issue_id=record_id,
                    from_status=None,
                    to_status=status,
                    changed_by=users["authority"].id if status != IssueStatus.REPORTED else users["citizen"].id,
                    note="Deterministic Kathmandu demo workflow record.",
                    created_at=created_at,
                )
            )
            if status in {IssueStatus.ASSIGNED, IssueStatus.IN_PROGRESS, IssueStatus.RESOLVED}:
                db.add(
                    IssueAssignment(
                        id=demo_id("issue-assignment", index),
                        issue_id=record_id,
                        assigned_to=users["authority"].id,
                        assigned_by=users["authority"].id,
                        assigned_at=created_at + timedelta(hours=2),
                        completed_at=created_at + timedelta(hours=18) if status == IssueStatus.RESOLVED else None,
                    )
                )
            created["issues"] += 1

        for index in range(1, 21):
            record_id = demo_id("service", index)
            if await db.get(CivicService, record_id) is not None:
                continue
            ward = wards[(index * 3 - 1) % len(wards)]
            latitude, longitude = ward_point(index * 3, index)
            category = service_categories[(index - 1) % len(service_categories)]
            db.add(
                CivicService(
                    id=record_id,
                    category_id=category.id,
                    administrative_area_id=ward.id,
                    name=f"{SERVICE_NAMES[(index - 1) % len(SERVICE_NAMES)]} {index:02d}",
                    description=f"Verified demonstration listing for {category.name} services in Kathmandu Metropolitan City.",
                    phone=f"01-55{index:04d}",
                    email=f"service{index:02d}@demo.civicgrid.dev",
                    address=f"Municipal service location, {ward.name}",
                    location=mysql_point(longitude, latitude),
                    opening_hours={"sun-fri": "10:00-17:00", "sat": "closed"},
                    emergency_service=index % 5 == 0,
                    active=True,
                )
            )
            created["services"] += 1

        for index in range(1, 11):
            record_id = demo_id("alert", index)
            if await db.get(EmergencyAlert, record_id) is not None:
                continue
            ward = wards[(index * 2 - 1) % len(wards)]
            active = index <= 7
            starts_at = now - timedelta(hours=index * 2)
            db.add(
                EmergencyAlert(
                    id=record_id,
                    title=f"Ward {index * 2:02d} municipal notice",
                    message="Demonstration alert for road access, weather readiness, public works, or local service coordination.",
                    severity=("INFO", "ADVISORY", "WARNING", "CRITICAL")[(index - 1) % 4],
                    administrative_area_id=ward.id,
                    created_by=users["authority"].id,
                    starts_at=starts_at,
                    expires_at=now + timedelta(hours=24 + index) if active else now - timedelta(hours=1),
                    active=active,
                    created_at=starts_at,
                    updated_at=starts_at,
                )
            )
            created["alerts"] += 1

        emergency_statuses = (
            EmergencyStatus.CREATED,
            EmergencyStatus.ACKNOWLEDGED,
            EmergencyStatus.DISPATCHED,
            EmergencyStatus.ON_SCENE,
            EmergencyStatus.RESOLVED,
            EmergencyStatus.CANCELLED,
        )
        emergency_types = ("MEDICAL", "FIRE", "SAFETY", "DISASTER", "OTHER")
        for index in range(1, 16):
            record_id = demo_id("emergency", index)
            if await db.get(EmergencySOS, record_id) is not None:
                continue
            ward = wards[(index * 5 - 1) % len(wards)]
            latitude, longitude = ward_point(index * 5, index)
            status = emergency_statuses[(index - 1) % len(emergency_statuses)]
            created_at = now - timedelta(minutes=index * 17)
            assigned = status not in {EmergencyStatus.CREATED, EmergencyStatus.CANCELLED}
            db.add(
                EmergencySOS(
                    id=record_id,
                    user_id=users["citizen"].id,
                    emergency_type=emergency_types[(index - 1) % len(emergency_types)],
                    status=status,
                    location=mysql_point(longitude, latitude),
                    address_text=f"Emergency demo location, {ward.name}",
                    message="Role-workflow demonstration SOS; not a real emergency.",
                    assigned_responder_id=users["responder"].id if assigned else None,
                    acknowledged_at=created_at + timedelta(minutes=3) if assigned else None,
                    resolved_at=created_at + timedelta(minutes=35) if status == EmergencyStatus.RESOLVED else None,
                    version=1 + (index % 4),
                    created_at=created_at,
                    updated_at=created_at + timedelta(minutes=5),
                )
            )
            db.add(
                EmergencySOSStatusHistory(
                    id=demo_id("emergency-history", index),
                    emergency_id=record_id,
                    from_status=None,
                    to_status=status,
                    changed_by=users["responder"].id if assigned else users["citizen"].id,
                    created_at=created_at,
                )
            )
            created["emergencies"] += 1

        for index in range(1, 11):
            record_id = demo_id("notification", index)
            if await db.get(Notification, record_id) is not None:
                continue
            created_at = now - timedelta(minutes=index * 23)
            db.add(
                Notification(
                    id=record_id,
                    event_type=("issue.updated", "alert.published", "emergency.updated")[index % 3],
                    title=f"Kathmandu operations update {index:02d}",
                    body="A demonstration notification showing persisted, role-aware municipal activity.",
                    payload={"demo": True, "ward": (index * 3) % 32 or 32},
                    created_at=created_at,
                )
            )
            for user in users.values():
                db.add(
                    NotificationRecipient(
                        notification_id=record_id,
                        user_id=user.id,
                        read_at=created_at + timedelta(minutes=5) if index % 3 == 0 else None,
                    )
                )
            created["notifications"] += 1

        await db.commit()

    print("Kathmandu demo dataset is ready (100 primary records):")
    print("  45 issues | 20 civic services | 10 alerts | 15 SOS cases | 10 notifications")
    print("Created this run: " + ", ".join(f"{name}={count}" for name, count in created.items()))


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
