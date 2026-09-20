from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.core.cache import cache
from app.db.session import get_db
from app.models.enums import AccountStatus, NotificationType, UserRole
from app.models.geography import Municipality, Ward
from app.models.civic import CivicComplaint
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.models.profile import Profile
from app.schema.admin import (
    AdminProfileUpdateRequest,
    AdminContentItem,
    AdminProfileDetailResponse,
    ApprovalRequest,
    EscalationSweepResponse,
    ProfileListResponse,
    RejectionRequest,
    WardCreateRequest,
    WardDetailResponse,
    WardManagementResponse,
    WardUpdateRequest,
)
from app.schema.auth import ProfileResponse
from app.services import ticket_service
from app.services.auth_service import delete_auth_user, update_auth_email
from app.services.storage_service import signed_url, signed_urls

router = APIRouter(prefix="/admin", tags=["Admin"])


def _load_profile(db: Session, profile_id: UUID) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such profile.",
        )
    return profile


def _profile_response(profile: Profile) -> ProfileResponse:
    """Expose a signed avatar URL only inside an authorized admin response."""
    response = ProfileResponse.model_validate(profile)
    return response.model_copy(
        update={
            "avatar_url": signed_url(profile.avatar_path)
            if profile.avatar_path
            else None
        }
    )


def _profile_responses(profiles: list[Profile]) -> list[ProfileResponse]:
    """Sign one page of private avatars in a single storage request."""
    paths = [profile.avatar_path for profile in profiles if profile.avatar_path]
    urls = signed_urls(paths) if paths else {}
    return [
        ProfileResponse.model_validate(profile).model_copy(
            update={
                "avatar_url": urls.get(profile.avatar_path)
                if profile.avatar_path
                else None
            }
        )
        for profile in profiles
    ]


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
    ward_id: UUID | None = None,
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
    if ward_id is not None:
        filters.append(Profile.ward_id == ward_id)
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(Profile.email).like(pattern)
            | func.lower(func.coalesce(Profile.full_name, "")).like(pattern)
            | func.lower(func.coalesce(Ward.name_en, "")).like(pattern)
            | func.cast(Ward.number, String).like(pattern)
        )

    base = select(Profile).outerjoin(Ward, Profile.ward_id == Ward.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(Profile).outerjoin(Ward, Profile.ward_id == Ward.id).where(*filters)) or 0
    rows = db.scalars(
        base
        .order_by(Profile.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return ProfileListResponse(
        items=_profile_responses(list(rows)),
        total=total,
    )


@router.get("/profiles/{profile_id}/detail", response_model=AdminProfileDetailResponse)
def get_profile_detail(
    profile_id: UUID,
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminProfileDetailResponse:
    profile = _load_profile(db, profile_id)
    reports = db.scalars(
        select(Ticket).where(Ticket.reporter_id == profile.id).order_by(Ticket.created_at.desc()).limit(100)
    ).all()
    civic = db.scalars(
        select(CivicComplaint).where(CivicComplaint.reporter_id == profile.id).order_by(CivicComplaint.created_at.desc()).limit(100)
    ).all()
    return AdminProfileDetailResponse(
        profile=_profile_response(profile),
        reports=[
            AdminContentItem(
                id=item.id, code=item.public_code, kind="report", title=item.title,
                description=item.description, ward_id=item.ward_id,
                status=item.status.value, created_at=item.created_at,
            )
            for item in reports
        ],
        civic_complaints=[
            AdminContentItem(
                id=item.id, code=item.public_code, kind="civic", title=None,
                description=item.description, ward_id=item.ward_id,
                status=item.status.value, created_at=item.created_at,
            )
            for item in civic
        ],
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
        items=_profile_responses(list(rows)),
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

    return _profile_response(profile)


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

    return _profile_response(profile)


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

    if "email" in payload:
        email = str(payload.pop("email"))
        if email != profile.email:
            other = db.scalar(select(Profile.id).where(Profile.email == email, Profile.id != profile.id))
            if other is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
            update_auth_email(profile.id, email)
            profile.email = email

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
    return _profile_response(profile)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: UUID,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    profile = _load_profile(db, profile_id)
    if profile.id == admin.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot delete your own administrator account.")
    # Auth is removed first so no credential survives a deleted application
    # profile. The transaction rolls the data side back on any DB failure.
    delete_auth_user(profile.id)
    db.delete(profile)
    db.flush()


def _ward_response(
    ward: Ward,
    civilian_count: int = 0,
    authority_count: int = 0,
    report_count: int = 0,
) -> WardManagementResponse:
    return WardManagementResponse(
        id=ward.id,
        municipality_id=ward.municipality_id,
        number=ward.number,
        name_en=ward.name_en,
        name_ne=ward.name_ne,
        centroid_lat=ward.centroid_lat,
        centroid_lon=ward.centroid_lon,
        civilian_count=civilian_count,
        authority_count=authority_count,
        report_count=report_count,
    )


@router.get("/wards", response_model=list[WardManagementResponse])
def list_wards(
    municipality_id: UUID | None = None,
    search: str | None = Query(default=None, max_length=120),
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[WardManagementResponse]:
    filters = []
    if municipality_id is not None:
        filters.append(Ward.municipality_id == municipality_id)
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(func.coalesce(Ward.name_en, "")).like(pattern)
            | func.lower(func.coalesce(Ward.name_ne, "")).like(pattern)
            | func.cast(Ward.number, String).like(pattern)
        )
    wards = db.scalars(select(Ward).where(*filters).order_by(Ward.municipality_id, Ward.number)).all()
    ids = [ward.id for ward in wards]
    civilians = {
        ward_id: count
        for ward_id, count in db.execute(
            select(Profile.ward_id, func.count()).where(Profile.ward_id.in_(ids), Profile.role == UserRole.CITIZEN).group_by(Profile.ward_id)
        ).all()
    } if ids else {}
    authorities = {
        ward_id: count
        for ward_id, count in db.execute(
            select(Profile.ward_id, func.count()).where(Profile.ward_id.in_(ids), Profile.role == UserRole.AUTHORITY).group_by(Profile.ward_id)
        ).all()
    } if ids else {}
    reports = {
        ward_id: count
        for ward_id, count in db.execute(
            select(Ticket.ward_id, func.count()).where(Ticket.ward_id.in_(ids)).group_by(Ticket.ward_id)
        ).all()
    } if ids else {}
    return [_ward_response(ward, civilians.get(ward.id, 0), authorities.get(ward.id, 0), reports.get(ward.id, 0)) for ward in wards]


@router.get("/wards/{ward_id}", response_model=WardDetailResponse)
def get_ward(
    ward_id: UUID,
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WardDetailResponse:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such ward.")
    civilians = db.scalars(
        select(Profile).where(Profile.ward_id == ward.id, Profile.role == UserRole.CITIZEN).order_by(Profile.full_name)
    ).all()
    base = _ward_response(
        ward,
        civilian_count=len(civilians),
        authority_count=db.scalar(select(func.count()).select_from(Profile).where(Profile.ward_id == ward.id, Profile.role == UserRole.AUTHORITY)) or 0,
        report_count=db.scalar(select(func.count()).select_from(Ticket).where(Ticket.ward_id == ward.id)) or 0,
    )
    return WardDetailResponse(
        **base.model_dump(),
        civilians=_profile_responses(list(civilians)),
    )


@router.post("/wards", response_model=WardManagementResponse, status_code=status.HTTP_201_CREATED)
def create_ward(
    data: WardCreateRequest,
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WardManagementResponse:
    if db.get(Municipality, data.municipality_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown municipality.")
    if db.scalar(select(Ward.id).where(Ward.municipality_id == data.municipality_id, Ward.number == data.number)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That municipality already has this ward number.")
    ward = Ward(**data.model_dump())
    db.add(ward)
    db.flush()
    cache.invalidate("ref:")
    return _ward_response(ward)


@router.patch("/wards/{ward_id}", response_model=WardManagementResponse)
def update_ward(
    ward_id: UUID,
    data: WardUpdateRequest,
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WardManagementResponse:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such ward.")
    payload = data.model_dump(exclude_unset=True)
    if "number" in payload and db.scalar(
        select(Ward.id).where(
            Ward.municipality_id == ward.municipality_id,
            Ward.number == payload["number"],
            Ward.id != ward.id,
        )
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That municipality already has this ward number.")
    for field, value in payload.items():
        setattr(ward, field, value)
    db.flush()
    cache.invalidate("ref:")
    return _ward_response(ward)


@router.delete("/wards/{ward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ward(
    ward_id: UUID,
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    ward = db.get(Ward, ward_id)
    if ward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such ward.")
    has_profiles = db.scalar(select(func.count()).select_from(Profile).where(Profile.ward_id == ward.id)) or 0
    has_tickets = db.scalar(select(func.count()).select_from(Ticket).where(Ticket.ward_id == ward.id)) or 0
    has_civic = db.scalar(select(func.count()).select_from(CivicComplaint).where(CivicComplaint.ward_id == ward.id)) or 0
    if has_profiles or has_tickets or has_civic:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Move the ward's users and content before deleting it.",
        )
    db.delete(ward)
    db.flush()
    cache.invalidate("ref:")


@router.post("/escalations/run", response_model=EscalationSweepResponse)
def run_escalations(
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EscalationSweepResponse:
    """Force the age-escalation sweep now, ignoring the throttle.

    The sweep also runs on its own whenever a ticket list is loaded; this is
    for demonstrating it on command rather than waiting for the interval.
    """
    moved = ticket_service.sweep_escalations(db, force=True)
    return EscalationSweepResponse(escalated=moved)
