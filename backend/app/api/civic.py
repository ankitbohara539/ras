"""Civic-sense complaints: citizens report another person's conduct.

Private by construction: every read goes through civic_service's scope
rules, so a complaint is only ever returned to its reporter, the ward office
where it happened, or an admin.
"""

import json
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app.core.geocode import reverse_geocode
from app.core.security import get_current_profile
from app.db.session import get_db
from app.models.civic import CivicComplaint
from app.models.enums import CivicCategory, CivicStatus, UserRole
from app.models.profile import Profile
from app.schema.civic import (
    CivicComplaintCreateRequest,
    CivicComplaintListResponse,
    CivicComplaintResponse,
    CivicComplaintUpdateRequest,
    CivicPhoto,
    CivicStatusUpdateRequest,
)
from app.services import civic_service
from app.services.storage_service import (
    read_and_validate,
    remove_photos,
    signed_urls,
    upload_photo,
)

router = APIRouter(prefix="/civic", tags=["Civic complaints"])


def _response(
    db: Session, complaint: CivicComplaint, viewer: Profile
) -> CivicComplaintResponse:
    response = CivicComplaintResponse.model_validate(complaint)
    urls = signed_urls([p.storage_path for p in complaint.photos])
    response.photos = [
        CivicPhoto(id=p.id, url=urls.get(p.storage_path)) for p in complaint.photos
    ]
    if civic_service.can_manage(viewer, complaint):
        reporter = db.get(Profile, complaint.reporter_id)
        if reporter is not None:
            response.reporter_name = reporter.full_name
            response.reporter_phone = reporter.phone
    return response


@router.post("", response_model=CivicComplaintResponse, status_code=status.HTTP_201_CREATED)
async def file_complaint(
    payload: str = Form(..., description="JSON body matching CivicComplaintCreateRequest."),
    photos: list[UploadFile] = File(default=[]),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> CivicComplaintResponse:
    try:
        data = CivicComplaintCreateRequest.model_validate(json.loads(payload))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"`payload` is not valid JSON: {exc}",
        ) from exc

    # Refuse before uploading anything that would then be orphaned.
    civic_service.check_can_file(db, profile)

    uploads = [p for p in photos if p.filename]
    if not uploads:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add at least one photo of what happened.",
        )
    if len(uploads) > civic_service.MAX_PHOTOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"At most {civic_service.MAX_PHOTOS} photos per complaint.",
        )

    contents = [(await read_and_validate(u), u.content_type or "image/jpeg") for u in uploads]

    # Place name and ward lookups hit the network; keep them off the event loop.
    if not (data.address_text or "").strip():
        place = await run_in_threadpool(reverse_geocode, data.latitude, data.longitude, "en")
        if place is not None:
            data.address_text = place.place_name
    else:
        await run_in_threadpool(reverse_geocode, data.latitude, data.longitude, "en")

    folder = f"civic/{uuid.uuid4()}"
    paths = [
        await run_in_threadpool(upload_photo, content, folder, content_type)
        for content, content_type in contents
    ]

    try:
        complaint = civic_service.create_complaint(
            db,
            profile,
            category=data.category,
            description=data.description,
            latitude=data.latitude,
            longitude=data.longitude,
            address_text=data.address_text,
            occurred_at=data.occurred_at,
            photo_paths=paths,
        )
        return _response(db, complaint, profile)
    except Exception:
        # The row will be rolled back; do not leave photos of a person in
        # storage with nothing pointing at them.
        await run_in_threadpool(remove_photos, paths)
        raise


@router.get("", response_model=CivicComplaintListResponse)
def list_complaints(
    status_filter: CivicStatus | None = Query(default=None, alias="status"),
    category: CivicCategory | None = None,
    ward_id: UUID | None = None,
    reporter_id: UUID | None = None,
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> CivicComplaintListResponse:
    """A citizen gets their own complaints; an office gets its ward's queue."""
    scope = civic_service.scope_filters(profile)

    filters = list(scope)
    if status_filter is not None:
        filters.append(CivicComplaint.status == status_filter)
    if category is not None:
        filters.append(CivicComplaint.category == category)
    if ward_id is not None:
        filters.append(CivicComplaint.ward_id == ward_id)
    if reporter_id is not None:
        filters.append(CivicComplaint.reporter_id == reporter_id)
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(CivicComplaint.public_code).like(pattern)
            | func.lower(CivicComplaint.description).like(pattern)
            | func.lower(func.coalesce(CivicComplaint.address_text, "")).like(pattern)
        )

    rows = db.scalars(
        select(CivicComplaint)
        .options(selectinload(CivicComplaint.photos))
        .where(*filters)
        .order_by(CivicComplaint.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).unique().all()
    total = db.scalar(select(func.count()).select_from(CivicComplaint).where(*filters)) or 0

    counts = {
        s.value: c
        for s, c in db.execute(
            select(CivicComplaint.status, func.count())
            .where(*scope)
            .group_by(CivicComplaint.status)
        ).all()
    }

    return CivicComplaintListResponse(
        items=[_response(db, c, profile) for c in rows],
        total=total,
        counts=counts,
    )


@router.get("/{complaint_id}", response_model=CivicComplaintResponse)
def get_complaint(
    complaint_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> CivicComplaintResponse:
    complaint = civic_service.get_visible(db, profile, complaint_id)
    return _response(db, complaint, profile)


@router.patch("/{complaint_id}", response_model=CivicComplaintResponse)
def update_complaint(
    complaint_id: UUID,
    data: CivicComplaintUpdateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> CivicComplaintResponse:
    complaint = civic_service.get_visible(db, profile, complaint_id)
    if profile.role is not UserRole.ADMIN and complaint.reporter_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can edit only your own civic complaint.")
    if profile.role is not UserRole.ADMIN and complaint.status is not CivicStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A civic complaint can be edited only before review starts.",
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(complaint, field, value)
    db.flush()
    return _response(db, complaint, profile)


@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_complaint(
    complaint_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> None:
    complaint = civic_service.get_visible(db, profile, complaint_id)
    if profile.role is not UserRole.ADMIN and complaint.reporter_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can delete only your own civic complaint.")
    if profile.role is not UserRole.ADMIN and complaint.status is not CivicStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A civic complaint can be deleted only before review starts.",
        )
    paths = [p.storage_path for p in complaint.photos]
    db.delete(complaint)
    db.flush()
    remove_photos(paths)


@router.patch("/{complaint_id}/status", response_model=CivicComplaintResponse)
def update_status(
    complaint_id: UUID,
    data: CivicStatusUpdateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> CivicComplaintResponse:
    complaint = civic_service.get_visible(db, profile, complaint_id)
    complaint = civic_service.update_status(db, profile, complaint, data.status, data.note)
    return _response(db, complaint, profile)
