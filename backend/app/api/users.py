import json
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_profile
from app.db.session import get_db
from app.models.profile import Profile
from app.schema.auth import ProfileResponse
from app.schema.user import DashboardIssueOut, DashboardSummaryResponse, ProfileUpdateRequest
from app.services.summary_service import (
    DashboardSummary,
    get_dashboard_summary,
    stream_dashboard_summary,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=ProfileResponse)
def me(profile: Profile = Depends(get_current_profile)) -> ProfileResponse:
    return ProfileResponse.model_validate(profile)


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
    """Update the caller's own profile.

    Role, account_status and scope are deliberately absent -- those are
    changed only by an admin, never by the account holder.
    """
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.flush()
    return ProfileResponse.model_validate(profile)
