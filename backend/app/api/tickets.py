import json
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.geo import bounding_box, haversine_m
from app.core.security import get_current_profile, require_authority
from app.db.session import get_db
from app.ml.imaging import compute_phash, image_dimensions
from app.models.enums import CandidateStatus, TicketStatus, UserRole
from app.models.profile import Profile
from app.models.ticket import (
    DuplicateCandidate,
    Ticket,
    TicketCorroboration,
    TicketStatusHistory,
)
from app.schema.ticket import (
    AssignRequest,
    CorroborationRequest,
    CorroborationResponse,
    DuplicateCandidateResponse,
    MergeRequest,
    PhotoResponse,
    StatusHistoryEntry,
    StatusUpdateRequest,
    TicketCreateRequest,
    TicketCreateResponse,
    TicketDetail,
    TicketListResponse,
    TicketSummary,
)
from app.services import ticket_service
from app.services.storage_service import (
    MAX_PHOTOS_PER_TICKET,
    read_and_validate,
    signed_url,
    upload_photo,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])


# ---------------------------------------------------------------- mapping


def _candidate_response(
    db: Session, candidate: DuplicateCandidate, include_ticket: bool = True
) -> DuplicateCandidateResponse:
    response = DuplicateCandidateResponse.model_validate(candidate)

    if include_ticket:
        other = db.get(Ticket, candidate.candidate_ticket_id)
        if other is not None:
            response.candidate = TicketSummary.model_validate(other)

        subject = db.get(Ticket, candidate.ticket_id)
        if subject is not None:
            response.ticket = TicketSummary.model_validate(subject)

    reasons = [f"{candidate.distance_m:.0f}m apart"]
    if candidate.category_score >= 1.0:
        reasons.append("same category")
    if candidate.text_score >= 0.6:
        reasons.append(f"descriptions {candidate.text_score:.0%} similar")
    if candidate.image_score >= 0.5:
        reasons.append(f"photos {candidate.image_score:.0%} similar")
    response.explanation = ", ".join(reasons)

    return response


def _detail(
    db: Session, ticket: Ticket, viewer: Profile, include_candidates: bool
) -> TicketDetail:
    detail = TicketDetail.model_validate(ticket)

    reporter = db.get(Profile, ticket.reporter_id)
    detail.reporter_name = reporter.full_name if reporter else None

    detail.photos = [
        PhotoResponse(
            id=photo.id,
            storage_path=photo.storage_path,
            url=signed_url(photo.storage_path),
        )
        for photo in ticket.photos
    ]

    children = db.scalars(
        select(Ticket).where(Ticket.parent_id == ticket.id).order_by(Ticket.created_at)
    ).all()
    detail.children = [TicketSummary.model_validate(c) for c in children]

    history = db.scalars(
        select(TicketStatusHistory)
        .where(TicketStatusHistory.ticket_id == ticket.id)
        .order_by(TicketStatusHistory.created_at)
    ).all()
    detail.history = [StatusHistoryEntry.model_validate(h) for h in history]

    if include_candidates:
        candidates = db.scalars(
            select(DuplicateCandidate)
            .where(
                DuplicateCandidate.ticket_id == ticket.id,
                DuplicateCandidate.status == CandidateStatus.PENDING,
            )
            .order_by(DuplicateCandidate.score.desc())
        ).all()
        detail.duplicate_candidates = [
            _candidate_response(db, c) for c in candidates
        ]

    mine = db.scalar(
        select(TicketCorroboration).where(
            TicketCorroboration.ticket_id == ticket.id,
            TicketCorroboration.citizen_id == viewer.id,
        )
    )
    detail.my_corroboration = None if mine is None else mine.is_confirmed

    return detail


# --------------------------------------------------------------- creating


@router.post(
    "", response_model=TicketCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_ticket(
    payload: str = Form(
        ...,
        description="JSON body matching TicketCreateRequest.",
    ),
    photos: list[UploadFile] = File(default=[]),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketCreateResponse:
    """Submit a report.

    Multipart because photos ride along. The JSON body goes in the `payload`
    field; up to four images in `photos`.
    """
    try:
        data = TicketCreateRequest.model_validate(json.loads(payload))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"`payload` is not valid JSON: {exc}",
        ) from exc

    if len(photos) > MAX_PHOTOS_PER_TICKET:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"At most {MAX_PHOTOS_PER_TICKET} photos per report.",
        )

    # Read and hash before creating anything, so a bad image fails fast.
    prepared: list[tuple[bytes, str, str | None, int | None, int | None]] = []
    for upload in photos:
        if not upload.filename:
            continue
        content = await read_and_validate(upload)
        dimensions = image_dimensions(content)
        prepared.append(
            (
                content,
                upload.content_type or "image/jpeg",
                compute_phash(content),
                dimensions[0] if dimensions else None,
                dimensions[1] if dimensions else None,
            )
        )

    ticket, candidates = ticket_service.create_ticket(db, profile, data, photos=[])

    stored = []
    for content, content_type, phash, width, height in prepared:
        path = upload_photo(content, ticket.id, content_type)
        stored.append((path, phash, width, height))

    if stored:
        from app.models.ticket import TicketPhoto

        for path, phash, width, height in stored:
            db.add(
                TicketPhoto(
                    ticket_id=ticket.id,
                    storage_path=path,
                    phash=phash,
                    width=width,
                    height=height,
                )
            )
        db.flush()
        db.refresh(ticket)

        # Photos arrived after the first pass, so re-run matching with them.
        from app.models.category import Category

        category = db.get(Category, ticket.category_id)
        if category is not None:
            db.query(DuplicateCandidate).filter(
                DuplicateCandidate.ticket_id == ticket.id,
                DuplicateCandidate.status == CandidateStatus.PENDING,
            ).delete()
            db.flush()
            candidates = ticket_service.find_duplicate_candidates(
                db, ticket, category
            )

    db.flush()
    db.refresh(ticket)

    return TicketCreateResponse(
        ticket=_detail(db, ticket, profile, include_candidates=False),
        possible_duplicates=[_candidate_response(db, c) for c in candidates],
    )


# --------------------------------------------------------------- listing


@router.get("", response_model=TicketListResponse)
def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    category_id: UUID | None = None,
    ward_id: UUID | None = None,
    mine: bool = False,
    parents_only: bool = True,
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketListResponse:
    filters = list(ticket_service.scope_filter(profile))

    if mine:
        filters.append(Ticket.reporter_id == profile.id)
    if status_filter is not None:
        filters.append(Ticket.status == status_filter)
    if category_id is not None:
        filters.append(Ticket.category_id == category_id)
    if ward_id is not None:
        filters.append(Ticket.ward_id == ward_id)
    if parents_only and not mine:
        # Children are shown nested under their parent, not as separate rows.
        filters.append(Ticket.parent_id.is_(None))
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(Ticket.title).like(pattern)
            | func.lower(Ticket.description).like(pattern)
            | func.lower(Ticket.public_code).like(pattern)
        )

    total = db.scalar(select(func.count()).select_from(Ticket).where(*filters)) or 0
    rows = db.scalars(
        select(Ticket)
        .where(*filters)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return TicketListResponse(
        items=[TicketSummary.model_validate(t) for t in rows], total=total
    )


@router.get("/nearby", response_model=TicketListResponse)
def nearby_tickets(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_m: int = Query(default=1000, ge=50, le=10_000),
    limit: int = Query(default=20, ge=1, le=100),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketListResponse:
    """Open reports around a point, for the corroboration flow."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_m)

    filters = list(ticket_service.scope_filter(profile))
    filters += [
        Ticket.parent_id.is_(None),
        Ticket.status.in_(ticket_service.OPEN_STATUSES),
        Ticket.latitude.between(min_lat, max_lat),
        Ticket.longitude.between(min_lon, max_lon),
    ]

    rows = db.scalars(select(Ticket).where(*filters).limit(300)).all()

    items = []
    for ticket in rows:
        distance = haversine_m(latitude, longitude, ticket.latitude, ticket.longitude)
        if distance > radius_m:
            continue
        summary = TicketSummary.model_validate(ticket)
        summary.distance_m = round(distance, 1)
        items.append(summary)

    items.sort(key=lambda t: t.distance_m or 0.0)
    return TicketListResponse(items=items[:limit], total=len(items))


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id)
    return _detail(db, ticket, profile, include_candidates=profile.is_authority)


# ---------------------------------------------------------- corroboration


@router.post("/{ticket_id}/corroborate", response_model=CorroborationResponse)
def corroborate_ticket(
    ticket_id: UUID,
    data: CorroborationRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> CorroborationResponse:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket, distance = ticket_service.corroborate(
        db,
        profile,
        ticket,
        is_confirmed=data.is_confirmed,
        latitude=data.latitude,
        longitude=data.longitude,
        note=data.note,
    )

    if data.is_confirmed:
        message = (
            "Thank you. This report is now community verified."
            if ticket.community_verified
            else "Thank you for confirming this report."
        )
    else:
        message = "Thank you. Your objection has been recorded for review."

    return CorroborationResponse(
        ticket_id=ticket.id,
        corroboration_count=ticket.corroboration_count,
        dispute_count=ticket.dispute_count,
        community_verified=ticket.community_verified,
        distance_m=round(distance, 1),
        message=message,
    )


# ------------------------------------------------------- authority actions


@router.patch("/{ticket_id}/status", response_model=TicketDetail)
def update_status(
    ticket_id: UUID,
    data: StatusUpdateRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket = ticket_service.update_status(
        db,
        authority,
        ticket,
        data.status,
        note=data.note,
        resolution_note=data.resolution_note,
    )
    return _detail(db, ticket, authority, include_candidates=True)


@router.patch("/{ticket_id}/assign", response_model=TicketDetail)
def assign(
    ticket_id: UUID,
    data: AssignRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket = ticket_service.assign_ticket(
        db, authority, ticket, data.assigned_to_id, data.priority
    )
    return _detail(db, ticket, authority, include_candidates=True)


@router.post("/{ticket_id}/merge", response_model=TicketDetail)
def merge(
    ticket_id: UUID,
    data: MergeRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> TicketDetail:
    """Confirm a duplicate: fold this ticket under the given parent."""
    child = ticket_service.get_ticket(db, ticket_id)
    parent = ticket_service.merge_tickets(
        db, authority, child, data.parent_ticket_id, note=data.note
    )
    db.refresh(parent)
    return _detail(db, parent, authority, include_candidates=True)


@router.post("/{ticket_id}/split", response_model=TicketDetail)
def split(
    ticket_id: UUID,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> TicketDetail:
    """Undo a merge that was wrong."""
    child = ticket_service.get_ticket(db, ticket_id)
    child = ticket_service.split_ticket(db, authority, child)
    return _detail(db, child, authority, include_candidates=True)


@router.get("/{ticket_id}/candidates", response_model=list[DuplicateCandidateResponse])
def list_candidates(
    ticket_id: UUID,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> list[DuplicateCandidateResponse]:
    ticket = ticket_service.get_ticket(db, ticket_id)
    rows = db.scalars(
        select(DuplicateCandidate)
        .where(
            DuplicateCandidate.ticket_id == ticket.id,
            DuplicateCandidate.status == CandidateStatus.PENDING,
        )
        .order_by(DuplicateCandidate.score.desc())
    ).all()
    return [_candidate_response(db, c) for c in rows]


@router.post(
    "/candidates/{candidate_id}/reject", response_model=DuplicateCandidateResponse
)
def dismiss_candidate(
    candidate_id: UUID,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> DuplicateCandidateResponse:
    """Say 'these are different problems' and clear the suggestion."""
    candidate = db.get(DuplicateCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such suggestion."
        )

    candidate = ticket_service.reject_candidate(db, authority, candidate)
    return _candidate_response(db, candidate)


@router.get("/review/queue", response_model=list[DuplicateCandidateResponse])
def review_queue(
    limit: int = Query(default=25, ge=1, le=100),
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> list[DuplicateCandidateResponse]:
    """Every pending merge suggestion in this authority's scope, best first."""
    scope = ticket_service.scope_filter(authority)

    rows = db.scalars(
        select(DuplicateCandidate)
        .join(Ticket, Ticket.id == DuplicateCandidate.ticket_id)
        .where(DuplicateCandidate.status == CandidateStatus.PENDING, *scope)
        .order_by(DuplicateCandidate.score.desc())
        .limit(limit)
    ).all()

    return [_candidate_response(db, c) for c in rows]
