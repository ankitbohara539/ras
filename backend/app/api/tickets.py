import json
from concurrent.futures import ThreadPoolExecutor
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
from starlette.concurrency import run_in_threadpool

from app.core.geocode import reverse_geocode
from app.core.security import get_current_profile, require_authority
from app.db.session import get_db, read_session
from app.ml.imaging import compute_phash, image_dimensions
from app.models.enums import CandidateStatus, TicketStatus, UserRole
from app.models.profile import Profile
from app.models.ticket import (
    DuplicateCandidate,
    Ticket,
    TicketComment,
    TicketCorroboration,
    TicketPhoto,
    TicketStatusHistory,
)
from app.schema.ticket import (
    AssignRequest,
    CorroborationRequest,
    CorroborationResponse,
    DuplicateCandidateResponse,
    MergeRequest,
    PhotoResponse,
    PriorityUpdateRequest,
    ReassignWardRequest,
    StatusHistoryEntry,
    StatusUpdateRequest,
    TicketCommentCreateRequest,
    TicketCommentListResponse,
    TicketCommentResponse,
    TicketCreateRequest,
    TicketCreateResponse,
    TicketDetail,
    TicketListResponse,
    TicketSummary,
    TicketUpdateRequest,
)
from app.services import ticket_service
from app.services.storage_service import (
    MAX_PHOTOS_PER_TICKET,
    read_and_validate,
    signed_urls,
    remove_photos,
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


def _prefetch_candidate_tickets(db: Session, candidates) -> list[Ticket]:
    """Load every ticket a list of suggestions mentions, in one query.

    _candidate_response looks each one up with db.get; with them already in
    the session's identity map those lookups cost nothing, instead of two
    round trips per suggestion.

    The caller must hold on to the returned list until it is done: the
    identity map only keeps weak references, so discarded rows are collected
    at once and db.get goes back to the database.
    """
    ids = {c.ticket_id for c in candidates} | {c.candidate_ticket_id for c in candidates}
    if not ids:
        return []
    return list(db.scalars(select(Ticket).where(Ticket.id.in_(ids))).all())


# Filled by the parts below, never read off the ORM object -- reading
# `ticket.photos` or `ticket.children` would fire a lazy query each.
_DETAIL_PARTS = {
    "photos",
    "children",
    "history",
    "duplicate_candidates",
    "my_corroboration",
    "reporter_name",
    "priority_set_by_name",
}

# The ticket page needs six independent reads. With the database ~145ms away,
# running them one after another was most of the page's load time; run in
# parallel they cost about one round trip. Bounded, because each worker holds
# a pooled connection and the Supabase pooler has a small connection cap.
_DETAIL_WORKERS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ticket-detail")


def _detail(
    db: Session,
    ticket: Ticket,
    viewer: Profile,
    include_candidates: bool,
    parallel: bool = False,
) -> TicketDetail:
    """Everything the ticket page shows.

    `parallel` only for plain reads: each part then runs on its own
    connection, which cannot see rows this request has not committed yet --
    right after a status change or a new report, the history would be stale.
    """
    ticket_id = ticket.id
    people_ids = {ticket.reporter_id, ticket.priority_set_by_id} - {None}

    def people(s: Session) -> dict:
        return {
            p.id: p.full_name
            for p in s.scalars(select(Profile).where(Profile.id.in_(people_ids))).all()
        }

    def photos(s: Session) -> list[PhotoResponse]:
        rows = s.scalars(
            select(TicketPhoto)
            .where(TicketPhoto.ticket_id == ticket_id)
            .order_by(TicketPhoto.created_at)
        ).all()
        urls = signed_urls([p.storage_path for p in rows])
        return [
            PhotoResponse(id=p.id, storage_path=p.storage_path, url=urls.get(p.storage_path))
            for p in rows
        ]

    def children(s: Session) -> list[TicketSummary]:
        rows = s.scalars(
            select(Ticket).where(Ticket.parent_id == ticket_id).order_by(Ticket.created_at)
        ).all()
        return [TicketSummary.model_validate(c) for c in rows]

    def history(s: Session) -> list[StatusHistoryEntry]:
        rows = s.scalars(
            select(TicketStatusHistory)
            .where(TicketStatusHistory.ticket_id == ticket_id)
            .order_by(TicketStatusHistory.created_at)
        ).all()
        return [StatusHistoryEntry.model_validate(h) for h in rows]

    def mine(s: Session) -> bool | None:
        row = s.scalar(
            select(TicketCorroboration).where(
                TicketCorroboration.ticket_id == ticket_id,
                TicketCorroboration.citizen_id == viewer.id,
            )
        )
        return None if row is None else row.is_confirmed

    def candidates(s: Session) -> list[DuplicateCandidateResponse]:
        rows = s.scalars(
            select(DuplicateCandidate)
            .where(
                DuplicateCandidate.ticket_id == ticket_id,
                DuplicateCandidate.status == CandidateStatus.PENDING,
            )
            .order_by(DuplicateCandidate.score.desc())
        ).all()
        loaded = _prefetch_candidate_tickets(s, rows)  # noqa: F841 -- keep alive
        return [_candidate_response(s, c) for c in rows]

    parts = {
        "people": people,
        "photos": photos,
        "children": children,
        "history": history,
        "mine": mine,
    }
    if include_candidates:
        parts["candidates"] = candidates

    if parallel:
        def run(part):
            with read_session() as s:
                return part(s)

        futures = {name: _DETAIL_WORKERS.submit(run, part) for name, part in parts.items()}
        results = {name: future.result() for name, future in futures.items()}
    else:
        results = {name: part(db) for name, part in parts.items()}

    detail = TicketDetail.model_validate(
        {
            name: getattr(ticket, name)
            for name in TicketDetail.model_fields
            if name not in _DETAIL_PARTS and hasattr(ticket, name)
        }
    )
    names = results["people"]
    detail.reporter_name = names.get(ticket.reporter_id)
    if ticket.priority_set_by_id is not None:
        detail.priority_set_by_name = names.get(ticket.priority_set_by_id)
    detail.photos = results["photos"]
    detail.children = results["children"]
    detail.history = results["history"]
    detail.my_corroboration = results["mine"]
    if include_candidates:
        detail.duplicate_candidates = results["candidates"]
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

    # The form fills this from the map pin; this covers a client that did not
    # (older app, geocoder unreachable from the phone). Best effort -- None
    # just leaves the coordinates to speak for themselves.
    if not (data.address_text or "").strip():
        place = await run_in_threadpool(
            reverse_geocode, data.latitude, data.longitude, data.description_lang.value
        )
        if place is not None:
            data.address_text = place.place_name

    # Ward routing needs the English lookup. Warm it off the event loop so
    # the (synchronous) create below finds it cached instead of blocking the
    # server on the network; the form's /geo/reverse call usually cached it.
    await run_in_threadpool(reverse_geocode, data.latitude, data.longitude, "en")

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

    # Only now, with photos in, is the score final enough to act on.
    merged = ticket_service.auto_merge_if_confident(db, ticket, candidates)

    db.flush()
    db.refresh(ticket)

    loaded = _prefetch_candidate_tickets(db, candidates)  # noqa: F841 -- keep alive
    return TicketCreateResponse(
        ticket=_detail(db, ticket, profile, include_candidates=False),
        possible_duplicates=[_candidate_response(db, c) for c in candidates],
        auto_merged_into=TicketSummary.model_validate(merged[0]) if merged else None,
        auto_merge_score=merged[1].score if merged else None,
    )


# --------------------------------------------------------------- listing


@router.get("", response_model=TicketListResponse)
def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    category_id: UUID | None = None,
    ward_id: UUID | None = None,
    reporter_id: UUID | None = None,
    mine: bool = False,
    parents_only: bool = True,
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketListResponse:
    # Age escalation has no scheduler behind it. Sweeping here (throttled to
    # once every few minutes) means a ticket that has gone stale has already
    # moved by the time anyone opens a queue to look at it.
    ticket_service.sweep_escalations(db)

    filters = list(ticket_service.scope_filter(profile))

    if mine:
        filters.append(Ticket.reporter_id == profile.id)
    if status_filter is not None:
        filters.append(Ticket.status == status_filter)
    if category_id is not None:
        filters.append(Ticket.category_id == category_id)
    if ward_id is not None:
        filters.append(Ticket.ward_id == ward_id)
    if reporter_id is not None:
        filters.append(Ticket.reporter_id == reporter_id)
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

    rows = db.scalars(
        select(Ticket)
        .where(*filters)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    # A short page is the whole remainder, so the total needs no second
    # round trip to count -- the common case for every list in the app.
    if len(rows) < limit:
        total = offset + len(rows)
    else:
        total = db.scalar(select(func.count()).select_from(Ticket).where(*filters)) or 0

    return TicketListResponse(
        items=[TicketSummary.model_validate(t) for t in rows], total=total
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id)
    if not ticket_service.can_view_ticket(profile, ticket):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this report.",
        )
    return _detail(
        db, ticket, profile, include_candidates=profile.is_authority, parallel=True
    )


@router.patch("/{ticket_id}", response_model=TicketDetail)
def update_ticket_content(
    ticket_id: UUID,
    data: TicketUpdateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketDetail:
    ticket = ticket_service.get_ticket(db, ticket_id)
    is_owner = ticket.reporter_id == profile.id
    if profile.role is not UserRole.ADMIN and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can edit only your own report.")
    if profile.role is not UserRole.ADMIN and ticket.status is not TicketStatus.REPORTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reports can be edited only before an authority starts reviewing them.",
        )
    if ticket.parent_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A merged duplicate cannot be edited separately.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    db.flush()
    return _detail(db, ticket, profile, include_candidates=profile.is_authority)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> None:
    ticket = ticket_service.get_ticket(db, ticket_id)
    if profile.role is not UserRole.ADMIN and ticket.reporter_id != profile.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can delete only your own report.")
    if ticket.parent_id is None and ticket.child_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report has corroborating duplicate reports and cannot be deleted.",
        )
    paths = list(db.scalars(select(TicketPhoto.storage_path).where(TicketPhoto.ticket_id == ticket.id)).all())
    db.delete(ticket)
    db.flush()
    remove_photos(paths)


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


# -------------------------------------------------------------- comments


def _comment_response(comment, viewer: Profile, author: Profile | None) -> TicketCommentResponse:
    response = TicketCommentResponse.model_validate(comment)
    response.author_name = author.full_name if author else None
    response.author_role = author.role.value if author else None
    response.is_mine = comment.author_id == viewer.id
    return response


@router.get("/{ticket_id}/comments", response_model=TicketCommentListResponse)
def get_comments(
    ticket_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketCommentListResponse:
    ticket = ticket_service.get_ticket(db, ticket_id)
    rows, total = ticket_service.list_comments(db, profile, ticket, limit, offset)

    # Authors are joined into the comment query; no second lookup.
    return TicketCommentListResponse(
        items=[_comment_response(c, profile, c.author) for c in rows],
        total=total,
    )


@router.post("/{ticket_id}/comments", response_model=TicketCommentResponse)
def post_comment(
    ticket_id: UUID,
    data: TicketCommentCreateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> TicketCommentResponse:
    ticket = ticket_service.get_ticket(db, ticket_id)
    comment = ticket_service.add_comment(db, profile, ticket, data.body)
    return _comment_response(comment, profile, profile)


@router.delete("/{ticket_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    ticket_id: UUID,
    comment_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> None:
    ticket = ticket_service.get_ticket(db, ticket_id)
    comment = db.get(TicketComment, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such comment."
        )
    ticket_service.delete_comment(db, profile, ticket, comment)


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


@router.patch("/{ticket_id}/priority", response_model=TicketDetail)
def set_priority(
    ticket_id: UUID,
    data: PriorityUpdateRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> TicketDetail:
    """Override priority by hand, or send `priority: null` to un-override.

    An override locks the ticket: neither the score nor the age ladder will
    touch it again until someone clears it.
    """
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket = ticket_service.set_priority(
        db, authority, ticket, data.priority, note=data.note
    )
    return _detail(db, ticket, authority, include_candidates=True)


@router.patch("/{ticket_id}/ward", response_model=TicketDetail)
def reassign_ward(
    ticket_id: UUID,
    data: ReassignWardRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> TicketDetail:
    """Correct a ticket that GPS routed to the wrong ward."""
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket = ticket_service.reassign_ward(db, authority, ticket, data.ward_id)
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
    loaded = _prefetch_candidate_tickets(db, rows)  # noqa: F841 -- keep alive
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

    loaded = _prefetch_candidate_tickets(db, rows)  # noqa: F841 -- keep alive
    return [_candidate_response(db, c) for c in rows]
