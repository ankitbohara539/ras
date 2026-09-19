from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Mode = Literal["walk", "wheelchair", "drive"]


class HazardResponse(BaseModel):
    id: str
    source: Literal["ticket", "alert"]
    kind: str
    title: str
    severity: Literal["low", "medium", "high"]
    latitude: float
    longitude: float
    radius_m: int
    modes: list[Mode]
    night_only: bool
    active_now: bool
    avoid: bool
    # Drawn as a circle around a ward centre, not the exact area.
    approximate: bool = False
    reported_at: datetime | None = None
    reports: int = 1
    confirmations: int = 0
    ticket_id: UUID | None = None
    alert_id: UUID | None = None
    category_key: str | None = None


class HazardListResponse(BaseModel):
    items: list[HazardResponse]
    night: bool


class Point(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    start: Point
    end: Point
    mode: Mode = "walk"
    # Override day/night (defaults to Nepal's current time).
    night: bool | None = None


class RouteOut(BaseModel):
    # [lat, lon] points.
    line: list[tuple[float, float]]
    distance_m: float
    duration_s: float
    hazard_ids: list[str]
    risk: int


class RouteResponse(BaseModel):
    mode: Mode
    profile_used: Mode
    night: bool
    fastest: RouteOut
    safer: RouteOut | None
    recommended: Literal["fastest", "safer"]
    hazards: list[HazardResponse]
    notes: list[str]
    disclaimer: str
