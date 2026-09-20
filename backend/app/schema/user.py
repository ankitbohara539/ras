from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Language


class ProfileUpdateRequest(BaseModel):
    """Fields a user may change about themselves.

    Note what is missing: role, account_status, municipality_id. Those are
    admin-only, so leaving them out of the schema is the enforcement.
    """

    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    # A person can correct their home ward themselves. The API derives the
    # municipality from the selected ward, so forged cross-municipality pairs
    # never enter the database.
    ward_id: UUID | None = None
    preferred_language: Language | None = None
    large_text: bool | None = None
    high_contrast: bool | None = None


class AvatarResponse(BaseModel):
    url: str | None = None


class DashboardIssueOut(BaseModel):
    """One row of the briefing's issue list -- real ticket data, never AI
    text. Priority/status are the same string values as everywhere else
    (TicketPriority/TicketStatus), so the frontend can reuse its existing
    badge components directly."""

    id: UUID
    code: str
    title: str
    priority: str
    status: str
    reporters: int
    age_days: int


class DashboardSummaryResponse(BaseModel):
    """The dashboard briefing button's answer: one short sentence (`text`)
    plus a real list of tickets (`issues`) -- for a citizen, their ward's
    most-reported open problems; for an officer, their own queue's highest-
    priority open tickets. Which of the count fields are populated depends
    on `audience`: a citizen gets `total_reports`/`open_reports`/
    `ward_open_reports`, an officer gets `open_reports_officer`/
    `needs_attention`/the queue counts."""

    audience: Literal["citizen", "officer"]
    text: str
    # False when the model was unavailable and `text` is a templated fallback
    # built from the same numbers -- shown, not hidden, so nobody mistakes a
    # fill-in-the-blanks sentence for a considered one.
    ai_generated: bool
    generated_at: datetime
    scope_label: str | None
    issues: list[DashboardIssueOut] = []

    # citizen
    total_reports: int | None = None
    open_reports: int | None = None
    ward_open_reports: int | None = None

    # officer
    open_reports_officer: int | None = None
    needs_attention: int | None = None
    oldest_open_days: int | None = None
    top_category_name: str | None = None
    top_category_count: int | None = None
    pending_duplicates: int | None = None
    open_sos: int | None = None
    pending_civic: int | None = None
