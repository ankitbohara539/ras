"""The safer-route planner: the usual route, and one around reported hazards.

Never claims a route is safe. It compares the usual route with one that
steers around hazard areas, recommends whichever passes fewer and less
serious *reported* hazards, and says in plain words what it could not avoid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.routing import NO_ROUTE_CODES, Route, RoutingError, directions, provider
from app.services.hazard_service import (
    ON_ROUTE_SLACK_M,
    Hazard,
    circle_polygon,
    contains,
    hazards_on_route,
    is_night,
    list_hazards,
    risk_score,
)

# How far beyond the start/end box to look for hazards (~1.1 km).
SEARCH_PAD_DEG = 0.01
# ORS rejects very large avoid sets; the nearest hazards matter most anyway.
MAX_AVOID = 40

DISCLAIMER = (
    "Based on citizen reports and alerts, which can be out of date. Conditions "
    "change quickly -- use your own judgement on the way. In an emergency call "
    "100 (police), 101 (fire) or 102 (ambulance)."
)


@dataclass
class PlannedRoute:
    route: Route
    hazards: list[Hazard]

    @property
    def risk(self) -> int:
        return risk_score(self.hazards)


@dataclass
class Plan:
    mode: str
    profile_used: str
    night: bool
    fastest: PlannedRoute
    safer: PlannedRoute | None
    recommended: str  # "fastest" | "safer"
    hazards: list[Hazard]
    notes: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def plan(
    db: Session,
    start: tuple[float, float],
    end: tuple[float, float],
    mode: str,
    night: bool | None = None,
) -> Plan:
    night = is_night() if night is None else night
    notes: list[str] = []

    box = (
        min(start[0], end[0]) - SEARCH_PAD_DEG,
        min(start[1], end[1]) - SEARCH_PAD_DEG,
        max(start[0], end[0]) + SEARCH_PAD_DEG,
        max(start[1], end[1]) + SEARCH_PAD_DEG,
    )
    everything = list_hazards(db, *box, night=night)
    relevant = [h for h in everything if mode in h.modes and h.active_now]

    # The usual route. Wheelchair routing needs sidewalk data OSM often lacks
    # here; fall back to walking and still avoid wheelchair barriers.
    profile = mode
    basic = provider() == "osrm"
    if basic and mode == "wheelchair":
        profile = "walk"
        notes.append(
            "Wheelchair routing needs the full routing service; this is a walking route "
            "that avoids reported wheelchair barriers. Check kerbs and steps on the way."
        )
    try:
        fastest = directions(profile, start, end)
    except RoutingError as exc:
        if mode != "wheelchair" or exc.code not in NO_ROUTE_CODES:
            raise
        profile = "walk"
        notes.append(
            "There is not enough accessibility data here for a wheelchair route, so this "
            "is a walking route that still avoids reported wheelchair barriers. Check kerbs "
            "and steps on the way."
        )
        fastest = directions(profile, start, end)

    fastest_hazards = hazards_on_route(fastest.line, relevant)

    # A hazard covering the start or the destination cannot be routed around.
    at_endpoint = [h for h in relevant if contains(h, *start) or contains(h, *end)]
    if at_endpoint:
        notes.append(
            "Your start or destination is inside a reported hazard area "
            f"({', '.join(sorted({h.title for h in at_endpoint}))}). Take extra care there."
        )

    endpoint_ids = {h.id for h in at_endpoint}
    to_avoid = [h for h in fastest_hazards if h.avoid and h.id not in endpoint_ids]

    safer: PlannedRoute | None = None
    if to_avoid:
        # Two passes: steering around one hazard can lead past another.
        for _ in range(2):
            rings = [
                circle_polygon(h.latitude, h.longitude, h.radius_m + ON_ROUTE_SLACK_M)
                for h in to_avoid[:MAX_AVOID]
            ]
            try:
                route = directions(profile, start, end, rings)
            except RoutingError as exc:
                if exc.code not in NO_ROUTE_CODES:
                    raise
                notes.append(
                    "No way around every reported hazard was found. The usual route is shown; "
                    "take care at the marked spots."
                )
                break

            safer = PlannedRoute(route, hazards_on_route(route.line, relevant))
            avoid_ids = {h.id for h in to_avoid}
            new = [
                h
                for h in safer.hazards
                if h.avoid and h.id not in avoid_ids and h.id not in endpoint_ids
            ]
            if not new:
                break
            to_avoid += new

    fast_plan = PlannedRoute(fastest, fastest_hazards)
    recommended = "fastest"
    if safer is not None and safer.risk < fast_plan.risk:
        recommended = "safer"
        extra_min = max(0, round((safer.route.duration_s - fastest.duration_s) / 60))
        notes.insert(
            0,
            f"The suggested route avoids {len(fastest_hazards) - len(safer.hazards)} "
            f"reported hazard(s)"
            + (f" and takes about {extra_min} min longer." if extra_min else "."),
        )
    elif safer is not None:
        safer = None  # it did not actually help; do not offer it
    if not fastest_hazards:
        notes.insert(0, "No reported hazards on this route right now.")
    if basic and fastest_hazards:
        notes.append(
            "Basic routing is in use, so detours are limited to nearby alternative streets."
        )
    if night and mode in ("walk", "wheelchair"):
        notes.append("It is dark: streets with broken streetlights are treated as hazards.")

    return Plan(
        mode=mode,
        profile_used=profile,
        night=night,
        fastest=fast_plan,
        safer=safer,
        recommended=recommended,
        hazards=everything,
        notes=notes,
    )
