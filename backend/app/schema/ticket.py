from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CandidateStatus,
    Language,
    TicketPriority,
    TicketStatus,
)


class TicketCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str = Field(min_length=10, max_length=4000)

    # Optional: when omitted the classifier picks the category. When supplied,
    # the citizen's choice wins and the prediction is kept for comparison.
    category_id: UUID | None = None

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_text: str | None = Field(default=None, max_length=300)
    description_lang: Language = Language.EN


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    storage_path: str
    url: str | None = None


class TicketSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_code: str
    title: str
    description: str
    category_id: UUID
    status: TicketStatus
    priority: TicketPriority
    latitude: float
    longitude: float
    address_text: str | None
    ward_id: UUID
    municipality_id: UUID
    # Which ward actually owns this. Decided by GPS at submission time, which
    # is not necessarily the reporter's home ward -- so it is always shown.
    ward_number: int | None = None
    ward_name: str | None = None
    municipality_code: str | None = None
    parent_id: UUID | None
    child_count: int
    corroboration_count: int
    dispute_count: int
    community_verified: bool
    # Distinct citizens who commented that this is urgent; raises priority.
    urgent_commenter_count: int = 0
    # True when a human fixed the priority, so neither scoring nor the age
    # ladder will move it. Shown as a lock on the badge.
    priority_locked: bool = False
    created_at: datetime
    resolved_at: datetime | None

    # Present on nearby listings, where the caller sent coordinates.
    distance_m: float | None = None


class DuplicateCandidateResponse(BaseModel):
    """A merge suggestion. Below the auto-merge score an authority decides."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # The newly submitted ticket ...
    ticket_id: UUID
    ticket: TicketSummary | None = None
    # ... and the existing one it might belong under.
    candidate_ticket_id: UUID
    candidate: TicketSummary | None = None
    score: float
    category_score: float
    text_score: float
    image_score: float
    geo_score: float
    distance_m: float
    status: CandidateStatus
    explanation: str | None = None


class StatusHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: TicketStatus | None
    to_status: TicketStatus
    note: str | None
    created_at: datetime


class TicketDetail(TicketSummary):
    reporter_id: UUID
    reporter_name: str | None = None
    assigned_to_id: UUID | None = None
    predicted_category_key: str | None = None
    category_confidence: float | None = None
    resolution_note: str | None = None
    verified_at: datetime | None = None
    priority_set_at: datetime | None = None
    priority_note: str | None = None
    priority_set_by_name: str | None = None

    photos: list[PhotoResponse] = []
    children: list[TicketSummary] = []
    history: list[StatusHistoryEntry] = []
    # Only populated for authority callers.
    duplicate_candidates: list[DuplicateCandidateResponse] = []
    # Whether the calling citizen has already corroborated.
    my_corroboration: bool | None = None


class TicketCreateResponse(BaseModel):
    ticket: TicketDetail
    # Shown to the citizen as "this may already be reported".
    possible_duplicates: list[DuplicateCandidateResponse] = []
    # Set when the match was strong enough (>= dedupe_auto_merge_score) that
    # the report was merged straight away: this is the ticket it now follows.
    auto_merged_into: TicketSummary | None = None
    auto_merge_score: float | None = None


class TicketListResponse(BaseModel):
    items: list[TicketSummary]
    total: int


class StatusUpdateRequest(BaseModel):
    status: TicketStatus
    note: str | None = Field(default=None, max_length=1000)
    resolution_note: str | None = Field(default=None, max_length=2000)


class AssignRequest(BaseModel):
    assigned_to_id: UUID | None = None
    priority: TicketPriority | None = None


class PriorityUpdateRequest(BaseModel):
    """Set priority by hand, or hand it back to automation.

    `priority: null` clears the override and recomputes from the score and the
    age ladder. Without that, an override would be one-way.
    """

    priority: TicketPriority | None = None
    note: str | None = Field(default=None, max_length=500)


class MergeRequest(BaseModel):
    """Fold one ticket under another as a duplicate."""

    parent_ticket_id: UUID
    note: str | None = Field(default=None, max_length=500)


class ReassignWardRequest(BaseModel):
    """Correct GPS routing that put a ticket in the wrong ward."""

    ward_id: UUID


class TicketCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class TicketCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    author_id: UUID
    author_name: str | None = None
    author_role: str | None = None
    body: str
    created_at: datetime
    # The comment presses for a faster fix, so it counts toward priority.
    is_urgent: bool = False
    # True when the caller wrote this comment, so the UI can offer delete.
    is_mine: bool = False


class TicketCommentListResponse(BaseModel):
    items: list[TicketCommentResponse]
    total: int


class CorroborationRequest(BaseModel):
    """A nearby citizen confirming or disputing a report."""

    is_confirmed: bool = True
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=500)


class CorroborationResponse(BaseModel):
    ticket_id: UUID
    corroboration_count: int
    dispute_count: int
    community_verified: bool
    distance_m: float
    message: str
