"""Civic-sense complaints: filing, visibility and the office's decision.

See app.models.civic for why these are kept apart from tickets. The rules
this module enforces:

  - Only the reporter, the ward office where it happened (or its
    municipality-wide office) and admins can see a complaint. Never other
    citizens: the photo shows a real person.
  - Every complaint needs a photo. An accusation with no evidence is not
    something an office can act on.
  - A citizen can file only a few a day, which blunts using this to harass
    a neighbour.
  - Closing one -- action taken or dismissed -- needs a note, because the
    reporter is told what happened and "dismissed" alone tells them nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.civic import CivicComplaint, CivicComplaintPhoto
from app.models.enums import CivicStatus, NotificationType, UserRole
from app.models.geography import Ward
from app.models.notification import Notification
from app.models.profile import Profile
from app.services.ticket_service import resolve_ward

MAX_PER_DAY = 10
MAX_PHOTOS = 3

# Where each status may go next. A closed complaint can be reopened.
TRANSITIONS: dict[CivicStatus, set[CivicStatus]] = {
    CivicStatus.SUBMITTED: {
        CivicStatus.UNDER_REVIEW,
        CivicStatus.ACTION_TAKEN,
        CivicStatus.DISMISSED,
    },
    CivicStatus.UNDER_REVIEW: {CivicStatus.ACTION_TAKEN, CivicStatus.DISMISSED},
    CivicStatus.ACTION_TAKEN: {CivicStatus.UNDER_REVIEW},
    CivicStatus.DISMISSED: {CivicStatus.UNDER_REVIEW},
}
NEEDS_NOTE = {CivicStatus.ACTION_TAKEN, CivicStatus.DISMISSED}

STATUS_TEXT = {
    CivicStatus.SUBMITTED: ("received", "प्राप्त भयो"),
    CivicStatus.UNDER_REVIEW: ("being reviewed", "समीक्षा हुँदैछ"),
    CivicStatus.ACTION_TAKEN: ("acted on", "कारबाही भयो"),
    CivicStatus.DISMISSED: ("closed without action", "कारबाहीबिना बन्द भयो"),
}


def _now() -> datetime:
    return datetime.now(UTC)


def scope_filters(profile: Profile) -> list:
    """WHERE clauses limiting a complaint query to what `profile` may see."""
    if profile.role is UserRole.ADMIN:
        return []
    if profile.role is UserRole.AUTHORITY:
        if profile.ward_id is not None:
            return [CivicComplaint.ward_id == profile.ward_id]
        if profile.municipality_id is not None:
            return [CivicComplaint.municipality_id == profile.municipality_id]
        return [CivicComplaint.id.is_(None)]  # unscoped authority sees nothing
    return [CivicComplaint.reporter_id == profile.id]


def can_manage(profile: Profile, complaint: CivicComplaint) -> bool:
    """Whether this profile is the office responsible for the complaint."""
    if profile.role is UserRole.ADMIN:
        return True
    if profile.role is UserRole.AUTHORITY:
        if profile.ward_id is not None:
            return complaint.ward_id == profile.ward_id
        if profile.municipality_id is not None:
            return complaint.municipality_id == profile.municipality_id
    return False


def can_view(profile: Profile, complaint: CivicComplaint) -> bool:
    return complaint.reporter_id == profile.id or can_manage(profile, complaint)


def get_visible(db: Session, profile: Profile, complaint_id: UUID) -> CivicComplaint:
    complaint = db.get(CivicComplaint, complaint_id)
    # 404 rather than 403 for someone else's: do not confirm it exists.
    if complaint is None or not can_view(profile, complaint):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such complaint.")
    return complaint


def _public_code(db: Session, ward: Ward) -> str:
    municipality_code = ward.municipality.code if ward.municipality else "GEN"
    used = (
        db.scalar(
            select(func.count())
            .select_from(CivicComplaint)
            .where(CivicComplaint.ward_id == ward.id)
        )
        or 0
    )
    for offset in range(1, 200):
        code = f"CIV-{municipality_code}-{ward.number:02d}-{used + offset:06d}"
        if db.scalar(select(CivicComplaint.id).where(CivicComplaint.public_code == code)) is None:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate a complaint code.",
    )


def check_can_file(db: Session, reporter: Profile) -> None:
    if reporter.role is not UserRole.CITIZEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only citizen accounts file civic complaints.",
        )
    recent = (
        db.scalar(
            select(func.count())
            .select_from(CivicComplaint)
            .where(
                CivicComplaint.reporter_id == reporter.id,
                CivicComplaint.created_at >= _now() - timedelta(days=1),
            )
        )
        or 0
    )
    if recent >= MAX_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You can file at most {MAX_PER_DAY} civic complaints a day.",
        )


def create_complaint(
    db: Session,
    reporter: Profile,
    *,
    category,
    description: str,
    latitude: float,
    longitude: float,
    address_text: str | None,
    occurred_at: datetime | None,
    photo_paths: list[str],
) -> CivicComplaint:
    """File a complaint. Photos are uploaded by the caller first."""
    if not photo_paths:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add at least one photo of what happened.",
        )

    now = _now()
    when = occurred_at or now
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    if when > now + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The time it happened cannot be in the future.",
        )

    ward = resolve_ward(db, latitude, longitude)
    complaint = CivicComplaint(
        public_code=_public_code(db, ward),
        reporter_id=reporter.id,
        category=category,
        description=description,
        latitude=latitude,
        longitude=longitude,
        address_text=address_text,
        ward_id=ward.id,
        municipality_id=ward.municipality_id,
        occurred_at=when,
        status=CivicStatus.SUBMITTED,
    )
    db.add(complaint)
    db.flush()

    for path in photo_paths:
        db.add(CivicComplaintPhoto(complaint_id=complaint.id, storage_path=path))
    db.flush()
    db.refresh(complaint)
    return complaint


def update_status(
    db: Session,
    officer: Profile,
    complaint: CivicComplaint,
    new_status: CivicStatus,
    note: str | None,
) -> CivicComplaint:
    if not can_manage(officer, complaint):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This complaint belongs to another ward.",
        )

    allowed = TRANSITIONS.get(complaint.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move from {complaint.status.value} to {new_status.value}. "
                f"Allowed: {', '.join(sorted(s.value for s in allowed)) or 'none'}."
            ),
        )

    note = (note or "").strip() or None
    if new_status in NEEDS_NOTE and not note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Say what was done (or why no action was taken). The reporter sees this.",
        )

    complaint.status = new_status
    if note:
        complaint.action_note = note
    complaint.reviewed_by_id = officer.id
    complaint.reviewed_at = _now()

    text_en, text_ne = STATUS_TEXT[new_status]
    db.add(
        Notification(
            user_id=complaint.reporter_id,
            type=NotificationType.CIVIC_COMPLAINT_UPDATED,
            title_en=f"Your civic complaint {complaint.public_code} was {text_en}",
            title_ne=f"तपाईंको नागरिक उजुरी {complaint.public_code} {text_ne}",
            body_en=note,
        )
    )
    db.flush()
    return complaint
