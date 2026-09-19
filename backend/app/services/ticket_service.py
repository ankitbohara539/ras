"""Ticket lifecycle: creation, duplicate detection, merging and status flow.

The matcher writes suggestions and, when it is sure enough (score at or above
`dedupe_auto_merge_score`), merges on its own. Everything else waits for an
authority. `parent_id` is set in exactly one place -- `_fold_under` -- reached
either through `merge_tickets` (an authority) or `auto_merge_if_confident`.
Any merge, automatic or not, can be undone with `split_ticket`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.cache import REFERENCE_TTL_S, cache
from app.core.config import get_settings
from app.core.geo import bounding_box, haversine_m
from app.core.geocode import reverse_geocode
from app.core.security import assert_can_access_ward
from app.ml.matcher import MatchCandidate, MatchInput, MatchWeights, rank_candidates
from app.ml.registry import ModelsNotTrained, get_classifier, get_encoder
from app.ml.urgency import is_urgent
from app.models.category import Category
from app.models.enums import (
    CandidateStatus,
    NotificationType,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.geography import Ward
from app.models.notification import Notification
from app.models.profile import Profile
from app.models.ticket import (
    DuplicateCandidate,
    Ticket,
    TicketComment,
    TicketCorroboration,
    TicketPhoto,
    TicketStatusHistory,
)
from app.schema.ticket import TicketCreateRequest

# A ticket can absorb duplicates only while it is still open.
OPEN_STATUSES = (
    TicketStatus.REPORTED,
    TicketStatus.VERIFIED,
    TicketStatus.IN_PROGRESS,
)

# Which transitions an authority may make.
ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.REPORTED: {
        TicketStatus.VERIFIED,
        TicketStatus.REJECTED,
        TicketStatus.IN_PROGRESS,
    },
    TicketStatus.VERIFIED: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
    },
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.REJECTED},
    TicketStatus.RESOLVED: {TicketStatus.IN_PROGRESS},
    TicketStatus.REJECTED: {TicketStatus.REPORTED},
    TicketStatus.MERGED: set(),  # a child follows its parent
}


# ---------------------------------------------------------------- helpers


def _now() -> datetime:
    return datetime.now(UTC)


def _name_key(name: str | None) -> str:
    """ "Kathmandu Metropolitan City" / "Kathmandu" -> "kathmandu"."""
    if not name:
        return ""
    first = name.strip().split()[0] if name.strip() else ""
    return "".join(ch for ch in first.lower() if ch.isalpha())


@dataclass(frozen=True)
class WardInfo:
    """A ward as plain data, safe to share between requests (unlike an ORM row)."""

    id: UUID
    number: int
    name_en: str | None
    name_ne: str | None
    municipality_id: UUID
    municipality_code: str
    municipality_name_en: str
    centroid_lat: float
    centroid_lon: float


def ward_index(db: Session) -> list[WardInfo]:
    """Every ward, cached: it changes only when the seed script is re-run.

    Used on every location lookup -- the report form asks each time its pin
    moves -- where reading all 94 wards cost two database round trips.
    """

    def load() -> list[WardInfo]:
        rows = db.scalars(select(Ward).options(selectinload(Ward.municipality))).all()
        return [
            WardInfo(
                id=w.id,
                number=w.number,
                name_en=w.name_en,
                name_ne=w.name_ne,
                municipality_id=w.municipality_id,
                municipality_code=w.municipality.code if w.municipality else "",
                municipality_name_en=w.municipality.name_en if w.municipality else "",
                centroid_lat=w.centroid_lat,
                centroid_lon=w.centroid_lon,
            )
            for w in rows
        ]

    wards = cache.get_or_load("ref:wards", load, REFERENCE_TTL_S)
    if not wards:
        # Do not remember "no wards": the seed may be running right now.
        cache.invalidate("ref:wards")
    return wards


def category_keys(db: Session) -> dict[UUID, str]:
    """Category id -> key, cached like the ward directory."""
    return cache.get_or_load(
        "ref:category_keys",
        lambda: {c.id: c.key for c in db.scalars(select(Category)).all()},
        REFERENCE_TTL_S,
    )


def category_radii(db: Session) -> dict[UUID, int]:
    """Category id -> match radius in metres, cached like the ward directory."""
    return cache.get_or_load(
        "ref:category_radii",
        lambda: {c.id: c.match_radius_m for c in db.scalars(select(Category)).all()},
        REFERENCE_TTL_S,
    )


def locate_ward(db: Session, latitude: float, longitude: float) -> WardInfo:
    """Which ward contains these coordinates.

    The seeded centroids are the real ward centres (OpenStreetMap ward
    boundaries), but "nearest centre" is still only an approximation near a
    boundary, and OpenStreetMap knows the actual ward (city_district
    "Kathmandu-07"), so it is asked first:

      1. OSM's ward and municipality, when both match a seeded ward.
      2. Otherwise the nearest centre *inside* OSM's municipality.
      3. Otherwise (geocoder down, place outside the seeded area) the nearest
         centre overall.
    """
    wards = ward_index(db)
    if not wards:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No wards are configured. Run: python -m scripts.seed",
        )

    def nearest(pool: list[WardInfo]) -> WardInfo:
        return min(
            pool,
            key=lambda w: haversine_m(latitude, longitude, w.centroid_lat, w.centroid_lon),
        )

    # English, whatever the UI language: the ward tag is parsed from it.
    place = reverse_geocode(latitude, longitude, "en")
    if place is not None:
        area = _name_key(place.ward_area) or _name_key(place.city)
        in_municipality = [w for w in wards if _name_key(w.municipality_name_en) == area]
        if in_municipality:
            if place.ward_number is not None:
                for ward in in_municipality:
                    if ward.number == place.ward_number:
                        return ward
            return nearest(in_municipality)

    return nearest(wards)


def resolve_ward(db: Session, latitude: float, longitude: float) -> Ward:
    """locate_ward, as the ORM row callers attach to a ticket or complaint.

    The citizen never picks a ward: the location decides, which is both less
    friction and harder to game than a dropdown.
    """
    info = locate_ward(db, latitude, longitude)
    ward = db.get(Ward, info.id)
    if ward is None:  # deleted by a reseed since the directory was cached
        cache.invalidate("ref:wards")
        info = locate_ward(db, latitude, longitude)
        ward = db.get(Ward, info.id)
    return ward


def generate_public_code(db: Session, ward: Ward) -> str:
    """Human-quotable ticket reference, e.g. KMC-05-000142."""
    municipality_code = ward.municipality.code if ward.municipality else "GEN"

    used = db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.ward_id == ward.id)
    ) or 0

    # Collisions are possible under concurrency; walk forward until free.
    for offset in range(1, 200):
        code = f"{municipality_code}-{ward.number:02d}-{used + offset:06d}"
        exists = db.scalar(select(Ticket.id).where(Ticket.public_code == code))
        if exists is None:
            return code

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate a ticket code.",
    )


PRIORITY_RANK: dict[TicketPriority, int] = {
    TicketPriority.LOW: 0,
    TicketPriority.MEDIUM: 1,
    TicketPriority.HIGH: 2,
    TicketPriority.CRITICAL: 3,
}
_PRIORITY_BY_RANK = {rank: priority for priority, rank in PRIORITY_RANK.items()}


def compute_priority(ticket: Ticket, category: Category) -> TicketPriority:
    """Blend category severity with how many people are affected.

    Twelve reports of one pothole should outrank one report of the same
    pothole -- that fan-in is the reason for merging duplicates at all.

    This is the *scored* priority only. Age is handled separately by
    `escalate_for_age`, because a ladder with named steps is something an
    officer can predict and a citizen can be told ("nobody touched it for a
    week, so it moved up"), which a soft nudge inside a score is not.
    """
    # Column defaults are applied at flush, so a not-yet-inserted ticket still
    # has None in its counters. Coalesce rather than reorder the caller.
    children = ticket.child_count or 0
    confirmations = ticket.corroboration_count or 0
    disputes = ticket.dispute_count or 0

    score = category.base_severity

    # Each additional reporter adds weight, with diminishing returns.
    score += min(0.30, 0.06 * children)
    score += min(0.20, 0.05 * confirmations)

    if ticket.community_verified:
        score += 0.10

    # Disputes pull it back down.
    score -= min(0.20, 0.07 * disputes)

    if score >= 1.00:
        return TicketPriority.CRITICAL
    if score >= 0.75:
        return TicketPriority.HIGH
    if score >= 0.50:
        return TicketPriority.MEDIUM
    return TicketPriority.LOW


def escalate_for_age(
    base: TicketPriority,
    created_at: datetime | None,
    ticket_status: TicketStatus,
) -> TicketPriority:
    """Climb the ladder for a ticket nobody has resolved.

    low -> medium after `escalate_low_to_medium_days` open, then
    medium -> high after a further `escalate_medium_to_high_days`.

    The days are counted from `created_at` and the ladder starts at whatever
    the score says, so a ticket that is medium on severity alone reaches high
    in 3 days while one that starts low takes 10. That is the intent: a
    mid-severity problem left alone should not wait as long as a minor one.

    Escalation stops at high. Critical means dangerous, and age is not danger
    -- an officer who thinks otherwise can set it by hand.
    """
    if ticket_status not in OPEN_STATUSES or created_at is None:
        return base

    settings = get_settings()
    age_days = (_now() - created_at).days

    if base is TicketPriority.LOW:
        threshold_high = (
            settings.escalate_low_to_medium_days + settings.escalate_medium_to_high_days
        )
        if age_days >= threshold_high:
            return TicketPriority.HIGH
        if age_days >= settings.escalate_low_to_medium_days:
            return TicketPriority.MEDIUM
        return base

    if base is TicketPriority.MEDIUM:
        if age_days >= settings.escalate_medium_to_high_days:
            return TicketPriority.HIGH
        return base

    return base


def escalate_for_comments(
    base: TicketPriority, urgent_commenters: int
) -> TicketPriority:
    """Raise priority when enough different people say it is urgent.

    One level for every `urgent_commenters_per_level` distinct citizens whose
    comment presses for a fix (3 people -> +1, 6 -> +2). A pothole that scores
    low but has a thread full of "someone will get hurt, fix it soon" is not
    low any more, and the thread is the evidence.

    Stops at high, for the same reason age does: critical means dangerous, and
    an officer decides that. Never lowers anything.
    """
    per_level = get_settings().urgent_commenters_per_level
    if per_level <= 0 or urgent_commenters < per_level:
        return base

    rank = PRIORITY_RANK[base]
    ceiling = PRIORITY_RANK[TicketPriority.HIGH]
    if rank >= ceiling:
        return base

    levels = urgent_commenters // per_level
    return _PRIORITY_BY_RANK[min(rank + levels, ceiling)]


def apply_priority(ticket: Ticket, category: Category) -> TicketPriority:
    """Set `ticket.priority` from the score, comment pressure and age.

    The single place automatic priority is written. A locked ticket is left
    exactly as the human left it.
    """
    if ticket.priority_locked:
        return ticket.priority

    scored = compute_priority(ticket, category)
    pressed = escalate_for_comments(
        scored, getattr(ticket, "urgent_commenter_count", 0) or 0
    )
    ticket.priority = escalate_for_age(pressed, ticket.created_at, ticket.status)
    return ticket.priority


def _notify(
    db: Session,
    user_id: UUID,
    notification_type: NotificationType,
    title_en: str,
    title_ne: str,
    body_en: str | None = None,
    ticket_id: UUID | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=notification_type,
            title_en=title_en,
            title_ne=title_ne,
            body_en=body_en,
            ticket_id=ticket_id,
        )
    )


def _record_status(
    db: Session,
    ticket: Ticket,
    from_status: TicketStatus | None,
    to_status: TicketStatus,
    actor_id: UUID | None,
    note: str | None = None,
) -> None:
    db.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=actor_id,
            note=note,
        )
    )


# ------------------------------------------------------------ duplicates


def find_duplicate_candidates(
    db: Session, ticket: Ticket, category: Category
) -> list[DuplicateCandidate]:
    """Score the new ticket against open parents nearby and store suggestions.

    Candidates are restricted to the same ward, still-open parent tickets,
    inside the category's time window and bounding box. The exact distance
    gate lives in rank_candidates.
    """
    settings = get_settings()

    window_start = _now() - timedelta(days=category.dedupe_window_days)
    min_lat, max_lat, min_lon, max_lon = bounding_box(
        ticket.latitude,
        ticket.longitude,
        category.match_radius_m + settings.dedupe_gps_slack_m,
    )

    query: Select = (
        select(Ticket)
        .options(selectinload(Ticket.photos))
        .where(
            Ticket.id != ticket.id,
            Ticket.ward_id == ticket.ward_id,
            # Only a parent can absorb a duplicate: no grandchildren.
            Ticket.parent_id.is_(None),
            Ticket.status.in_(OPEN_STATUSES),
            Ticket.created_at >= window_start,
            Ticket.latitude.between(min_lat, max_lat),
            Ticket.longitude.between(min_lon, max_lon),
        )
        .limit(200)
    )

    nearby = db.scalars(query).all()
    if not nearby:
        return []

    new_phashes = [p.phash for p in ticket.photos]
    # The ticket's own category, not the classifier's guess: when a citizen
    # picks "Illegal Construction" and the model guessed something else, the
    # citizen is right. Matching on the guess merged two different problems
    # whose short descriptions happened to fool the classifier the same way.
    match_input = MatchInput(
        category_key=category.key,
        embedding=list(ticket.embedding) if ticket.embedding is not None else None,
        latitude=ticket.latitude,
        longitude=ticket.longitude,
        phashes=new_phashes,
    )

    keys_by_id = category_keys(db)

    candidates = [
        MatchCandidate(
            ticket_id=other.id,
            category_key=keys_by_id.get(other.category_id, "other"),
            embedding=list(other.embedding) if other.embedding is not None else None,
            latitude=other.latitude,
            longitude=other.longitude,
            phashes=[p.phash for p in other.photos],
        )
        for other in nearby
    ]

    weights = MatchWeights(
        category=settings.dedupe_weight_category,
        text=settings.dedupe_weight_text,
        image=settings.dedupe_weight_image,
        geo=settings.dedupe_weight_geo,
    )

    results = rank_candidates(
        match_input,
        candidates,
        radius_m=category.match_radius_m,
        weights=weights,
        min_score=settings.dedupe_min_score,
        limit=settings.dedupe_max_candidates,
        gps_slack_m=settings.dedupe_gps_slack_m,
    )

    rows = []
    for result in results:
        row = DuplicateCandidate(
            ticket_id=ticket.id,
            candidate_ticket_id=result.ticket_id,
            score=result.score,
            category_score=result.category_score,
            text_score=result.text_score,
            image_score=result.image_score,
            geo_score=result.geo_score,
            distance_m=result.distance_m,
            status=CandidateStatus.PENDING,
        )
        db.add(row)
        rows.append(row)

    db.flush()
    return rows


# --------------------------------------------------------------- creation


def create_ticket(
    db: Session,
    reporter: Profile,
    data: TicketCreateRequest,
    photos: list[tuple[str, str | None, int | None, int | None]] | None = None,
) -> tuple[Ticket, list[DuplicateCandidate]]:
    """Create a ticket, classify it, embed it and find duplicate suggestions.

    `photos` is a list of (storage_path, phash, width, height) already uploaded.
    """
    ward = resolve_ward(db, data.latitude, data.longitude)

    predicted_key: str | None = None
    confidence: float | None = None
    embedding: list[float] | None = None

    try:
        classifier = get_classifier()
        encoder = get_encoder()

        prediction = classifier.predict(data.description)
        predicted_key = prediction.category_key
        confidence = prediction.confidence
        embedding = encoder.encode_one(data.description)
    except ModelsNotTrained:
        # The app must still accept reports without a trained model; it just
        # cannot suggest duplicates for them.
        predicted_key = None

    # The citizen's choice wins when they made one.
    if data.category_id is not None:
        category = db.get(Category, data.category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown category.",
            )
    else:
        lookup_key = predicted_key or "other"
        category = db.scalar(select(Category).where(Category.key == lookup_key))
        if category is None:
            category = db.scalar(select(Category).where(Category.key == "other"))
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No categories are configured. Run: python -m scripts.seed",
            )

    title = data.title or category.name_en

    ticket = Ticket(
        public_code=generate_public_code(db, ward),
        reporter_id=reporter.id,
        category_id=category.id,
        title=title,
        description=data.description,
        description_lang=data.description_lang,
        latitude=data.latitude,
        longitude=data.longitude,
        address_text=data.address_text,
        ward_id=ward.id,
        municipality_id=ward.municipality_id,
        status=TicketStatus.REPORTED,
        embedding=embedding,
        predicted_category_key=predicted_key,
        category_confidence=confidence,
    )
    apply_priority(ticket, category)
    db.add(ticket)
    db.flush()

    for storage_path, phash, width, height in photos or []:
        db.add(
            TicketPhoto(
                ticket_id=ticket.id,
                storage_path=storage_path,
                phash=phash,
                width=width,
                height=height,
            )
        )
    db.flush()
    db.refresh(ticket)

    _record_status(db, ticket, None, TicketStatus.REPORTED, reporter.id, "Reported")

    candidates = find_duplicate_candidates(db, ticket, category)
    return ticket, candidates


# ---------------------------------------------------------------- queries


def scope_filter(profile: Profile):
    """Restrict a ticket query to what this profile may see.

    Citizens see everything in their municipality (they need to find and
    corroborate neighbours' reports). Authorities are confined to their ward
    when they have one, their municipality otherwise. Admins see all.
    """
    if profile.role is UserRole.ADMIN:
        return []

    if profile.role is UserRole.AUTHORITY:
        if profile.ward_id is not None:
            return [Ticket.ward_id == profile.ward_id]
        if profile.municipality_id is not None:
            return [Ticket.municipality_id == profile.municipality_id]
        return [Ticket.id.is_(None)]  # unscoped authority sees nothing

    if profile.municipality_id is not None:
        return [Ticket.municipality_id == profile.municipality_id]
    return []


def can_view_ticket(profile: Profile, ticket: Ticket) -> bool:
    """Whether this profile is inside the ticket's audience.

    The single-row twin of `scope_filter`, for the endpoints that already
    have one ticket in hand -- reading it directly, and reading or posting
    its comments -- and need a yes/no instead of a WHERE clause. Keep the two
    in sync: this is the same rule, just checked against a row instead of
    applied to a query.
    """
    if profile.role is UserRole.ADMIN:
        return True

    if profile.role is UserRole.AUTHORITY:
        if profile.ward_id is not None:
            return ticket.ward_id == profile.ward_id
        if profile.municipality_id is not None:
            return ticket.municipality_id == profile.municipality_id
        return False

    if profile.municipality_id is not None:
        return ticket.municipality_id == profile.municipality_id
    return True


def get_ticket(db: Session, ticket_id: UUID) -> Ticket:
    # Deliberately lean: one query (ward and municipality are joined in).
    # Photos and children load on first access, and most callers -- comments,
    # status changes -- never touch them.
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such ticket."
        )
    return ticket


# ---------------------------------------------------------------- merging


def merge_tickets(
    db: Session,
    authority: Profile,
    child: Ticket,
    parent_id: UUID,
    note: str | None = None,
) -> Ticket:
    """An authority folds `child` under `parent`."""
    if child.id == parent_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A ticket cannot be merged into itself.",
        )

    parent = get_ticket(db, parent_id)
    assert_can_access_ward(authority, parent.ward_id)
    assert_can_access_ward(authority, child.ward_id)

    if parent.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{parent.public_code} is itself a duplicate. "
                "Merge into its parent instead."
            ),
        )

    if child.children:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{child.public_code} already has {len(child.children)} duplicates "
                "under it. Split them out before merging it."
            ),
        )

    _fold_under(
        db, child, parent, authority.id, note or f"Merged into {parent.public_code}"
    )
    return parent


def auto_merge_if_confident(
    db: Session, ticket: Ticket, candidates: list[DuplicateCandidate]
) -> tuple[Ticket, DuplicateCandidate] | None:
    """Merge a fresh report under its best match when the matcher is sure.

    At or above `dedupe_auto_merge_score` the officer would click "merge"
    every time, so making them do it only delays the reporter count and the
    priority bump that merging brings. Below it, the suggestion waits for a
    human. Either way `split_ticket` undoes it.

    Returns (parent, the winning suggestion), or None if nothing was merged.
    """
    if ticket.parent_id is not None or not candidates:
        return None

    threshold = get_settings().dedupe_auto_merge_score
    for best in sorted(candidates, key=lambda c: c.score, reverse=True):
        if best.score < threshold:
            return None

        parent = db.get(Ticket, best.candidate_ticket_id)
        # The candidate query already guarantees these; re-check because the
        # parent may have closed or been merged since the suggestion was made.
        if (
            parent is None
            or parent.parent_id is not None
            or parent.status not in OPEN_STATUSES
        ):
            continue
        # Never fold someone's report into their own. Several reports filed
        # together from one spot are several problems -- that is why they
        # were filed separately. If it really is a repeat, the suggestion is
        # still there for an officer to merge.
        if parent.reporter_id == ticket.reporter_id:
            continue
        # Only merge on its own inside the category's true radius. Pairs in
        # the GPS-slack band beyond it are suggestions for a human to judge.
        radius = category_radii(db).get(parent.category_id)
        if radius is not None and best.distance_m > radius:
            continue
        break
    else:
        return None

    _fold_under(
        db,
        ticket,
        parent,
        None,
        f"Automatically merged into {parent.public_code} ({best.score:.0%} match)",
    )
    return parent, best


def _fold_under(
    db: Session,
    child: Ticket,
    parent: Ticket,
    actor_id: UUID | None,
    note: str,
) -> None:
    """Make `child` a duplicate of `parent`. The only place parent_id is set.

    Callers do the permission and shape checks; `actor_id` is None when the
    matcher merged on its own.
    """
    previous_status = child.status
    child.parent_id = parent.id
    child.status = TicketStatus.MERGED

    parent.child_count = (parent.child_count or 0) + 1
    category = db.get(Category, parent.category_id)
    if category is not None:
        apply_priority(parent, category)

    # Close out the suggestion that led here, and drop the rest.
    db.query(DuplicateCandidate).filter(
        DuplicateCandidate.ticket_id == child.id,
        DuplicateCandidate.candidate_ticket_id == parent.id,
    ).update(
        {
            "status": CandidateStatus.MERGED,
            "reviewed_by_id": actor_id,
            "reviewed_at": _now(),
        }
    )
    db.query(DuplicateCandidate).filter(
        DuplicateCandidate.ticket_id == child.id,
        DuplicateCandidate.candidate_ticket_id != parent.id,
        DuplicateCandidate.status == CandidateStatus.PENDING,
    ).update(
        {
            "status": CandidateStatus.REJECTED,
            "reviewed_by_id": actor_id,
            "reviewed_at": _now(),
        }
    )

    _record_status(db, child, previous_status, TicketStatus.MERGED, actor_id, note)

    _notify(
        db,
        child.reporter_id,
        NotificationType.TICKET_MERGED,
        "Your report was linked to an existing one",
        "तपाईंको उजुरी विद्यमान उजुरीसँग जोडियो",
        f"Your report is now tracked under {parent.public_code}. "
        f"It now has {parent.child_count + 1} reporters.",
        ticket_id=parent.id,
    )

    db.flush()


def split_ticket(db: Session, authority: Profile, child: Ticket) -> Ticket:
    """Undo a merge. Wrong merges must be reversible or nobody will merge."""
    if child.parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This ticket is not a duplicate of anything.",
        )

    parent = db.get(Ticket, child.parent_id)
    assert_can_access_ward(authority, child.ward_id)

    child.parent_id = None
    child.status = TicketStatus.REPORTED

    if parent is not None:
        parent.child_count = max(0, (parent.child_count or 0) - 1)
        category = db.get(Category, parent.category_id)
        if category is not None:
            apply_priority(parent, category)

    _record_status(
        db,
        child,
        TicketStatus.MERGED,
        TicketStatus.REPORTED,
        authority.id,
        "Split out from parent",
    )
    db.flush()
    return child


def reject_candidate(
    db: Session, authority: Profile, candidate: DuplicateCandidate
) -> DuplicateCandidate:
    candidate.status = CandidateStatus.REJECTED
    candidate.reviewed_by_id = authority.id
    candidate.reviewed_at = _now()
    db.flush()
    return candidate


# ------------------------------------------------------------ status flow


def update_status(
    db: Session,
    authority: Profile,
    ticket: Ticket,
    new_status: TicketStatus,
    note: str | None = None,
    resolution_note: str | None = None,
) -> Ticket:
    assert_can_access_ward(authority, ticket.ward_id)

    if ticket.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This ticket is a duplicate; it follows its parent. "
                "Update the parent instead."
            ),
        )

    allowed = ALLOWED_TRANSITIONS.get(ticket.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move from {ticket.status.value} to {new_status.value}. "
                f"Allowed: {', '.join(sorted(s.value for s in allowed)) or 'none'}."
            ),
        )

    previous = ticket.status
    ticket.status = new_status

    if new_status is TicketStatus.VERIFIED:
        ticket.verified_at = _now()
    if new_status is TicketStatus.RESOLVED:
        ticket.resolved_at = _now()
        ticket.resolution_note = resolution_note or note

    _record_status(db, ticket, previous, new_status, authority.id, note)

    # Resolving a parent resolves the whole tree and tells everyone who
    # reported it. This fan-out is the payoff for merging duplicates.
    recipients = {ticket.reporter_id}
    if new_status is TicketStatus.RESOLVED:
        children = db.scalars(
            select(Ticket).where(Ticket.parent_id == ticket.id)
        ).all()
        for child in children:
            child.status = TicketStatus.RESOLVED
            child.resolved_at = ticket.resolved_at
            child.resolution_note = ticket.resolution_note
            _record_status(
                db,
                child,
                TicketStatus.MERGED,
                TicketStatus.RESOLVED,
                authority.id,
                f"Resolved with parent {ticket.public_code}",
            )
            recipients.add(child.reporter_id)

    notification_type = (
        NotificationType.TICKET_RESOLVED
        if new_status is TicketStatus.RESOLVED
        else NotificationType.TICKET_STATUS_CHANGED
    )
    for recipient in recipients:
        _notify(
            db,
            recipient,
            notification_type,
            f"{ticket.public_code} is now {new_status.value.replace('_', ' ')}",
            f"{ticket.public_code} अब {new_status.value} भयो",
            ticket.resolution_note or note,
            ticket_id=ticket.id,
        )

    db.flush()
    return ticket


def reassign_ward(
    db: Session,
    actor: Profile,
    ticket: Ticket,
    ward_id: UUID,
) -> Ticket:
    """Move a ticket to a different ward.

    Routing is by GPS, and GPS is imperfect -- a report near a ward boundary,
    or taken indoors, lands next door. Without this the ticket is invisible to
    the office that should handle it and there is no way to fix it.

    A ward-scoped officer can hand a ticket away but cannot pull one in; that
    would let any officer reach into a neighbouring ward.
    """
    target = db.get(Ward, ward_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown ward.",
        )

    if target.municipality_id != ticket.municipality_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A ticket cannot be moved to a different municipality.",
        )

    # You must already have authority over the ticket to move it.
    assert_can_access_ward(actor, ticket.ward_id)

    previous = ticket.ward

    # Set the relationship, not just the foreign key. Assigning ward_id alone
    # leaves the already-loaded `ward` object in place, so the response echoes
    # the old ward even though the row has moved.
    ticket.ward = target
    ticket.ward_id = target.id

    _record_status(
        db,
        ticket,
        ticket.status,
        ticket.status,
        actor.id,
        f"Reassigned from ward {previous.number if previous else '?'} "
        f"to ward {target.number}",
    )

    db.flush()
    return ticket


def assign_ticket(
    db: Session,
    authority: Profile,
    ticket: Ticket,
    assigned_to_id: UUID | None,
    priority: TicketPriority | None,
) -> Ticket:
    assert_can_access_ward(authority, ticket.ward_id)

    if assigned_to_id is not None:
        assignee = db.get(Profile, assigned_to_id)
        if assignee is None or not assignee.is_authority:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tickets can only be assigned to an authority account.",
            )
        ticket.assigned_to_id = assignee.id
    else:
        ticket.assigned_to_id = None

    if priority is not None:
        set_priority(db, authority, ticket, priority)

    db.flush()
    return ticket


# -------------------------------------------------------------- priority


def set_priority(
    db: Session,
    actor: Profile,
    ticket: Ticket,
    priority: TicketPriority | None,
    note: str | None = None,
) -> Ticket:
    """Override priority by hand, or hand it back to automation.

    `priority=None` clears the lock and recomputes, which is the only way back:
    an override with no exit is a trap, and an officer who over-escalated one
    ticket in a busy week should be able to undo it.

    Ward isolation still applies -- an officer can re-prioritise their own
    ward's tickets, an admin anyone's.
    """
    assert_can_access_ward(actor, ticket.ward_id)

    if ticket.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This ticket is a duplicate; it follows its parent. "
                "Set the priority on the parent instead."
            ),
        )

    previous = ticket.priority

    if priority is None:
        ticket.priority_locked = False
        ticket.priority_set_by_id = None
        ticket.priority_set_at = None
        ticket.priority_note = None

        category = db.get(Category, ticket.category_id)
        if category is not None:
            apply_priority(ticket, category)

        detail = f"Priority returned to automatic ({ticket.priority.value})"
    else:
        ticket.priority = priority
        ticket.priority_locked = True
        ticket.priority_set_by_id = actor.id
        ticket.priority_set_at = _now()
        ticket.priority_note = note
        detail = f"Priority set to {priority.value} by hand"

    if ticket.priority is not previous or priority is not None:
        _record_status(
            db,
            ticket,
            ticket.status,
            ticket.status,
            actor.id,
            f"{detail}{f' -- {note}' if note else ''}",
        )

    db.flush()
    return ticket


# The sweep is throttled per process rather than scheduled. A cron or a
# background worker would be the right answer in production; for a system
# running on one box, recomputing on read is correct the moment anyone looks
# and costs nothing when nobody does.
_ESCALATION_SWEEP_INTERVAL = timedelta(minutes=5)
_last_escalation_sweep: datetime | None = None


def sweep_escalations(db: Session, force: bool = False) -> int:
    """Re-apply the age ladder to every open, unlocked ticket.

    Returns how many tickets actually moved. Without this, a ticket sitting
    untouched for a week would never escalate -- nothing writes to it, and
    being untouched is precisely the condition escalation exists to catch.
    """
    global _last_escalation_sweep

    now = _now()
    if (
        not force
        and _last_escalation_sweep is not None
        and now - _last_escalation_sweep < _ESCALATION_SWEEP_INTERVAL
    ):
        return 0
    _last_escalation_sweep = now

    settings = get_settings()
    oldest_relevant = now - timedelta(
        days=min(
            settings.escalate_low_to_medium_days,
            settings.escalate_medium_to_high_days,
        )
    )

    tickets = db.scalars(
        select(Ticket).where(
            Ticket.status.in_(OPEN_STATUSES),
            Ticket.priority_locked.is_(False),
            Ticket.parent_id.is_(None),
            Ticket.created_at <= oldest_relevant,
        )
    ).all()
    if not tickets:
        return 0

    categories = {c.id: c for c in db.scalars(select(Category)).all()}

    moved = 0
    for ticket in tickets:
        category = categories.get(ticket.category_id)
        if category is None:
            continue

        previous = ticket.priority
        if apply_priority(ticket, category) is not previous:
            moved += 1
            _record_status(
                db,
                ticket,
                ticket.status,
                ticket.status,
                None,
                (
                    f"Priority escalated {previous.value} -> "
                    f"{ticket.priority.value} after "
                    f"{(now - ticket.created_at).days} days unresolved"
                ),
            )

    if moved:
        db.flush()
    return moved


# ----------------------------------------------------------- corroboration


def corroborate(
    db: Session,
    citizen: Profile,
    ticket: Ticket,
    is_confirmed: bool,
    latitude: float,
    longitude: float,
    note: str | None = None,
) -> tuple[Ticket, float]:
    """Record a nearby citizen's confirmation that a report is real.

    Three guards, all necessary: you cannot vouch for your own report, you
    cannot vote twice, and you must actually be at the location. Without the
    last one this is just an upvote button.
    """
    if ticket.reporter_id == citizen.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot corroborate your own report.",
        )

    existing = db.scalar(
        select(TicketCorroboration).where(
            TicketCorroboration.ticket_id == ticket.id,
            TicketCorroboration.citizen_id == citizen.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already responded to this report.",
        )

    category = db.get(Category, ticket.category_id)
    radius = category.match_radius_m if category else 100
    # Allow a little slack for GPS drift in dense urban areas.
    allowed = max(radius * 2, 150)

    distance = haversine_m(latitude, longitude, ticket.latitude, ticket.longitude)
    if distance > allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You are {distance:.0f}m away. You must be within {allowed}m "
                "of the reported location to confirm it."
            ),
        )

    db.add(
        TicketCorroboration(
            ticket_id=ticket.id,
            citizen_id=citizen.id,
            is_confirmed=is_confirmed,
            latitude=latitude,
            longitude=longitude,
            distance_m=distance,
            note=note,
        )
    )

    if is_confirmed:
        ticket.corroboration_count = (ticket.corroboration_count or 0) + 1
    else:
        ticket.dispute_count = (ticket.dispute_count or 0) + 1

    settings = get_settings()
    became_verified = (
        not ticket.community_verified
        and ticket.corroboration_count >= settings.corroboration_threshold
    )
    if became_verified:
        ticket.community_verified = True

    if category is not None:
        apply_priority(ticket, category)

    if is_confirmed:
        _notify(
            db,
            ticket.reporter_id,
            NotificationType.TICKET_CORROBORATED,
            f"A neighbour confirmed {ticket.public_code}",
            f"छिमेकीले {ticket.public_code} पुष्टि गर्नुभयो",
            f"{ticket.corroboration_count} people nearby have now confirmed this.",
            ticket_id=ticket.id,
        )

    db.flush()
    return ticket, distance


# --------------------------------------------------------------- comments


def add_comment(db: Session, author: Profile, ticket: Ticket, body: str) -> TicketComment:
    """Post to a ticket's discussion thread.

    Anyone who can view the ticket can post -- same audience as `can_view_ticket`,
    which is the whole point of a public thread instead of a private one.
    A child ticket has no thread of its own; it follows its parent, same as
    status.
    """
    if not can_view_ticket(author, ticket):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this report.",
        )

    if ticket.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This ticket is a duplicate; it follows its parent. "
                "Comment on the parent instead."
            ),
        )

    comment = TicketComment(
        ticket_id=ticket.id,
        author_id=author.id,
        body=body,
        is_urgent=is_urgent(body),
    )
    db.add(comment)
    db.flush()

    if comment.is_urgent:
        refresh_comment_urgency(db, ticket)

    # Notify the people actually responsible for this ticket, not everyone in
    # the municipality who happens to be able to see it -- the thread is
    # public, but a notification for every viewer would be spam.
    notify_ids = {ticket.reporter_id, ticket.assigned_to_id} - {author.id, None}
    for user_id in notify_ids:
        _notify(
            db,
            user_id,
            NotificationType.TICKET_COMMENTED,
            f"New comment on {ticket.public_code}",
            f"{ticket.public_code} मा नयाँ टिप्पणी",
            body[:200],
            ticket_id=ticket.id,
        )

    return comment


def list_comments(
    db: Session, viewer: Profile, ticket: Ticket, limit: int = 100, offset: int = 0
) -> tuple[list[TicketComment], int]:
    if not can_view_ticket(viewer, ticket):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this report.",
        )

    rows = list(
        db.scalars(
            select(TicketComment)
            .where(TicketComment.ticket_id == ticket.id)
            .order_by(TicketComment.created_at)
            .limit(limit)
            .offset(offset)
        ).all()
    )

    # A page that came back short is the whole remainder, so the total is
    # known without a second round trip to count.
    if len(rows) < limit:
        return rows, offset + len(rows)

    total = (
        db.scalar(
            select(func.count())
            .select_from(TicketComment)
            .where(TicketComment.ticket_id == ticket.id)
        )
        or 0
    )
    return rows, total


def delete_comment(
    db: Session, actor: Profile, ticket: Ticket, comment: TicketComment
) -> None:
    """Remove a comment: its own author, or the ward authority moderating it.

    Ward isolation still applies to the moderation path -- an authority can
    only reach into threads on tickets it can already act on.
    """
    if comment.ticket_id != ticket.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such comment."
        )

    is_own = comment.author_id == actor.id
    if not is_own:
        assert_can_access_ward(actor, ticket.ward_id)

    was_urgent = comment.is_urgent
    db.delete(comment)
    db.flush()

    # The pressure has to come off again, or deleting three "urgent!" posts
    # would leave the ticket bumped with no visible reason.
    if was_urgent:
        refresh_comment_urgency(db, ticket)


def refresh_comment_urgency(db: Session, ticket: Ticket) -> None:
    """Recount distinct citizens pressing for a fix and re-score the ticket.

    Counted from the rows every time rather than incremented, so a deleted
    comment, or one person posting "urgent" five times, both come out right.
    Only citizens count: an officer writing "we will fix this immediately" is
    an answer to the pressure, not more of it.
    """
    count = (
        db.scalar(
            select(func.count(func.distinct(TicketComment.author_id)))
            .join(Profile, Profile.id == TicketComment.author_id)
            .where(
                TicketComment.ticket_id == ticket.id,
                TicketComment.is_urgent.is_(True),
                Profile.role == UserRole.CITIZEN,
            )
        )
        or 0
    )
    ticket.urgent_commenter_count = count

    category = db.get(Category, ticket.category_id)
    if category is None:
        return

    previous = ticket.priority
    apply_priority(ticket, category)
    if ticket.priority is previous:
        db.flush()
        return

    raised = PRIORITY_RANK[ticket.priority] > PRIORITY_RANK[previous]
    people = "person" if count == 1 else "people"
    _record_status(
        db,
        ticket,
        ticket.status,
        ticket.status,
        None,
        (
            f"Priority {'raised' if raised else 'lowered'} {previous.value} -> "
            f"{ticket.priority.value}: {count} {people} asked in the comments for it to be fixed"
        ),
    )

    if raised and ticket.assigned_to_id is not None:
        _notify(
            db,
            ticket.assigned_to_id,
            NotificationType.TICKET_STATUS_CHANGED,
            f"{ticket.public_code} is now {ticket.priority.value} priority",
            f"{ticket.public_code} अब {ticket.priority.value} प्राथमिकतामा",
            f"{count} people have asked in the comments for this to be fixed.",
            ticket_id=ticket.id,
        )
    db.flush()
