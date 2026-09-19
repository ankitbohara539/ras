import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock

from app.core.exceptions import ConflictError
from app.core.events import event_envelope
from app.core.security import hash_password, hash_token, verify_password
from app.modules.emergency.domain.workflow import ensure_emergency_transition
from app.modules.auth.domain.schemas import LoginRequest
from app.modules.issues.domain.workflow import ensure_issue_transition
from app.modules.users.application.service import PreferenceUpdate, UserService
from app.shared.infrastructure.models import (
    EmergencyStatus,
    IssueStatus,
    User,
    UserPreference,
)


def test_argon2id_password_roundtrip_and_token_hashing() -> None:
    password_hash = hash_password("StrongPassword9")
    assert password_hash.startswith("$argon2id$")
    assert verify_password("StrongPassword9", password_hash)
    assert not verify_password("wrong", password_hash)
    assert hash_token("secret") != "secret"
    assert len(hash_token("secret")) == 64


def test_issue_workflow_rejects_invalid_transition() -> None:
    ensure_issue_transition(IssueStatus.REPORTED, IssueStatus.VERIFIED)
    with pytest.raises(ConflictError):
        ensure_issue_transition(IssueStatus.REPORTED, IssueStatus.RESOLVED)


def test_emergency_workflow_requires_ordered_response() -> None:
    ensure_emergency_transition(EmergencyStatus.CREATED, EmergencyStatus.ACKNOWLEDGED)
    with pytest.raises(ConflictError):
        ensure_emergency_transition(EmergencyStatus.CREATED, EmergencyStatus.RESOLVED)


def test_realtime_events_use_versioned_envelope() -> None:
    payload = event_envelope({"type": "issue.created", "data": {"issue_id": "issue-1"}})
    assert payload["event"] == "issue.created"
    assert payload["version"] == 1
    assert payload["data"] == {"issue_id": "issue-1"}
    assert payload["id"]
    assert payload["timestamp"]


def test_reading_preferences_accept_only_supported_values() -> None:
    preferences = PreferenceUpdate(language="ne", text_scale="x-large", high_contrast=True)
    assert preferences.language == "ne"
    assert preferences.text_scale == "x-large"
    assert preferences.high_contrast is True

    with pytest.raises(ValidationError):
        PreferenceUpdate(language="fr")

    with pytest.raises(ValidationError):
        PreferenceUpdate(text_scale="huge")


@pytest.mark.parametrize(
    "email",
    [
        "admin@demo.civicgrid.dev",
        "authority@demo.civicgrid.dev",
        "responder@demo.civicgrid.dev",
        "citizen@demo.civicgrid.dev",
    ],
)
def test_development_login_addresses_are_api_valid(email: str) -> None:
    assert str(LoginRequest(email=email, password="password").email) == email


@pytest.mark.asyncio
async def test_reading_preferences_persist_and_sync_profile_language() -> None:
    stored = UserPreference(
        user_id="user-1",
        language="en",
        text_scale="normal",
        high_contrast=False,
        reduced_motion=False,
        text_to_speech=False,
    )
    user = User(
        id="user-1",
        email="reader@example.com",
        password_hash="unused",
        full_name="Reader",
        preferred_language="en",
    )
    db = AsyncMock()
    db.get.side_effect = lambda model, _id: stored if model is UserPreference else user

    result = await UserService(db).update_preferences(
        "user-1",
        PreferenceUpdate(language="ne", text_scale="large", high_contrast=True),
    )

    assert result.language == "ne"
    assert result.text_scale == "large"
    assert result.high_contrast is True
    assert user.preferred_language == "ne"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(stored)
