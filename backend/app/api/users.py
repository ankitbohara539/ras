import json
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_current_profile, require_authority
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.geography import Ward
from app.models.profile import Profile
from app.schema.admin import ProfileListResponse
from app.schema.auth import ProfileResponse
from app.schema.user import AvatarResponse, DashboardIssueOut, DashboardSummaryResponse, ProfileUpdateRequest
from app.services.auth_service import update_auth_email
from app.services.storage_service import read_and_validate, remove_photos, signed_url, upload_photo
from app.services.summary_service import (
    DashboardSummary,
    get_dashboard_summary,
    stream_dashboard_summary,
)

router = APIRouter(prefix="/users", tags=["Users"])


def _profile_response(profile: Profile) -> ProfileResponse:
    """Return the caller's profile with a usable private-avatar URL."""
    response = ProfileResponse.model_validate(profile)
    return response.model_copy(
        update={
            "avatar_url": signed_url(profile.avatar_path)
            if profile.avatar_path
            else None
        }
    )


@router.get("/me", response_model=ProfileResponse)
def me(profile: Profile = Depends(get_current_profile)) -> ProfileResponse:
    return _profile_response(profile)


@router.get("/ward/civilians", response_model=ProfileListResponse)
def ward_civilians(
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> ProfileListResponse:
    """Directory for the authority's assigned operational area only."""
    filters = [Profile.role == UserRole.CITIZEN]
    if authority.role is not UserRole.ADMIN:
        if authority.ward_id is not None:
            filters.append(Profile.ward_id == authority.ward_id)
        elif authority.municipality_id is not None:
            filters.append(Profile.municipality_id == authority.municipality_id)
        else:
            filters.append(Profile.id.is_(None))
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            func.lower(Profile.email).like(pattern)
            | func.lower(func.coalesce(Profile.full_name, "")).like(pattern)
        )
    total = db.scalar(select(func.count()).select_from(Profile).where(*filters)) or 0
    rows = db.scalars(
        select(Profile).where(*filters).order_by(Profile.full_name, Profile.email).limit(limit).offset(offset)
    ).all()
    return ProfileListResponse(items=[ProfileResponse.model_validate(row) for row in rows], total=total)


@router.get("/me/summary", response_model=DashboardSummaryResponse)
def my_dashboard_summary(
    refresh: bool = Query(default=False),
    lang: Literal["en", "ne"] | None = Query(default=None),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    """The dashboard's "briefing" button: one short sentence plus a real
    list of tickets -- a citizen's own reports and their ward's most-
    reported open issues, or an officer's own highest-priority open
    tickets -- built from real numbers. The sentence is written by our own
    model (an open-weight instruct model, see app.core.huggingface) when it
    is configured and by a template when it is not; the issue list is
    always real ticket data, never AI text.

    Cached for a few minutes; pass `refresh=true` to regenerate on the spot
    (rate-limited to once a minute per person, on top of the cache, because
    free inference is one shared budget for the whole deployment).
    """
    return _to_response(get_dashboard_summary(db, profile, refresh, lang))


@router.get("/me/summary/stream")
def my_dashboard_summary_stream(
    refresh: bool = Query(default=False),
    lang: Literal["en", "ne"] | None = Query(default=None),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """The same briefing, written out live like a chat reply: one JSON object
    per line -- {"type": "meta", "summary": ...} with the real numbers and
    issue list, then {"type": "delta", "text": ...} pieces as the model
    writes the sentence, then {"type": "done", "summary": ...}. A
    {"type": "reset"} means discard the text so far (the model failed
    midway; the template sentence follows). `lang` is the language the app
    is showing right now; it defaults to the profile's saved preference."""
    events = stream_dashboard_summary(db, profile, refresh, lang)

    def body():
        for kind, value in events:
            if kind in ("meta", "done"):
                line = {"type": kind, "summary": _to_response(value).model_dump(mode="json")}
            elif kind == "delta":
                line = {"type": kind, "text": value}
            else:
                line = {"type": kind}
            yield json.dumps(line, ensure_ascii=False) + "\n"

    return StreamingResponse(
        body(),
        media_type="application/x-ndjson",
        # Stop proxies (nginx, Render's edge) from holding pieces back until
        # the whole answer is ready -- that would undo the point of streaming.
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


def _to_response(summary: DashboardSummary) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        audience=summary.audience,
        text=summary.text,
        ai_generated=summary.ai_generated,
        generated_at=summary.generated_at,
        scope_label=summary.scope_label,
        issues=[
            DashboardIssueOut(
                id=i.id,
                code=i.code,
                title=i.title,
                priority=i.priority,
                status=i.status,
                reporters=i.reporters,
                age_days=i.age_days,
            )
            for i in summary.issues
        ],
        total_reports=summary.total_reports,
        open_reports=summary.open_reports,
        ward_open_reports=summary.ward_open_reports,
        open_reports_officer=summary.open_reports_officer,
        needs_attention=summary.needs_attention,
        oldest_open_days=summary.oldest_open_days,
        top_category_name=summary.top_category_name,
        top_category_count=summary.top_category_count,
        pending_duplicates=summary.pending_duplicates,
        open_sos=summary.open_sos,
        pending_civic=summary.pending_civic,
    )


@router.patch("/me", response_model=ProfileResponse)
def update_me(
    data: ProfileUpdateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update the caller's own profile, without allowing scope escalation.

    Citizens can correct their home ward. Authority ward assignment controls
    what they are allowed to access, so that remains an administrator action.
    """
    payload = data.model_dump(exclude_unset=True)
    if "ward_id" in payload:
        if profile.role is UserRole.AUTHORITY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can change an authority account's ward.",
            )
        ward_id = payload.pop("ward_id")
        if ward_id is None:
            profile.ward_id = None
            profile.municipality_id = None
        else:
            ward = db.get(Ward, ward_id)
            if ward is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown ward.")
            profile.ward_id = ward.id
            profile.municipality_id = ward.municipality_id

    if "email" in payload:
        email = str(payload.pop("email"))
        if email != profile.email:
            other = db.scalar(select(Profile.id).where(Profile.email == email, Profile.id != profile.id))
            if other is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
            update_auth_email(profile.id, email)
            profile.email = email

    for field, value in payload.items():
        setattr(profile, field, value)

    db.flush()
    return _profile_response(profile)


@router.get("/me/avatar", response_model=AvatarResponse)
def my_avatar(profile: Profile = Depends(get_current_profile)) -> AvatarResponse:
    return AvatarResponse(url=signed_url(profile.avatar_path) if profile.avatar_path else None)


@router.put("/me/avatar", response_model=ProfileResponse)
async def update_my_avatar(
    avatar: UploadFile = File(...),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    payload = await read_and_validate(avatar)
    path = upload_photo(payload, f"avatars/{profile.id}", avatar.content_type or "image/jpeg")
    previous = profile.avatar_path
    profile.avatar_path = path
    db.flush()
    if previous:
        remove_photos([previous])
    return _profile_response(profile)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_avatar(
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> None:
    previous = profile.avatar_path
    profile.avatar_path = None
    db.flush()
    if previous:
        remove_photos([previous])
