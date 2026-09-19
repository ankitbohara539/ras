from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.emergency.domain.workflow import ensure_emergency_transition
from app.shared.infrastructure.geo import mysql_point
from app.shared.infrastructure.models import (
    EmergencySOS,
    EmergencySOSStatusHistory,
    EmergencyStatus,
    Notification,
    NotificationRecipient,
    Role,
    RoleCode,
    UserRole,
    utcnow,
)


class SOSCreate(BaseModel):
    emergency_type: str = Field(min_length=2, max_length=60)
    latitude: float
    longitude: float
    address_text: str | None = Field(default=None, max_length=500)
    message: str | None = Field(default=None, max_length=1000)

    @field_validator("latitude")
    @classmethod
    def latitude_range(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Invalid latitude.")
        return value

    @field_validator("longitude")
    @classmethod
    def longitude_range(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Invalid longitude.")
        return value


class SOSResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    emergency_type: str
    status: EmergencyStatus
    address_text: str | None
    message: str | None
    assigned_responder_id: str | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    version: int


class EmergencyService:
    def __init__(self, db: AsyncSession, events: EventBus) -> None:
        self.db = db
        self.events = events

    async def create(self, user_id: str, payload: SOSCreate) -> EmergencySOS:
        sos = EmergencySOS(
            user_id=user_id,
            emergency_type=payload.emergency_type,
            status=EmergencyStatus.CREATED,
            location=mysql_point(payload.longitude, payload.latitude),
            address_text=payload.address_text,
            message=payload.message,
        )
        self.db.add(sos)
        await self.db.flush()
        self.db.add(
            EmergencySOSStatusHistory(
                emergency_id=sos.id,
                from_status=None,
                to_status=EmergencyStatus.CREATED,
                changed_by=user_id,
            )
        )
        notification = Notification(
            event_type="emergency.created",
            title="New emergency SOS",
            body=f"{payload.emergency_type} assistance requested",
            payload={"emergency_id": sos.id},
        )
        self.db.add(notification)
        await self.db.flush()
        responders = (
            await self.db.execute(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.code.in_([RoleCode.RESPONDER, RoleCode.ADMIN]))
            )
        ).scalars().all()
        self.db.add_all(
            [NotificationRecipient(notification_id=notification.id, user_id=user) for user in responders]
        )
        await self.db.commit()
        await self.events.publish(
            "role:RESPONDER",
            {"type": "emergency.created", "data": {"emergency_id": sos.id}},
        )
        return sos

    async def get(self, emergency_id: str) -> EmergencySOS:
        sos = await self.db.get(EmergencySOS, emergency_id)
        if sos is None:
            raise NotFoundError("The emergency request was not found.")
        return sos

    async def transition(
        self,
        emergency_id: str,
        actor_id: str,
        target: EmergencyStatus,
        expected_version: int,
    ) -> EmergencySOS:
        sos = await self.get(emergency_id)
        ensure_emergency_transition(sos.status, target)
        values: dict[str, object] = {"status": target, "version": expected_version + 1}
        if target == EmergencyStatus.ACKNOWLEDGED:
            values.update({"assigned_responder_id": actor_id, "acknowledged_at": utcnow()})
        if target == EmergencyStatus.RESOLVED:
            values["resolved_at"] = utcnow()
        result = await self.db.execute(
            update(EmergencySOS)
            .where(EmergencySOS.id == emergency_id, EmergencySOS.version == expected_version)
            .values(**values)
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise ConflictError("This emergency was updated by another responder. Refresh and retry.")
        self.db.add(
            EmergencySOSStatusHistory(
                emergency_id=emergency_id,
                from_status=sos.status,
                to_status=target,
                changed_by=actor_id,
            )
        )
        notification = Notification(
            event_type="emergency.status_changed",
            title="Emergency status updated",
            body=f"Your SOS is now {target.value.replace('_', ' ').title()}",
            payload={"emergency_id": emergency_id, "status": target.value},
        )
        self.db.add(notification)
        await self.db.flush()
        self.db.add(NotificationRecipient(notification_id=notification.id, user_id=sos.user_id))
        await self.db.commit()
        await self.events.publish(
            f"user:{sos.user_id}",
            {"type": "emergency.status_changed", "data": {"emergency_id": emergency_id, "status": target.value}},
        )
        return await self.get(emergency_id)
