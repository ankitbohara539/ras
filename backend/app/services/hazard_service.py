"""Hazards on the street, and routes around them.

A hazard is anything reported that makes a stretch of street dangerous or
impassable *for someone*: a flooded road stops everyone, a broken footpath
stops a wheelchair but not a car, a dead streetlight only matters after dark.
They come from two places:

  - open tickets in hazard categories (a citizen reported it), and
  - active public alerts (an authority declared an area dangerous).

Everything here is a best guess from reports that may be hours old. The API
says so on every route it returns, and nothing in this module claims a route
is safe -- only that it passes fewer *reported* hazards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.geo import haversine_m
from app.models.emergency import Alert
from app.models.enums import AlertSeverity, AlertTargetType, TicketPriority, TicketStatus
from app.models.ticket import Ticket
from app.services.ticket_service import category_keys, ward_index

WALK, WHEELCHAIR, DRIVE = "walk", "wheelchair", "drive"
ALL_MODES = frozenset({WALK, WHEELCHAIR, DRIVE})

NEPAL_TIME = timezone(timedelta(hours=5, minutes=45))
OPEN = (TicketStatus.REPORTED, TicketStatus.VERIFIED, TicketStatus.IN_PROGRESS)

# A ward-wide alert has no exact shape here (ward boundaries are not stored),
# so it is drawn as a circle around the ward's centre and marked approximate.
WARD_ALERT_RADIUS_M = 800


@dataclass(frozen=True)
class Rule:
    kind: str
    radius_m: int
    severity: str  # "low" | "medium" | "high"
    modes: frozenset[str]
    night_only: bool = False


# Which ticket categories are hazards, and to whom.
RULES: dict[str, Rule] = {
    "waterlogging": Rule("flooding", 150, "high", ALL_MODES),
    "road_blocked": Rule("blocked_road", 80, "high", ALL_MODES),
    "electricity": Rule("electrical", 60, "high", ALL_MODES),
    "street_light": Rule("dark_street", 80, "medium", frozenset({WALK, WHEELCHAIR}), night_only=True),
    "drainage": Rule("open_drain", 40, "medium", frozenset({WALK, WHEELCHAIR})),
    "footpath_damage": Rule("damaged_footpath", 40, "medium", frozenset({WALK, WHEELCHAIR})),
    "accessibility_barrier": Rule("wheelchair_barrier", 30, "high", frozenset({WHEELCHAIR})),
    "pothole": Rule("road_damage", 30, "low", frozenset({DRIVE, WHEELCHAIR})),
}

SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 4}


@dataclass
class Hazard:
    id: str
    source: str  # "ticket" | "alert"
    kind: str
    title: str
    severity: str
    latitude: float
    longitude: float
    radius_m: int
    modes: frozenset[str]
    night_only: bool
    active_now: bool
    # Routes are steered around it. Night-only hazards in daytime, and
    # alerts below critical, are shown but not avoided.
    avoid: bool
    approximate: bool = False
    reported_at: datetime | None = None
    reports: int = 1
    confirmations: int = 0
    ticket_id: UUID | None = None
    alert_id: UUID | None = None
    category_key: str | None = None
    extra: dict = field(default_factory=dict)


def is_night(at: datetime | None = None) -> bool:
    """After dark in Nepal: 18:00 to 06:00 local time."""
    local = (at or datetime.now(UTC)).astimezone(NEPAL_TIME)
    return local.hour >= 18 or local.hour < 6


def list_hazards(
    db: Session,
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    night: bool | None = None,
) -> list[Hazard]:
    """Every current hazard whose centre falls inside the box."""
    night = is_night() if night is None else night
    hazards: list[Hazard] = []

    # Reference data from the in-process cache; the hazards themselves are
    # always read fresh below.
    categories = {cid: key for cid, key in category_keys(db).items() if key in RULES}
    if categories:
        tickets = db.scalars(
            select(Ticket).where(
                Ticket.category_id.in_(list(categories)),
                Ticket.status.in_(OPEN),
                Ticket.parent_id.is_(None),
                Ticket.latitude.between(min_lat, max_lat),
                Ticket.longitude.between(min_lon, max_lon),
            )
        ).all()
        for ticket in tickets:
            key = categories[ticket.category_id]
            rule = RULES[key]
            severity = rule.severity
            # An officer-escalated or widely-reported one is treated as serious.
            if ticket.priority in (TicketPriority.HIGH, TicketPriority.CRITICAL):
                severity = "high"
            active = night or not rule.night_only
            hazards.append(
                Hazard(
                    id=f"ticket:{ticket.id}",
                    source="ticket",
                    kind=rule.kind,
                    title=ticket.title,
                    severity=severity,
                    latitude=ticket.latitude,
                    longitude=ticket.longitude,
                    radius_m=rule.radius_m,
                    modes=rule.modes,
                    night_only=rule.night_only,
                    active_now=active,
                    avoid=active,
                    reported_at=ticket.created_at,
                    reports=(ticket.child_count or 0) + 1,
                    confirmations=ticket.corroboration_count or 0,
                    ticket_id=ticket.id,
                    category_key=key,
                )
            )

    now = datetime.now(UTC)
    alerts = db.scalars(
        select(Alert).where(
            Alert.is_active.is_(True),
            Alert.severity.in_([AlertSeverity.CRITICAL, AlertSeverity.WARNING]),
            or_(Alert.expires_at.is_(None), Alert.expires_at > now),
            or_(Alert.starts_at.is_(None), Alert.starts_at <= now),
        )
    ).all()
    wards = {w.id: w for w in ward_index(db)} if alerts else {}

    for alert in alerts:
        critical = alert.severity is AlertSeverity.CRITICAL
        areas: list[tuple[float, float, int, bool]] = []
        if alert.target_type is AlertTargetType.RADIUS and alert.center_lat is not None:
            areas.append((alert.center_lat, alert.center_lon, alert.radius_m or 500, False))
        elif alert.target_type is AlertTargetType.WARD:
            for ward_id in alert.ward_ids or []:
                ward = wards.get(ward_id)
                if ward is not None:
                    areas.append(
                        (ward.centroid_lat, ward.centroid_lon, WARD_ALERT_RADIUS_M, True)
                    )

        for index, (lat, lon, radius, approximate) in enumerate(areas):
            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                continue
            hazards.append(
                Hazard(
                    id=f"alert:{alert.id}:{index}",
                    source="alert",
                    kind="alert_area",
                    title=alert.title_en,
                    severity="high" if critical else "medium",
                    latitude=lat,
                    longitude=lon,
                    radius_m=int(radius),
                    modes=ALL_MODES,
                    night_only=False,
                    active_now=True,
                    # Only a critical alert re-routes people; a warning is
                    # shown so they can decide for themselves.
                    avoid=critical,
                    approximate=approximate,
                    reported_at=alert.created_at,
                    alert_id=alert.id,
                )
            )

    return hazards


# ------------------------------------------------------------ geometry


def _to_xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    """Local flat projection in metres -- fine at city scale."""
    return (
        math.radians(lon) * 6_371_000 * math.cos(math.radians(lat0)),
        math.radians(lat) * 6_371_000,
    )


def distance_to_line_m(lat: float, lon: float, line: list[tuple[float, float]]) -> float:
    """Shortest distance from a point to a polyline of (lat, lon) points."""
    if not line:
        return math.inf
    if len(line) == 1:
        return haversine_m(lat, lon, line[0][0], line[0][1])

    px, py = _to_xy(lat, lon, lat)
    best = math.inf
    for (a_lat, a_lon), (b_lat, b_lon) in zip(line, line[1:]):
        ax, ay = _to_xy(a_lat, a_lon, lat)
        bx, by = _to_xy(b_lat, b_lon, lat)
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
        cx, cy = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(px - cx, py - cy))
    return best


# Slack added to a hazard's radius when deciding whether a route passes it:
# GPS error in the report plus the width of the street.
ON_ROUTE_SLACK_M = 20


def hazards_on_route(
    line: list[tuple[float, float]], hazards: list[Hazard]
) -> list[Hazard]:
    return [
        h
        for h in hazards
        if distance_to_line_m(h.latitude, h.longitude, line) <= h.radius_m + ON_ROUTE_SLACK_M
    ]


def risk_score(hazards: list[Hazard]) -> int:
    return sum(SEVERITY_WEIGHT.get(h.severity, 1) for h in hazards)


def circle_polygon(lat: float, lon: float, radius_m: float, sides: int = 12) -> list[list[float]]:
    """A closed ring of [lon, lat] points approximating a circle (GeoJSON order)."""
    ring = []
    for i in range(sides):
        angle = 2 * math.pi * i / sides
        d_lat = (radius_m * math.cos(angle)) / 111_320
        d_lon = (radius_m * math.sin(angle)) / (111_320 * math.cos(math.radians(lat)))
        ring.append([round(lon + d_lon, 6), round(lat + d_lat, 6)])
    ring.append(ring[0])
    return ring


def contains(h: Hazard, lat: float, lon: float) -> bool:
    return haversine_m(lat, lon, h.latitude, h.longitude) <= h.radius_m
