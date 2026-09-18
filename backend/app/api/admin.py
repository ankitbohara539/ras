from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.models.enums import AccountStatus, NotificationType, UserRole
from app.models.geography import Ward
from app.models.notification import Notification
from app.models.profile import Profile
from app.schema.admin import (
    AdminProfileUpdateRequest,
    ApprovalRequest,
    ProfileListResponse,
    RejectionRequest,
)
from app.schema.auth import ProfileResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


def _load_profile(db: Session, profile_id: UUID) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such profile.",
        )
    return profile


def _resolve_scope(
    db: Session, municipality_id: UUID | None, ward_id: UUID | None
) -> tuple[UUID | None, UUID | None]:
    """A ward implies its municipality, so callers need only send the ward."""
    if ward_id is None:
        return municipality_id, None

    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown ward.",
        )
    return ward.municipality_id, ward.id


@router.get("/profiles", response_model=ProfileListResponse)
def list_profiles(
    role: UserRole | None = None,
    account_status: AccountStatus | None = None,
    municipality_id: UUID | None = None,
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProfileListResponse:
    filters = []
    if role is not None:
        filters.append(Profile.role == role)
    if account_status is not None:
        filters.append(Profile.account_status == account_status)
    if municipality_id is not None:
        filters.append(Profile.municipality_id == municipality_id)
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(Profile.email).like(pattern)
            | func.lower(func.coalesce(Profile.full_name, "")).like(pattern)
        )

    total = db.scalar(select(func.count()).select_from(Profile).where(*filters)) or 0
    rows = db.scalars(
        select(Profile)
        .where(*filters)
        .order_by(Profile.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return ProfileListResponse(
        items=[ProfileResponse.model_validate(p) for p in rows],
        total=total,
    )


@router.get("/profiles/pending", response_model=ProfileListResponse)
def list_pending_authorities(
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProfileListResponse:
    """The approval queue: authority signups waiting on an admin."""
    rows = db.scalars(
        select(Profile)
        .where(
            Profile.role == UserRole.AUTHORITY,
            Profile.account_status == AccountStatus.PENDING,
        )
        .order_by(Profile.created_at.asc())
    ).all()

    return ProfileListResponse(
        items=[ProfileResponse.model_validate(p) for p in rows],
        total=len(rows),
    )


@router.post("/profiles/{profile_id}/approve", response_model=ProfileResponse)
def approve_authority(
    profile_id: UUID,
    data: ApprovalRequest,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = _load_profile(db, profile_id)

    if profile.account_status is AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already active.",
        )

    if data.municipality_id is not None or data.ward_id is not None:
        municipality_id, ward_id = _resolve_scope(
            db, data.municipality_id, data.ward_id
        )
        profile.municipality_id = municipality_id
        profile.ward_id = ward_id

    if profile.role is UserRole.AUTHORITY and profile.municipality_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An authority account must be scoped to a municipality.",
        )

    profile.account_status = AccountStatus.ACTIVE
    profile.approved_by_id = admin.id

    db.add(
        Notification(
            user_id=profile.id,
            type=NotificationType.ACCOUNT_APPROVED,
            title_en="Your authority account is approved",
            title_ne="तपाईंको प्राधिकरण खाता स्वीकृत भयो",
            body_en=data.note or "You can now sign in and manage reports.",
        )
    )
    db.flush()

    return ProfileResponse.model_validate(profile)


@router.post("/profiles/{profile_id}/reject", response_model=ProfileResponse)
def reject_authority(
    profile_id: UUID,
    data: RejectionRequest,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = _load_profile(db, profile_id)

    profile.account_status = AccountStatus.REJECTED
    profile.approved_by_id = admin.id

    db.add(
        Notification(
            user_id=profile.id,
            type=NotificationType.ACCOUNT_APPROVED,
            title_en="Your authority account was not approved",
            title_ne="तपाईंको प्राधिकरण खाता स्वीकृत भएन",
            body_en=data.reason,
        )
    )
    db.flush()

    return ProfileResponse.model_validate(profile)


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: UUID,
    data: AdminProfileUpdateRequest,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = _load_profile(db, profile_id)

    if profile.id == admin.id and data.role is not None and data.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot remove your own administrator role.",
        )

    payload = data.model_dump(exclude_unset=True)

    if "ward_id" in payload or "municipality_id" in payload:
        municipality_id, ward_id = _resolve_scope(
            db,
            payload.get("municipality_id", profile.municipality_id),
            payload.get("ward_id"),
        )
        profile.municipality_id = municipality_id
        profile.ward_id = ward_id
        payload.pop("municipality_id", None)
        payload.pop("ward_id", None)

    for field, value in payload.items():
        setattr(profile, field, value)

    db.flush()
    return ProfileResponse.model_validate(profile)
