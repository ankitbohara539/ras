from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    app: str
    environment: str
    supabase_configured: bool
    database_connected: bool


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()

    database_connected = False
    if settings.database_configured:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            database_connected = True
        except Exception:
            database_connected = False

    healthy = settings.supabase_configured and database_connected

    return HealthResponse(
        status="ok" if healthy else "degraded",
        app=settings.app_name,
        environment=settings.app_env,
        supabase_configured=settings.supabase_configured,
        database_connected=database_connected,
    )
