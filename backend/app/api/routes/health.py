from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import database_ready

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    environment: str


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    settings = get_settings()
    return LiveResponse(app=settings.app_name, environment=settings.app_env)


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    ready_state = await database_ready()
    if not ready_state:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_state else "not_ready",
        "database": "up" if ready_state else "down",
        "email": "smtp" if get_settings().smtp_enabled else "console_only",
        "geocoding": get_settings().geocoding_provider,
    }
