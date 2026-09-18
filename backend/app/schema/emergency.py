from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    AlertSeverity,
    AlertTargetType,
    EmergencyType,
    SosStatus,
)


class SosCreateRequest(BaseModel):
    emergency_type: EmergencyType
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=1000)
    contact_phone: str | None = Field(default=None, max_length=32)
    address_text: str | None = Field(default=None, max_length=300)


class SosResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    citizen_id: UUID
    citizen_name: str | None = None
    citizen_phone: str | None = None
    emergency_type: EmergencyType
    latitude: float
    longitude: float
    address_text: str | None
    ward_id: UUID | None
    note: str | None
    contact_phone: str | None
    status: SosStatus
    acknowledged_at: datetime | None
    closed_at: datetime | None
    resolution_note: str | None
    created_at: datetime


class SosCreateResponse(BaseModel):
    sos: SosResponse
    # Emergency numbers are returned inline: the citizen should not have to
    # navigate anywhere to get a phone number during an emergency.
    emergency_contacts: list[dict]
    message: str


class SosUpdateRequest(BaseModel):
    status: SosStatus
    resolution_note: str | None = Field(default=None, max_length=1000)


class AlertCreateRequest(BaseModel):
    title_en: str = Field(min_length=3, max_length=200)
    title_ne: str | None = Field(default=None, max_length=200)
    body_en: str = Field(min_length=3, max_length=4000)
    body_ne: str | None = Field(default=None, max_length=4000)
    instructions_en: str | None = Field(default=None, max_length=4000)
    instructions_ne: str | None = Field(default=None, max_length=4000)

    severity: AlertSeverity = AlertSeverity.INFO
    target_type: AlertTargetType

    ward_ids: list[UUID] | None = None
    center_lat: float | None = Field(default=None, ge=-90, le=90)
    center_lon: float | None = Field(default=None, ge=-180, le=180)
    radius_m: int | None = Field(default=None, ge=100, le=50_000)

    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def check_target(self) -> "AlertCreateRequest":
        if self.target_type is AlertTargetType.WARD:
            if not self.ward_ids:
                raise ValueError("A ward-targeted alert needs at least one ward.")
        else:
            missing = [
                name
                for name, value in (
                    ("center_lat", self.center_lat),
                    ("center_lon", self.center_lon),
                    ("radius_m", self.radius_m),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"A radius-targeted alert needs: {', '.join(missing)}."
                )
        return self


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title_en: str
    title_ne: str | None
    body_en: str
    body_ne: str | None
    instructions_en: str | None
    instructions_ne: str | None
    severity: AlertSeverity
    target_type: AlertTargetType
    ward_ids: list[UUID] | None
    center_lat: float | None
    center_lon: float | None
    radius_m: int | None
    starts_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    distance_m: float | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    title_en: str
    title_ne: str | None
    body_en: str | None
    ticket_id: UUID | None
    alert_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread: int
