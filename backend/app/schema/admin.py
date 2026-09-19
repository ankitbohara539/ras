from uuid import UUID

from pydantic import BaseModel, Field

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
    municipality_id: UUID | None = None
    ward_id: UUID | None = None


class EscalationSweepResponse(BaseModel):
    """How many tickets the age ladder moved on this pass."""

    escalated: int
