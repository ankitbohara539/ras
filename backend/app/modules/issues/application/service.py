from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.application.service import user_roles
from app.modules.issues.domain.workflow import ensure_issue_transition
from app.shared.infrastructure.geo import distance_meters, mysql_point
from app.shared.infrastructure.models import (
    AdministrativeArea,
    Issue,
    IssueAssignment,
    IssueCategory,
    IssueStatus,
    IssueStatusHistory,
    IssueVote,
    Notification,
    NotificationRecipient,
    Role,
    RoleCode,
    UserRole,
    utcnow,
)


class IssueCreate(BaseModel):
    category_id: str
    title: str = Field(min_length=4, max_length=180)
    description: str = Field(min_length=10, max_length=5000)
    severity: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    latitude: float
    longitude: float
    administrative_area_id: str | None = None
    address_text: str | None = Field(default=None, max_length=500)
    anonymous_public_display: bool = False
    client_request_id: str

    @field_validator("latitude")
    @classmethod
    def latitude_range(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Latitude must be between -90 and 90.")
        return value

    @field_validator("longitude")
    @classmethod
    def longitude_range(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Longitude must be between -180 and 180.")
        return value

    @field_validator("client_request_id")
    @classmethod
    def valid_uuid(cls, value: str) -> str:
        UUID(value)
        return value


class IssueStatusChange(BaseModel):
    status: IssueStatus
    note: str | None = Field(default=None, max_length=1000)


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=4, max_length=180)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    severity: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    address_text: str | None = Field(default=None, max_length=500)
    anonymous_public_display: bool | None = None


class IssueAssign(BaseModel):
    assigned_to: str
    note: str | None = Field(default=None, max_length=1000)


class IssueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    reporter_id: str
    category_id: str
    title: str
    description: str
    status: IssueStatus
    severity: str
    address_text: str | None
    anonymous_public_display: bool
    administrative_area_id: str | None
    client_request_id: str
    created_at: datetime
    updated_at: datetime
    distance_meters: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    confirmations: int = 0


class IssuePage(BaseModel):
    items: list[IssueItem]
    page: int
    page_size: int
    total: int


class IssueService:
    def __init__(self, db: AsyncSession, events: EventBus) -> None:
        self.db = db
        self.events = events

    async def create(self, actor_id: str, payload: IssueCreate) -> IssueItem:
        existing = await self.db.scalar(
            select(Issue).where(Issue.client_request_id == payload.client_request_id)
        )
        if existing:
            return await self.get(existing.id)
        if not await self.db.get(IssueCategory, payload.category_id):
            raise NotFoundError("Issue category was not found.")
        if payload.administrative_area_id and not await self.db.get(
            AdministrativeArea, payload.administrative_area_id
        ):
            raise NotFoundError("Ward was not found.")
        issue = Issue(
            reporter_id=actor_id,
            category_id=payload.category_id,
            administrative_area_id=payload.administrative_area_id,
            title=payload.title.strip(),
            description=payload.description.strip(),
            severity=payload.severity,
            status=IssueStatus.REPORTED,
            location=mysql_point(payload.longitude, payload.latitude),
            address_text=payload.address_text,
            anonymous_public_display=payload.anonymous_public_display,
            client_request_id=payload.client_request_id,
        )
        self.db.add(issue)
        await self.db.flush()
        self.db.add(
            IssueStatusHistory(
                issue_id=issue.id,
                from_status=None,
                to_status=IssueStatus.REPORTED,
                changed_by=actor_id,
                note="Issue reported",
            )
        )
        notification = Notification(
            event_type="issue.created",
            title="New community issue",
            body=issue.title,
            payload={"issue_id": issue.id},
        )
        self.db.add(notification)
        await self.db.flush()
        authority_ids = (
            await self.db.execute(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.code.in_([RoleCode.AUTHORITY, RoleCode.ADMIN]))
            )
        ).scalars().all()
        self.db.add_all(
            [NotificationRecipient(notification_id=notification.id, user_id=user_id) for user_id in authority_ids]
        )
        await self.db.commit()
        await self.events.publish(
            "role:AUTHORITY", {"type": "issue.created", "data": {"issue_id": issue.id}}
        )
        return await self.get(issue.id)

    async def get(self, issue_id: str) -> IssueItem:
        distance = None
        row = (
            await self.db.execute(
                select(
                    Issue,
                    func.ST_Latitude(Issue.location).label("latitude"),
                    func.ST_Longitude(Issue.location).label("longitude"),
                    func.count(IssueVote.id).label("confirmations"),
                )
                .outerjoin(IssueVote, IssueVote.issue_id == Issue.id)
                .where(Issue.id == issue_id)
                .group_by(Issue.id)
            )
        ).first()
        if row is None:
            raise NotFoundError("The requested issue was not found.")
        issue = IssueItem.model_validate(row[0])
        return issue.model_copy(
            update={
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
                "confirmations": int(row.confirmations),
                "distance_meters": distance,
            }
        )

    async def list(
        self,
        page: int,
        page_size: int,
        reporter_id: str | None = None,
        status: IssueStatus | None = None,
    ) -> IssuePage:
        filters = []
        if reporter_id:
            filters.append(Issue.reporter_id == reporter_id)
        if status:
            filters.append(Issue.status == status)
        total = await self.db.scalar(select(func.count()).select_from(Issue).where(*filters)) or 0
        rows = (
            await self.db.execute(
                select(Issue)
                .where(*filters)
                .order_by(Issue.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return IssuePage(
            items=[IssueItem.model_validate(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def nearby(
        self, latitude: float, longitude: float, radius: int, page: int, page_size: int
    ) -> IssuePage:
        distance = distance_meters(Issue.location, longitude, latitude).label("distance_meters")
        criteria = distance_meters(Issue.location, longitude, latitude) <= radius
        total = await self.db.scalar(select(func.count()).select_from(Issue).where(criteria)) or 0
        rows = (
            await self.db.execute(
                select(
                    Issue,
                    distance,
                    func.ST_Latitude(Issue.location).label("latitude"),
                    func.ST_Longitude(Issue.location).label("longitude"),
                )
                .where(criteria)
                .order_by(distance)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return IssuePage(
            items=[
                IssueItem.model_validate(row[0]).model_copy(
                    update={
                        "distance_meters": float(row.distance_meters),
                        "latitude": float(row.latitude),
                        "longitude": float(row.longitude),
                    }
                )
                for row in rows
            ],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def confirm(self, issue_id: str, actor_id: str) -> None:
        if not await self.db.get(Issue, issue_id):
            raise NotFoundError("The requested issue was not found.")
        self.db.add(IssueVote(issue_id=issue_id, user_id=actor_id))
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError("You have already confirmed this issue.") from exc

    async def unconfirm(self, issue_id: str, actor_id: str) -> None:
        await self.db.execute(
            delete(IssueVote).where(IssueVote.issue_id == issue_id, IssueVote.user_id == actor_id)
        )
        await self.db.commit()

    async def update_details(
        self, issue_id: str, actor_id: str, privileged: bool, payload: IssueUpdate
    ) -> IssueItem:
        issue = await self.db.get(Issue, issue_id)
        if issue is None:
            raise NotFoundError("The requested issue was not found.")
        if not privileged and (
            issue.reporter_id != actor_id or issue.status != IssueStatus.REPORTED
        ):
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError("Only a newly reported issue can be edited by its reporter.")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(issue, field, value.strip() if isinstance(value, str) else value)
        issue.version += 1
        await self.db.commit()
        return await self.get(issue_id)

    async def assign(
        self, issue_id: str, actor_id: str, payload: IssueAssign
    ) -> IssueItem:
        issue = await self.db.get(Issue, issue_id)
        if issue is None:
            raise NotFoundError("The requested issue was not found.")
        target_roles = await user_roles(self.db, payload.assigned_to)
        if not set(target_roles).intersection({RoleCode.AUTHORITY, RoleCode.ADMIN}):
            raise ConflictError("Issues can only be assigned to an authority or administrator.")
        ensure_issue_transition(issue.status, IssueStatus.ASSIGNED)
        previous = issue.status
        issue.status = IssueStatus.ASSIGNED
        issue.version += 1
        self.db.add_all(
            [
                IssueAssignment(
                    issue_id=issue_id,
                    assigned_to=payload.assigned_to,
                    assigned_by=actor_id,
                ),
                IssueStatusHistory(
                    issue_id=issue_id,
                    from_status=previous,
                    to_status=IssueStatus.ASSIGNED,
                    changed_by=actor_id,
                    note=payload.note,
                ),
            ]
        )
        await self.db.commit()
        await self.events.publish(
            f"user:{payload.assigned_to}",
            {"type": "issue.assigned", "data": {"issue_id": issue_id}},
        )
        return await self.get(issue_id)

    async def change_status(
        self, issue_id: str, actor_id: str, payload: IssueStatusChange
    ) -> IssueItem:
        issue = await self.db.get(Issue, issue_id)
        if issue is None:
            raise NotFoundError("The requested issue was not found.")
        ensure_issue_transition(issue.status, payload.status)
        previous = issue.status
        issue.status = payload.status
        issue.version += 1
        if payload.status == IssueStatus.RESOLVED:
            issue.resolved_at = utcnow()
        self.db.add(
            IssueStatusHistory(
                issue_id=issue.id,
                from_status=previous,
                to_status=payload.status,
                changed_by=actor_id,
                note=payload.note,
            )
        )
        notification = Notification(
            event_type="issue.status_changed",
            title="Issue status updated",
            body=f"{issue.title} is now {payload.status.value.replace('_', ' ').title()}",
            payload={"issue_id": issue.id, "status": payload.status.value},
        )
        self.db.add(notification)
        await self.db.flush()
        self.db.add(NotificationRecipient(notification_id=notification.id, user_id=issue.reporter_id))
        await self.db.commit()
        await self.events.publish(
            f"user:{issue.reporter_id}",
            {"type": "issue.status_changed", "data": {"issue_id": issue.id, "status": payload.status.value}},
        )
        return await self.get(issue.id)
