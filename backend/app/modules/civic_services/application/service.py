from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.shared.infrastructure.geo import distance_meters, mysql_point
from app.shared.infrastructure.models import CivicService, CivicServiceCategory


class CivicServiceCreate(BaseModel):
    category_id: str
    administrative_area_id: str | None = None
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str = Field(min_length=2, max_length=500)
    latitude: float
    longitude: float
    opening_hours: dict[str, Any] | None = None
    emergency_service: bool = False

    @field_validator("latitude")
    @classmethod
    def lat_range(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Invalid latitude.")
        return value

    @field_validator("longitude")
    @classmethod
    def lng_range(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Invalid longitude.")
        return value


class CivicServiceUpdate(BaseModel):
    category_id: str | None = None
    administrative_area_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=2, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    opening_hours: dict[str, Any] | None = None
    emergency_service: bool | None = None
    active: bool | None = None


class CivicServiceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category_id: str
    name: str
    description: str | None
    phone: str | None
    email: str | None
    address: str
    opening_hours: dict[str, Any] | None
    emergency_service: bool
    active: bool
    created_at: datetime
    distance_meters: float | None = None


class CivicServicePage(BaseModel):
    items: list[CivicServiceItem]
    page: int
    page_size: int
    total: int


class CivicDirectoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: CivicServiceCreate) -> CivicService:
        if not await self.db.get(CivicServiceCategory, payload.category_id):
            raise NotFoundError("Civic service category was not found.")
        service = CivicService(
            **payload.model_dump(exclude={"latitude", "longitude"}),
            location=mysql_point(payload.longitude, payload.latitude),
            active=True,
        )
        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def get(self, service_id: str) -> CivicService:
        result = await self.db.get(CivicService, service_id)
        if result is None:
            raise NotFoundError("Civic service was not found.")
        return result

    async def update(self, service_id: str, payload: CivicServiceUpdate) -> CivicService:
        service = await self.get(service_id)
        values = payload.model_dump(exclude_unset=True)
        latitude = values.pop("latitude", None)
        longitude = values.pop("longitude", None)
        if (latitude is None) != (longitude is None):
            from app.core.exceptions import ConflictError

            raise ConflictError("Latitude and longitude must be updated together.")
        for field, value in values.items():
            setattr(service, field, value)
        if latitude is not None and longitude is not None:
            service.location = mysql_point(longitude, latitude)
        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def deactivate(self, service_id: str) -> None:
        service = await self.get(service_id)
        service.active = False
        await self.db.commit()

    async def list(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: int | None = None,
    ) -> CivicServicePage:
        filters = [CivicService.active.is_(True)]
        if search:
            filters.append(CivicService.name.like(f"%{search[:100]}%"))
        distance = None
        if latitude is not None and longitude is not None and radius is not None:
            distance = distance_meters(CivicService.location, longitude, latitude)
            filters.append(distance <= radius)
        total = await self.db.scalar(select(func.count()).select_from(CivicService).where(*filters)) or 0
        statement = select(CivicService)
        if distance is not None:
            statement = select(CivicService, distance.label("distance_meters")).order_by(distance)
        statement = statement.where(*filters).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.db.execute(statement)).all()
        items = []
        for row in rows:
            item = CivicServiceItem.model_validate(row[0])
            if distance is not None:
                item = item.model_copy(update={"distance_meters": float(row.distance_meters)})
            items.append(item)
        return CivicServicePage(items=items, page=page, page_size=page_size, total=total)
