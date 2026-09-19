from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.events import event_bus
from app.modules.auth.presentation.dependencies import CurrentUser, require_any_role
from app.modules.issues.application.service import (
    IssueCreate,
    IssueAssign,
    IssueItem,
    IssuePage,
    IssueService,
    IssueStatusChange,
    IssueUpdate,
)
from app.modules.issues.infrastructure.storage import ObjectStoragePort, get_object_storage
from app.shared.infrastructure.models import (
    Issue,
    IssueCategory,
    IssueMedia,
    IssueStatus,
    IssueStatusHistory,
    RoleCode,
)

router = APIRouter(prefix="/issues", tags=["issues"])


def service(db: AsyncSession = Depends(get_db)) -> IssueService:
    return IssueService(db, event_bus)


@router.post("", response_model=IssueItem, status_code=201)
async def create_issue(
    payload: IssueCreate,
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
) -> IssueItem:
    return await use_case.create(current.id, payload)


@router.get("", response_model=IssuePage)
async def list_issues(
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: IssueStatus | None = None,
    mine: bool = False,
) -> IssuePage:
    return await use_case.list(page, page_size, current.id if mine else None, status)


@router.get("/nearby", response_model=IssuePage)
async def nearby_issues(
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius: int = Query(2_000, ge=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> IssuePage:
    radius = min(radius, get_settings().max_nearby_radius_meters)
    return await use_case.nearby(lat, lng, radius, page, page_size)


@router.get("/categories")
async def issue_categories(
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, str]]:
    rows = (
        await db.execute(
            select(IssueCategory)
            .where(IssueCategory.active.is_(True))
            .order_by(IssueCategory.name)
        )
    ).scalars().all()
    return [{"id": item.id, "code": item.code, "name": item.name} for item in rows]


@router.get("/{issue_id}", response_model=IssueItem)
async def get_issue(
    issue_id: str,
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
) -> IssueItem:
    return await use_case.get(issue_id)


@router.patch("/{issue_id}", response_model=IssueItem)
async def update_issue(
    issue_id: str,
    payload: IssueUpdate,
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
) -> IssueItem:
    privileged = bool(set(current.roles).intersection({RoleCode.AUTHORITY, RoleCode.ADMIN}))
    return await use_case.update_details(issue_id, current.id, privileged, payload)


@router.post("/{issue_id}/media", status_code=201)
async def upload_issue_media(
    issue_id: str,
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[ObjectStoragePort, Depends(get_object_storage)],
    file: UploadFile = File(...),
) -> dict[str, str | int]:
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed:
        from app.core.exceptions import AppError

        raise AppError("STORAGE_ERROR", "Only JPEG, PNG, and WebP images are allowed.", 400)
    issue = await db.get(Issue, issue_id)
    if issue is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("The requested issue was not found.")
    if issue.reporter_id != current.id and not set(current.roles).intersection(
        {RoleCode.AUTHORITY, RoleCode.ADMIN}
    ):
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError()
    media_count = await db.scalar(
        select(func.count()).select_from(IssueMedia).where(IssueMedia.issue_id == issue_id)
    )
    if (media_count or 0) >= 5:
        from app.core.exceptions import AppError

        raise AppError("STORAGE_ERROR", "A report can contain at most five images.", 400)
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        from app.core.exceptions import AppError

        raise AppError("STORAGE_ERROR", "Images must be 5 MB or smaller.", 400)
    key = await storage.save(content, allowed[file.content_type])
    media = IssueMedia(
        issue_id=issue_id,
        storage_key=key,
        content_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(media)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await storage.delete(key)
        raise
    return {"id": media.id, "storage_key": key, "size_bytes": len(content)}


@router.post("/{issue_id}/confirm", status_code=204)
async def confirm_issue(
    issue_id: str,
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
) -> None:
    await use_case.confirm(issue_id, current.id)


@router.delete("/{issue_id}/confirm", status_code=204)
async def unconfirm_issue(
    issue_id: str,
    current: CurrentUser,
    use_case: Annotated[IssueService, Depends(service)],
) -> None:
    await use_case.unconfirm(issue_id, current.id)


@router.post("/{issue_id}/verify", response_model=IssueItem)
async def verify_issue(
    issue_id: str,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    use_case: IssueService = Depends(service),
) -> IssueItem:
    return await use_case.change_status(
        issue_id, current.id, IssueStatusChange(status=IssueStatus.VERIFIED, note="Report verified")
    )


@router.post("/{issue_id}/assign", response_model=IssueItem)
async def assign_issue(
    issue_id: str,
    payload: IssueAssign,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    use_case: IssueService = Depends(service),
) -> IssueItem:
    return await use_case.assign(issue_id, current.id, payload)


@router.post("/{issue_id}/status", response_model=IssueItem)
async def change_issue_status(
    issue_id: str,
    payload: IssueStatusChange,
    current=Depends(require_any_role(RoleCode.AUTHORITY, RoleCode.ADMIN)),
    use_case: IssueService = Depends(service),
) -> IssueItem:
    return await use_case.change_status(issue_id, current.id, payload)


@router.get("/{issue_id}/history")
async def issue_history(
    issue_id: str,
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, str | None]]:
    rows = (
        await db.execute(
            select(IssueStatusHistory)
            .where(IssueStatusHistory.issue_id == issue_id)
            .order_by(IssueStatusHistory.created_at)
        )
    ).scalars().all()
    return [
        {
            "from_status": row.from_status.value if row.from_status else None,
            "to_status": row.to_status.value,
            "note": row.note,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
