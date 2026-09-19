from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.presentation.dependencies import CurrentUser
from app.modules.maps.infrastructure.geocoding import geocoder
from app.shared.infrastructure.models import AdministrativeArea

router = APIRouter(prefix="/geo", tags=["geocoding"])


@router.get("/reverse")
async def reverse_geocode(
    current: CurrentUser,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    language: str = Query("en", pattern="^(en|ne)$"),
) -> dict:
    return await geocoder.reverse(lat, lng, language)


@router.get("/search")
async def search_places(
    current: CurrentUser,
    q: str = Query(min_length=3, max_length=120),
    limit: int = Query(5, ge=1, le=10),
    language: str = Query("en", pattern="^(en|ne)$"),
) -> list[dict]:
    return await geocoder.search(q.strip(), limit, language)


@router.get("/wards")
async def kathmandu_wards(
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    wards = (
        await db.execute(
            select(AdministrativeArea)
            .where(AdministrativeArea.code.like("KMC-WARD-%"), AdministrativeArea.active.is_(True))
            .order_by(AdministrativeArea.code)
        )
    ).scalars().all()
    return [{"id": ward.id, "code": ward.code, "name": ward.name} for ward in wards]
