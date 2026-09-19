from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import event_bus
from app.modules.auth.presentation.dependencies import CurrentUser, require_any_role
from app.shared.infrastructure.models import (
    EmergencyAlert,
    Notification,
    NotificationRecipient,
    RoleCode,
    User,
    UserStatus,
    utcnow,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    message: str = Field(min_length=5, max_length=5000)
    severity: str = Field(pattern="^(INFO|WATCH|WARNING|CRITICAL)$")
    administrative_area_id: str | None = None
    starts_at: datetime
    expires_at: datetime | None = None


class AlertUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    message: str | None = Field(default=None, min_length=5, max_length=5000)
    severity: str | None = Field(default=None, pattern="^(INFO|WATCH|WARNING|CRITICAL)$")
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    active: bool | None = None


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    message: str
    severity: str
    starts_at: datetime
    expires_at: datetime | None
    active: bool
    created_at: datetime


@router.get("", response_model=list[AlertResponse])
async def alerts(
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active: bool | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> list[EmergencyAlert]:
    statement = select(EmergencyAlert).order_by(EmergencyAlert.created_at.desc()).limit(limit)
    if active is True:
        statement = statement.where(
            EmergencyAlert.active.is_(True),
            EmergencyAlert.starts_at <= utcnow(),
            or_(EmergencyAlert.expires_at.is_(None), EmergencyAlert.expires_at > utcnow()),
        )
    return list((await db.execute(statement)).scalars().all())


@router.get("/active", response_model=list[AlertResponse])
async def active_alerts(
    current: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[EmergencyAlert]:
    return await alerts(current, db, True, 50)


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    payload: AlertCreate,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EmergencyAlert:
    alert = EmergencyAlert(**payload.model_dump(), created_by=current.id, active=True)
    db.add(alert)
    await db.flush()
    notification = Notification(
        event_type="alert.published",
        title=alert.title,
        body=alert.message,
        payload={
            "alert_id": alert.id,
            "severity": alert.severity,
            "administrative_area_id": alert.administrative_area_id,
        },
    )
    db.add(notification)
    await db.flush()
    recipient_ids = (
        await db.execute(select(User.id).where(User.status == UserStatus.ACTIVE))
    ).scalars().all()
    db.add_all(
        [
            NotificationRecipient(notification_id=notification.id, user_id=user_id)
            for user_id in recipient_ids
        ]
    )
    await db.commit()
    await db.refresh(alert)
    realtime_payload = {
        "type": "alert.published",
        "data": {"alert_id": alert.id, "severity": alert.severity},
    }
    for role in RoleCode:
        await event_bus.publish(f"role:{role.value}", realtime_payload)
    return alert


@router.post("/{alert_id}/expire", response_model=AlertResponse)
async def expire_alert(
    alert_id: str,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EmergencyAlert:
    alert = await db.get(EmergencyAlert, alert_id)
    if alert is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Alert was not found.")
    alert.active = False
    alert.expires_at = utcnow()
    await db.commit()
    await db.refresh(alert)
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    payload: AlertUpdate,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> EmergencyAlert:
    alert = await db.get(EmergencyAlert, alert_id)
    if alert is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Alert was not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    await db.commit()
    await db.refresh(alert)
    return alert
