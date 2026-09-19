from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import MunicipalityType, ServiceType


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    name_en: str
    name_ne: str
    icon: str
    match_radius_m: int


class WardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    municipality_id: UUID
    number: int
    name_en: str | None
    name_ne: str | None
    centroid_lat: float
    centroid_lon: float


class MunicipalityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_en: str
    name_ne: str
    district: str
    province: str
    type: MunicipalityType


class MunicipalityDetailResponse(MunicipalityResponse):
    wards: list[WardResponse]


class CivicServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name_en: str
    name_ne: str | None
    service_type: ServiceType
    phone: str | None
    alt_phone: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    ward_id: UUID | None
    municipality_id: UUID | None
    is_24x7: bool
    is_emergency: bool
    notes_en: str | None
    notes_ne: str | None


class CivicServiceListItem(CivicServiceResponse):
    """A service plus its distance from the caller, when coordinates are given."""

    distance_m: float | None = None
