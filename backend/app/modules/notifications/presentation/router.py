from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.presentation.dependencies import CurrentUser
from app.shared.infrastructure.models import Notification, NotificationRecipient, utcnow

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationItem(BaseModel):
    id: str
    event_type: str
    title: str
    body: str
    payload: dict[str, Any] | None
    created_at: datetime
    read_at: datetime | None


@router.get("", response_model=list[NotificationItem])
async def list_notifications(
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(30, ge=1, le=100),
) -> list[NotificationItem]:
    rows = (
        await db.execute(
            select(Notification, NotificationRecipient.read_at)
            .join(
                NotificationRecipient,
                NotificationRecipient.notification_id == Notification.id,
            )
            .where(NotificationRecipient.user_id == current.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        NotificationItem(
            id=item.id,
            event_type=item.event_type,
            title=item.title,
            body=item.body,
            payload=item.payload,
            created_at=item.created_at,
            read_at=read_at,
        )
        for item, read_at in rows
    ]


@router.get("/unread-count")
async def unread_count(
    current: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, int]:
    count = await db.scalar(
        select(func.count())
        .select_from(NotificationRecipient)
        .where(
            NotificationRecipient.user_id == current.id,
            NotificationRecipient.read_at.is_(None),
        )
    )
    return {"count": count or 0}


@router.patch("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: str,
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await db.execute(
        update(NotificationRecipient)
        .where(
            NotificationRecipient.notification_id == notification_id,
            NotificationRecipient.user_id == current.id,
        )
        .values(read_at=utcnow())
    )
    await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_read(
    current: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    await db.execute(
        update(NotificationRecipient)
        .where(
            NotificationRecipient.user_id == current.id,
            NotificationRecipient.read_at.is_(None),
        )
        .values(read_at=utcnow())
    )
    await db.commit()
