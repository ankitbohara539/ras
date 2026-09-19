"""Aggregate numbers for the public transparency page.

Every ticket query here filters `parent_id IS NULL`. A merged duplicate's
resolution time belongs to its parent -- the ticket the office actually
worked -- so counting both would double the total and skew the median
toward whatever category happens to attract the most duplicates.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import TicketStatus
from app.models.geography import Municipality, Ward
from app.models.ticket import Ticket
from app.schema.public import CategoryStat, PublicStatsResponse, WardStat

OPEN_STATUSES = (TicketStatus.REPORTED, TicketStatus.VERIFIED, TicketStatus.IN_PROGRESS)


def median_hours(durations_hours: list[float]) -> float | None:
    """The median of a list of resolution times, or None with no data yet.

    Pulled out as a pure function so it can be tested without a database --
    the interesting bugs here are off-by-ones on empty and single-item lists,
    not anything that needs a session.
    """
    if not durations_hours:
        return None
    return round(statistics.median(durations_hours), 1)


def _start_of_month(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class _Row:
    __slots__ = ("category_id", "ward_id", "status", "duration_hours")

    def __init__(self, category_id: UUID, ward_id: UUID, ticket_status: TicketStatus, duration_hours: float | None):
        self.category_id = category_id
        self.ward_id = ward_id
        self.status = ticket_status
        self.duration_hours = duration_hours


def compute_public_stats(db: Session, municipality_code: str) -> PublicStatsResponse:
    municipality = db.scalar(
        select(Municipality).where(Municipality.code == municipality_code)
    )
    if municipality is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No municipality with code {municipality_code}.",
        )

    now = datetime.now(UTC)
    month_start = _start_of_month(now)

    categories = db.scalars(select(Category).order_by(Category.sort_order)).all()
    wards = db.scalars(
        select(Ward).where(Ward.municipality_id == municipality.id).order_by(Ward.number)
    ).all()

    tickets = db.scalars(
        select(Ticket).where(
            Ticket.municipality_id == municipality.id,
            Ticket.parent_id.is_(None),
        )
    ).all()

    rows: list[_Row] = []
    resolved_this_month = 0
    for t in tickets:
        duration = None
        if t.status is TicketStatus.RESOLVED and t.resolved_at is not None:
            duration = (t.resolved_at - t.created_at).total_seconds() / 3600
            if t.resolved_at >= month_start:
                resolved_this_month += 1
        rows.append(_Row(t.category_id, t.ward_id, t.status, duration))

    def summarise(matching: list[_Row]) -> tuple[int, int, int, float | None]:
        total = len(matching)
        open_count = sum(1 for r in matching if r.status in OPEN_STATUSES)
        resolved = sum(1 for r in matching if r.status is TicketStatus.RESOLVED)
        durations = [r.duration_hours for r in matching if r.duration_hours is not None]
        return total, open_count, resolved, median_hours(durations)

    overall_total, overall_open, overall_resolved, overall_median = summarise(rows)

    by_category = []
    for cat in categories:
        matching = [r for r in rows if r.category_id == cat.id]
        total, _open, resolved, median = summarise(matching)
        by_category.append(
            CategoryStat(
                key=cat.key,
                name_en=cat.name_en,
                name_ne=cat.name_ne,
                total=total,
                resolved=resolved,
                median_resolution_hours=median,
            )
        )

    by_ward = []
    for ward in wards:
        matching = [r for r in rows if r.ward_id == ward.id]
        total, open_count, resolved, median = summarise(matching)
        by_ward.append(
            WardStat(
                number=ward.number,
                name_en=ward.name_en,
                name_ne=ward.name_ne,
                total=total,
                open=open_count,
                resolved=resolved,
                median_resolution_hours=median,
            )
        )

    return PublicStatsResponse(
        municipality_code=municipality.code,
        municipality_name_en=municipality.name_en,
        municipality_name_ne=municipality.name_ne,
        total_tickets=overall_total,
        open_tickets=overall_open,
        resolved_tickets=overall_resolved,
        resolved_this_month=resolved_this_month,
        median_resolution_hours=overall_median,
        by_category=by_category,
        by_ward=by_ward,
        generated_at=now,
    )
