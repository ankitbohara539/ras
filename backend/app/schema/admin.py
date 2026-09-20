from uuid import UUID

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import AccountStatus, UserRole
from app.schema.auth import ProfileResponse


class ProfileListResponse(BaseModel):
    items: list[ProfileResponse]
    total: int


class ApprovalRequest(BaseModel):
    """Admin approving a pending authority account.

    The admin may correct the scope at approval time -- applicants pick their
    own ward at signup and get it wrong often enough to matter.
    """

    municipality_id: UUID | None = None
    ward_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminProfileUpdateRequest(BaseModel):
    """Everything an admin may change that a user may not."""

    role: UserRole | None = None
    account_status: AccountStatus | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    municipality_id: UUID | None = None
    ward_id: UUID | None = None


class EscalationSweepResponse(BaseModel):
    """How many tickets the age ladder moved on this pass."""

    escalated: int


class AdminContentItem(BaseModel):
    """Compact cross-content row used by the user-management detail drawer."""

    id: UUID
    code: str
    kind: str
    title: str | None = None
    description: str
    ward_id: UUID
    status: str
    created_at: datetime


class AdminProfileDetailResponse(BaseModel):
    profile: ProfileResponse
    reports: list[AdminContentItem] = []
    civic_complaints: list[AdminContentItem] = []


class WardCreateRequest(BaseModel):
    municipality_id: UUID
    number: int = Field(ge=1, le=999)
    name_en: str | None = Field(default=None, max_length=120)
    name_ne: str | None = Field(default=None, max_length=120)
    centroid_lat: float = Field(ge=-90, le=90)
    centroid_lon: float = Field(ge=-180, le=180)


class WardUpdateRequest(BaseModel):
    number: int | None = Field(default=None, ge=1, le=999)
    name_en: str | None = Field(default=None, max_length=120)
    name_ne: str | None = Field(default=None, max_length=120)
    centroid_lat: float | None = Field(default=None, ge=-90, le=90)
    centroid_lon: float | None = Field(default=None, ge=-180, le=180)


class WardManagementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    municipality_id: UUID
    number: int
    name_en: str | None
    name_ne: str | None
    centroid_lat: float
    centroid_lon: float
    civilian_count: int = 0
    authority_count: int = 0
    report_count: int = 0


class WardDetailResponse(WardManagementResponse):
    civilians: list[ProfileResponse] = []
