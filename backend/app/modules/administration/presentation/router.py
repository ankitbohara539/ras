from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.presentation.dependencies import require_role
from app.shared.infrastructure.models import (
    AdministrativeArea,
    AuditLog,
    IssueCategory,
    Role,
    RoleCode,
    User,
    UserRole,
    UserStatus,
)

router = APIRouter(prefix="/admin", tags=["administration"])


class RoleUpdate(BaseModel):
    role: RoleCode


class StatusUpdate(BaseModel):
    status: UserStatus


class ReferenceCreate(BaseModel):
    code: str
    name: str


class ReferenceUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    active: bool | None = None


async def serialize_user(db: AsyncSession, user: User) -> dict:
    roles = (
        await db.execute(
            select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
        )
    ).scalars().all()
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "status": user.status,
        "roles": roles,
        "created_at": user.created_at,
    }


@router.get("/users")
async def users(
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    total = await db.scalar(select(func.count()).select_from(User)) or 0
    records = (
        await db.execute(
            select(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [await serialize_user(db, user) for user in records],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/users/{user_id}")
async def user_detail(
    user_id: str,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User was not found.")
    return await serialize_user(db, user)


@router.patch("/users/{user_id}/role")
async def update_role(
    user_id: str,
    payload: RoleUpdate,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, user_id)
    role = await db.scalar(select(Role).where(Role.code == payload.role))
    if user is None or role is None:
        raise NotFoundError("User or role was not found.")
    current_roles = (
        await db.execute(
            select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
    ).scalars().all()
    if RoleCode.ADMIN in current_roles and payload.role != RoleCode.ADMIN:
        admin_count = await db.scalar(
            select(func.count())
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .join(User, User.id == UserRole.user_id)
            .where(Role.code == RoleCode.ADMIN, User.status == UserStatus.ACTIVE)
        )
        if (admin_count or 0) <= 1:
            raise ConflictError("The last active administrator cannot be demoted.")
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    db.add(UserRole(user_id=user_id, role_id=role.id, assigned_by=current.id))
    db.add(
        AuditLog(
            actor_user_id=current.id,
            action="user.role_changed",
            target_type="user",
            target_id=user_id,
            metadata_json={"from": [value.value for value in current_roles], "to": payload.role.value},
        )
    )
    await db.commit()
    return await serialize_user(db, user)


@router.patch("/users/{user_id}/status")
async def update_status(
    user_id: str,
    payload: StatusUpdate,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User was not found.")
    if user.id == current.id and payload.status != UserStatus.ACTIVE:
        raise ConflictError("You cannot deactivate your own administrator account.")
    old = user.status
    user.status = payload.status
    db.add(
        AuditLog(
            actor_user_id=current.id,
            action="user.status_changed",
            target_type="user",
            target_id=user_id,
            metadata_json={"from": old.value, "to": payload.status.value},
        )
    )
    await db.commit()
    return await serialize_user(db, user)


@router.get("/audit-logs")
async def audit_logs(
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=200),
) -> list[dict]:
    records = (
        await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    ).scalars().all()
    return [
        {
            "id": item.id,
            "actor_user_id": item.actor_user_id,
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "metadata": item.metadata_json,
            "created_at": item.created_at,
        }
        for item in records
    ]


@router.post("/issue-categories", status_code=201)
async def create_issue_category(
    payload: ReferenceCreate,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = IssueCategory(code=payload.code.upper(), name=payload.name)
    db.add(item)
    await db.commit()
    return {"id": item.id, "code": item.code, "name": item.name}


@router.post("/areas", status_code=201)
async def create_area(
    payload: ReferenceCreate,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = AdministrativeArea(code=payload.code.upper(), name=payload.name)
    db.add(item)
    await db.commit()
    return {"id": item.id, "code": item.code, "name": item.name}


@router.patch("/issue-categories/{category_id}")
async def update_issue_category(
    category_id: str,
    payload: ReferenceUpdate,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await db.get(IssueCategory, category_id)
    if item is None:
        raise NotFoundError("Issue category was not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.upper() if field == "code" and value else value)
    await db.commit()
    return {"id": item.id, "code": item.code, "name": item.name, "active": item.active}


@router.patch("/areas/{area_id}")
async def update_area(
    area_id: str,
    payload: ReferenceUpdate,
    current=Depends(require_role(RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await db.get(AdministrativeArea, area_id)
    if item is None:
        raise NotFoundError("Administrative area was not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.upper() if field == "code" and value else value)
    await db.commit()
    return {"id": item.id, "code": item.code, "name": item.name, "active": item.active}
