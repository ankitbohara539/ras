"""Public reference data: categories, geography and the civic service directory.

These endpoints are unauthenticated on purpose. Emergency contacts have to be
reachable before anyone logs in -- that is the whole point of the directory.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.cache import REFERENCE_TTL_S, STATS_TTL_S, cache
from app.core.config import get_settings
from app.core.geo import bounding_box, haversine_m
from app.core.geocode import reverse_geocode, search_places
from app.core.security import get_current_profile
from app.db.session import get_db
from app.models.category import Category
from app.models.emergency import CivicService
from app.models.enums import ServiceType
from app.models.geography import Municipality
from app.models.profile import Profile
from app.schema.public import PublicStatsResponse
from app.schema.reference import (
    CategoryResponse,
    CivicServiceListItem,
    MunicipalityDetailResponse,
    MunicipalityResponse,
    PlaceSearchResult,
    ReverseGeocodeResponse,
    WardResponse,
)
from app.services.stats_service import compute_public_stats
from app.services.ticket_service import locate_ward

router = APIRouter(tags=["Reference"])


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryResponse]:
    # Reference data: cached in-process, see app.core.cache.
    return cache.get_or_load(
        "ref:categories",
        lambda: [
            CategoryResponse.model_validate(c)
            for c in db.scalars(select(Category).order_by(Category.sort_order)).all()
        ],
        REFERENCE_TTL_S,
    )


@router.get("/municipalities", response_model=list[MunicipalityResponse])
def list_municipalities(db: Session = Depends(get_db)) -> list[MunicipalityResponse]:
    return cache.get_or_load(
        "ref:municipalities",
        lambda: [
            MunicipalityResponse.model_validate(m)
            for m in db.scalars(select(Municipality).order_by(Municipality.name_en)).all()
        ],
        REFERENCE_TTL_S,
    )


@router.get(
    "/municipalities/{municipality_id}",
    response_model=MunicipalityDetailResponse,
)
def get_municipality(
    municipality_id: UUID, db: Session = Depends(get_db)
) -> MunicipalityDetailResponse:
    return cache.get_or_load(
        f"ref:municipality:{municipality_id}",
        lambda: _load_municipality(db, municipality_id),
        REFERENCE_TTL_S,
    )


def _load_municipality(db: Session, municipality_id: UUID) -> MunicipalityDetailResponse:
    municipality = db.scalar(
        select(Municipality)
        .where(Municipality.id == municipality_id)
        .options(selectinload(Municipality.wards))
    )
    if municipality is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such municipality.",
        )

    wards = sorted(municipality.wards, key=lambda w: w.number)
    return MunicipalityDetailResponse(
        **MunicipalityResponse.model_validate(municipality).model_dump(),
        wards=[WardResponse.model_validate(w) for w in wards],
    )


@router.get("/wards/nearest", response_model=WardResponse)
def nearest_ward(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
) -> WardResponse:
    """Resolve coordinates to a ward, by the same rule a new report uses.

    Kept for older clients; the report form now gets this from /geo/reverse.
    """
    return WardResponse.model_validate(locate_ward(db, latitude, longitude))


@router.get("/geo/reverse", response_model=ReverseGeocodeResponse)
def reverse(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    lang: str = Query(default="en", pattern="^(en|ne)$"),
    _profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ReverseGeocodeResponse:
    """Name the place at a point and say which ward a report there goes to.

    Signed-in only, unlike the rest of this module: it spends a shared,
    rate-limited upstream (Nominatim), and an open endpoint would let anyone
    burn that allowance through us.
    """
    # resolve_ward asks in English (it parses the ward tag); a Nepali caller
    # also wants the Nepali name. Both are cached, so a report submitted from
    # here re-uses them instead of asking again.
    # From the cached ward directory: no database read for a pin move.
    ward = locate_ward(db, latitude, longitude)
    place = reverse_geocode(latitude, longitude, lang)
    return ReverseGeocodeResponse(
        latitude=latitude,
        longitude=longitude,
        place_name=place.place_name if place else None,
        display_name=place.display_name if place else None,
        ward=WardResponse.model_validate(ward),
    )


@router.get("/geo/search", response_model=list[PlaceSearchResult])
def search(
    q: str = Query(min_length=2, max_length=120),
    lang: str = Query(default="en", pattern="^(en|ne)$"),
    _profile: Profile = Depends(get_current_profile),
) -> list[PlaceSearchResult]:
    """Find a place by name, for picking a destination on the hazard map."""
    return [
        PlaceSearchResult(
            name=r.name, display_name=r.display_name, latitude=r.latitude, longitude=r.longitude
        )
        for r in search_places(q, lang)
    ]


@router.get("/services", response_model=list[CivicServiceListItem])
def list_services(
    service_type: ServiceType | None = None,
    municipality_id: UUID | None = None,
    ward_id: UUID | None = None,
    emergency_only: bool = False,
    search: str | None = Query(default=None, max_length=120),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_m: int | None = Query(default=None, ge=100, le=50_000),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
) -> list[CivicServiceListItem]:
    filters = []
    if service_type is not None:
        filters.append(CivicService.service_type == service_type)
    if municipality_id is not None:
        filters.append(CivicService.municipality_id == municipality_id)
    if ward_id is not None:
        filters.append(CivicService.ward_id == ward_id)
    if emergency_only:
        filters.append(CivicService.is_emergency.is_(True))
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(CivicService.name_en.ilike(pattern))

    # Bounding box first so the radius filter stays indexed, exact distance after.
    if latitude is not None and longitude is not None and radius_m is not None:
        min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_m)
        filters.append(CivicService.latitude.between(min_lat, max_lat))
        filters.append(CivicService.longitude.between(min_lon, max_lon))

    rows = db.scalars(select(CivicService).where(*filters)).all()

    items: list[CivicServiceListItem] = []
    for service in rows:
        item = CivicServiceListItem.model_validate(service)

        if (
            latitude is not None
            and longitude is not None
            and service.latitude is not None
            and service.longitude is not None
        ):
            item.distance_m = round(
                haversine_m(latitude, longitude, service.latitude, service.longitude),
                1,
            )
            if radius_m is not None and item.distance_m > radius_m:
                continue

        items.append(item)

    if latitude is not None and longitude is not None:
        # Hotlines have no coordinates; keep them first, they are always usable.
        items.sort(key=lambda i: (i.distance_m is not None, i.distance_m or 0.0))

    return items[:limit]


@router.get("/public/stats", response_model=PublicStatsResponse)
def public_stats(
    municipality_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PublicStatsResponse:
    """Transparency numbers for one municipality. No login, no per-ticket data.

    Counts, medians and category/ward breakdowns only -- nothing here carries
    a title, description, photo or exact coordinate. That boundary is what
    makes this endpoint safe to leave unauthenticated.
    """
    code = (municipality_code or get_settings().public_stats_municipality_code).upper()
    # City-wide aggregates, cached for 30 s: the page shows when they were
    # generated, and nobody's own report depends on them.
    return cache.get_or_load(
        f"stats:{code}", lambda: compute_public_stats(db, code), STATS_TTL_S
    )
