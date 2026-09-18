from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import Language


class ProfileUpdateRequest(BaseModel):
    """Fields a user may change about themselves.

    Note what is missing: role, account_status, municipality_id. Those are
    admin-only, so leaving them out of the schema is the enforcement.
    """

    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    ward_id: UUID | None = None
    preferred_language: Language | None = None
    large_text: bool | None = None
    high_contrast: bool | None = None
