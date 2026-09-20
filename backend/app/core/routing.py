"""Directions from OpenRouteService.

ORS rather than a keyless router because it has two things the hazard map
needs: a real wheelchair profile (kerbs, steps, surface) and `avoid_polygons`,
which routes around areas instead of merely preferring other roads.

Best with a free API key from openrouteservice.org (OPENROUTESERVICE_API_KEY).
Without one it falls back to the public OSRM servers -- see the bottom of
this module -- which work, but avoid hazards less precisely.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.geo import haversine_m

PROFILES = {
    "walk": "foot-walking",
    "wheelchair": "wheelchair",
    "drive": "driving-car",
}


class RoutingNotConfigured(Exception):
    pass


class RoutingError(Exception):
    """ORS could not produce a route. `code` is ORS's error code, if any."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


# ORS error codes that mean "no route with these constraints", as opposed to
# a bad request or an outage.
NO_ROUTE_CODES = {2009, 2010}


@dataclass
class Route:
    # (lat, lon) points, in travel order.
    line: list[tuple[float, float]]
    distance_m: float
    duration_s: float


def provider() -> str:
    """"ors" with a key, else "osrm" (the keyless fallback)."""
    return "ors" if get_settings().openrouteservice_api_key else "osrm"


def directions(
    mode: str,
    start: tuple[float, float],
    end: tuple[float, float],
    avoid_rings: list[list[list[float]]] | None = None,
) -> Route:
    """One route from start to end ((lat, lon) each), optionally avoiding areas.

    `avoid_rings` are closed [lon, lat] rings, as from
    hazard_service.circle_polygon.
    """
    settings = get_settings()
    if not settings.openrouteservice_api_key:
        return _osrm_directions(mode, start, end, avoid_rings)

    body: dict = {
        "coordinates": [[start[1], start[0]], [end[1], end[0]]],
        "instructions": False,
        "elevation": False,
    }
    if avoid_rings:
        body["options"] = {
            "avoid_polygons": {
                "type": "MultiPolygon",
                "coordinates": [[ring] for ring in avoid_rings],
            }
        }

    try:
        response = httpx.post(
            f"{settings.openrouteservice_url.rstrip('/')}/v2/directions/{PROFILES[mode]}/geojson",
            json=body,
            headers={
                "Authorization": settings.openrouteservice_api_key,
                "Accept": "application/geo+json, application/json",
            },
            timeout=settings.openrouteservice_timeout_s,
        )
    except httpx.HTTPError as exc:
        raise RoutingError(f"Could not reach the routing service: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RoutingError(f"Routing service answered {response.status_code}.") from exc

    if response.status_code != 200:
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            raise RoutingError(str(error.get("message") or error), error.get("code"))
        raise RoutingError(str(error or f"Routing service answered {response.status_code}."))

    features = payload.get("features") or []
    if not features:
        raise RoutingError("No route found.", 2009)

    feature = features[0]
    summary = feature.get("properties", {}).get("summary", {})
    coordinates = feature.get("geometry", {}).get("coordinates", [])
    return Route(
        line=[(lat, lon) for lon, lat, *_ in coordinates],
        distance_m=float(summary.get("distance", 0.0)),
        duration_s=float(summary.get("duration", 0.0)),
    )


# ------------------------------------------------ keyless fallback (OSRM)
#
# Without an OpenRouteService key, routes come from the public OSRM servers
# run by FOSSGIS for OpenStreetMap (routing.openstreetmap.de). They cannot be
# told to avoid areas, so avoidance is done by choosing: take OSRM's own
# alternatives, plus detours forced through points either side of the first
# hazard in the way, and keep whichever crosses the fewest hazard areas.
# Good enough to show the idea; an ORS key gives true area avoidance and
# wheelchair routing. The public server is for light use -- fine for a demo.

OSRM_URL = "https://routing.openstreetmap.de"
OSRM_PROFILES = {"walk": "routed-foot", "wheelchair": "routed-foot", "drive": "routed-car"}
# How far beyond a hazard's edge a detour point is placed.
DETOUR_CLEARANCE_M = 180


def _ring_circle(ring: list[list[float]]) -> tuple[float, float, float]:
    """(lat, lon, radius_m) of a ring made by circle_polygon."""
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    lat = sum(p[1] for p in points) / len(points)
    lon = sum(p[0] for p in points) / len(points)
    radius = haversine_m(lat, lon, points[0][1], points[0][0])
    return lat, lon, radius


def _osrm_routes(mode: str, points: list[tuple[float, float]], alternatives: bool) -> list[Route]:
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    try:
        response = httpx.get(
            f"{OSRM_URL}/{OSRM_PROFILES[mode]}/route/v1/driving/{coords}",
            params={
                "alternatives": "3" if alternatives else "false",
                "overview": "full",
                "geometries": "geojson",
            },
            headers={"User-Agent": get_settings().geocoder_user_agent},
            timeout=get_settings().openrouteservice_timeout_s,
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RoutingError(f"Could not reach the routing service: {exc}") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError(str(payload.get("message") or payload.get("code") or "No route found."), 2009)

    return [
        Route(
            line=[(lat, lon) for lon, lat in r["geometry"]["coordinates"]],
            distance_m=float(r["distance"]),
            duration_s=float(r["duration"]),
        )
        for r in payload["routes"]
    ]


def _crossings(route: Route, circles: list[tuple[float, float, float]]) -> list[int]:
    from app.services.hazard_service import distance_to_line_m

    return [
        i
        for i, (lat, lon, radius) in enumerate(circles)
        if distance_to_line_m(lat, lon, route.line) <= radius
    ]


def _osrm_directions(
    mode: str,
    start: tuple[float, float],
    end: tuple[float, float],
    avoid_rings: list[list[list[float]]] | None,
) -> Route:
    candidates = _osrm_routes(mode, [start, end], alternatives=bool(avoid_rings))
    if not avoid_rings:
        return candidates[0]

    circles = [_ring_circle(ring) for ring in avoid_rings]

    def score(route: Route) -> tuple[int, float]:
        return (len(_crossings(route, circles)), route.duration_s)

    best = min(candidates, key=score)
    crossed = _crossings(best, circles)
    if crossed:
        # Force detours around the first hazard still in the way: through a
        # point clear of it on each side (north, south, east, west).
        lat, lon, radius = circles[crossed[0]]
        offset = radius + DETOUR_CLEARANCE_M
        d_lat = offset / 111_320
        d_lon = offset / (111_320 * math.cos(math.radians(lat)))
        for via in ((lat + d_lat, lon), (lat - d_lat, lon), (lat, lon + d_lon), (lat, lon - d_lon)):
            try:
                detour = _osrm_routes(mode, [start, via, end], alternatives=False)[0]
            except RoutingError:
                continue
            if score(detour) < score(best):
                best = detour

    return best
