from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CivicCategory, CivicStatus


class CivicComplaintCreateRequest(BaseModel):
    category: CivicCategory
    description: str = Field(min_length=10, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_text: str | None = Field(default=None, max_length=300)
    # When it happened; defaults to now.
    occurred_at: datetime | None = None


class CivicPhoto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str | None = None


class CivicComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_code: str
    category: CivicCategory
    description: str
    latitude: float
    longitude: float
    address_text: str | None
    ward_id: UUID
    ward_number: int | None = None
    ward_name: str | None = None
    occurred_at: datetime
    status: CivicStatus
    action_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    photos: list[CivicPhoto] = []
    # Only filled for the office handling it -- so they can follow up with
    # the witness. The reporter already knows who they are.
    reporter_name: str | None = None
    reporter_phone: str | None = None


class CivicComplaintListResponse(BaseModel):
    items: list[CivicComplaintResponse]
    total: int
    # Per-status counts for the office's queue tabs.
    counts: dict[str, int] = {}


class CivicStatusUpdateRequest(BaseModel):
    status: CivicStatus
    note: str | None = Field(default=None, max_length=1000)
