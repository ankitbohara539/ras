"""The hazard map and safer-route planner."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.routing import RoutingError, RoutingNotConfigured
from app.core.security import get_current_profile
from app.db.session import get_db
from app.models.profile import Profile
from app.schema.hazard import (
    HazardListResponse,
    HazardResponse,
    RouteOut,
    RouteRequest,
    RouteResponse,
)
from app.services import hazard_service, route_service
from app.services.hazard_service import Hazard

router = APIRouter(prefix="/hazards", tags=["Hazards"])

# A citywide box is fine; a country-sized one is a mistake or a scrape.
MAX_BOX_DEG = 0.6


def _hazard(h: Hazard) -> HazardResponse:
    return HazardResponse(
        id=h.id,
        source=h.source,
        kind=h.kind,
        title=h.title,
        severity=h.severity,
        latitude=h.latitude,
        longitude=h.longitude,
        radius_m=h.radius_m,
        modes=sorted(h.modes),
        night_only=h.night_only,
        active_now=h.active_now,
        avoid=h.avoid,
        approximate=h.approximate,
        reported_at=h.reported_at,
        reports=h.reports,
        confirmations=h.confirmations,
        ticket_id=h.ticket_id,
        alert_id=h.alert_id,
        category_key=h.category_key,
    )


def _route(planned: route_service.PlannedRoute) -> RouteOut:
    return RouteOut(
        line=[(round(lat, 6), round(lon, 6)) for lat, lon in planned.route.line],
        distance_m=round(planned.route.distance_m, 1),
        duration_s=round(planned.route.duration_s, 1),
        hazard_ids=[h.id for h in planned.hazards],
        risk=planned.risk,
    )


@router.get("", response_model=HazardListResponse)
def list_hazards(
    min_lat: float = Query(ge=-90, le=90),
    min_lon: float = Query(ge=-180, le=180),
    max_lat: float = Query(ge=-90, le=90),
    max_lon: float = Query(ge=-180, le=180),
    night: bool | None = None,
    _profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> HazardListResponse:
    """Current hazards inside a map view.

    Only what is needed to stay safe -- kind, place, how many reported it --
    never who reported it or their description.
    """
    if max_lat - min_lat > MAX_BOX_DEG or max_lon - min_lon > MAX_BOX_DEG:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Zoom in: the map area is too large.",
        )
    night_now = hazard_service.is_night() if night is None else night
    hazards = hazard_service.list_hazards(db, min_lat, min_lon, max_lat, max_lon, night_now)
    return HazardListResponse(items=[_hazard(h) for h in hazards], night=night_now)


@router.post("/route", response_model=RouteResponse)
def plan_route(
    data: RouteRequest,
    _profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> RouteResponse:
    start = (data.start.latitude, data.start.longitude)
    end = (data.end.latitude, data.end.longitude)
    try:
        result = route_service.plan(db, start, end, data.mode, data.night)
    except RoutingNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not plan a route: {exc}",
        ) from exc

    return RouteResponse(
        mode=result.mode,
        profile_used=result.profile_used,
        night=result.night,
        fastest=_route(result.fastest),
        safer=_route(result.safer) if result.safer else None,
        recommended=result.recommended,
        hazards=[_hazard(h) for h in result.hazards],
        notes=result.notes,
        disclaimer=result.disclaimer,
    )
