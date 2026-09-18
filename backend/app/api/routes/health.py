from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    environment: str
    supabase_configured: bool


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        app=settings.app_name,
        environment=settings.app_env,
        supabase_configured=settings.supabase_configured,
    )

