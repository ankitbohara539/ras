from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.auth.presentation.dependencies import CurrentUser, require_any_role
from app.modules.civic_services.application.service import (
    CivicDirectoryService,
    CivicServiceCreate,
    CivicServiceItem,
    CivicServicePage,
    CivicServiceUpdate,
)
from app.shared.infrastructure.models import RoleCode

router = APIRouter(prefix="/civic-services", tags=["civic services"])


def service(db: AsyncSession = Depends(get_db)) -> CivicDirectoryService:
    return CivicDirectoryService(db)


@router.get("", response_model=CivicServicePage)
async def list_services(
    current: CurrentUser,
    use_case: Annotated[CivicDirectoryService, Depends(service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
) -> CivicServicePage:
    return await use_case.list(page, page_size, search)


@router.get("/nearby", response_model=CivicServicePage)
async def nearby_services(
    current: CurrentUser,
    use_case: Annotated[CivicDirectoryService, Depends(service)],
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius: int = Query(5_000, ge=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CivicServicePage:
    radius = min(radius, get_settings().max_nearby_radius_meters)
    return await use_case.list(page, page_size, latitude=lat, longitude=lng, radius=radius)


@router.get("/{service_id}", response_model=CivicServiceItem)
async def get_service(
    service_id: str,
    current: CurrentUser,
    use_case: Annotated[CivicDirectoryService, Depends(service)],
) -> CivicServiceItem:
    return CivicServiceItem.model_validate(await use_case.get(service_id))


@router.post("", response_model=CivicServiceItem, status_code=201)
async def create_service(
    payload: CivicServiceCreate,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    use_case: CivicDirectoryService = Depends(service),
) -> CivicServiceItem:
    return CivicServiceItem.model_validate(await use_case.create(payload))


@router.patch("/{service_id}", response_model=CivicServiceItem)
async def update_service(
    service_id: str,
    payload: CivicServiceUpdate,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    use_case: CivicDirectoryService = Depends(service),
) -> CivicServiceItem:
    return CivicServiceItem.model_validate(await use_case.update(service_id, payload))


@router.delete("/{service_id}", status_code=204)
async def delete_service(
    service_id: str,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    use_case: CivicDirectoryService = Depends(service),
) -> None:
    await use_case.deactivate(service_id)
