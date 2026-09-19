"""The public transparency page: aggregates only, no login, no per-ticket data.

Nothing here carries a title, description, photo or exact coordinate --
only counts and medians. That is a deliberate boundary, not an omission: an
anonymous visitor should be able to see that ward 5 has a backlog without
being able to read what any one citizen wrote or where they live.
"""

from datetime import datetime

from pydantic import BaseModel


class CategoryStat(BaseModel):
    key: str
    name_en: str
    name_ne: str
    total: int
    resolved: int
    median_resolution_hours: float | None = None


class WardStat(BaseModel):
    number: int
    name_en: str | None
    name_ne: str | None
    total: int
    open: int
    resolved: int
    median_resolution_hours: float | None = None


class PublicStatsResponse(BaseModel):
    municipality_code: str
    municipality_name_en: str
    municipality_name_ne: str

    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    resolved_this_month: int
    median_resolution_hours: float | None = None

    by_category: list[CategoryStat]
    by_ward: list[WardStat]

    generated_at: datetime
