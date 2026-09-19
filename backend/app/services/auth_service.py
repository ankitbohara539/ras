"""Authentication built on Supabase Auth, with roles held in `profiles`.

Supabase owns credentials and token issuing. This module owns the application
side: creating the matching profile row and deciding whether the account is
usable straight away or has to wait for an admin.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.supabase import get_supabase, new_auth_client
from app.models.enums import AccountStatus, UserRole
from app.models.geography import Ward
from app.models.profile import Profile
from app.schema.auth import LoginRequest, RegisterRequest


def _supabase_error(exc: Exception, fallback: str) -> HTTPException:
    """Turn a Supabase client error into a proper HTTP response.

    Without this, a wrong password surfaces as a 500 instead of a 401.
    """
    message = getattr(exc, "message", None) or str(exc)
    lowered = message.lower()

    if "already registered" in lowered or "already been registered" in lowered:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    if "invalid login" in lowered or "invalid credentials" in lowered:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if "password" in lowered:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message,
        )

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"{fallback}: {message}",
    )


def _resolve_scope(
    db: Session, data: RegisterRequest
) -> tuple[UUID | None, UUID | None]:
    """Derive (municipality_id, ward_id), filling municipality from the ward."""
    if data.ward_id is None:
        return data.municipality_id, None

    ward = db.get(Ward, data.ward_id)
    if ward is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown ward.",
        )
    return ward.municipality_id, ward.id


def register_user(db: Session, data: RegisterRequest) -> tuple[Profile, bool]:
    """Create an auth user plus its profile. Returns (profile, needs_approval)."""
    if data.requested_role is UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be self-registered.",
        )

    needs_approval = data.requested_role is UserRole.AUTHORITY

    if needs_approval and data.municipality_id is None and data.ward_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An authority account must name the municipality it serves.",
        )

    municipality_id, ward_id = _resolve_scope(db, data)

    supabase = get_supabase()
    try:
        # admin.create_user rather than sign_up: it confirms the email inline,
        # so demo accounts work immediately without an inbox round-trip.
        result = supabase.auth.admin.create_user(
            {
                "email": data.email,
                "password": data.password,
                "email_confirm": True,
                "user_metadata": {"full_name": data.full_name},
            }
        )
    except Exception as exc:
        raise _supabase_error(exc, "Could not create the account") from exc

    if result.user is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return a user.",
        )

    profile = Profile(
        id=UUID(str(result.user.id)),
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        role=data.requested_role,
        account_status=(
            AccountStatus.PENDING if needs_approval else AccountStatus.ACTIVE
        ),
        municipality_id=municipality_id,
        ward_id=ward_id,
        preferred_language=data.preferred_language,
    )
    db.add(profile)
    db.flush()

    return profile, needs_approval


def login_user(db: Session, data: LoginRequest) -> tuple[object, Profile]:
    """Verify credentials and return (session, profile)."""
    # A throwaway client: sign_in_with_password stores the session on the
    # client it is called on, which would downgrade the shared service-role
    # client to this user for every subsequent request in the process.
    supabase = new_auth_client()
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": data.email, "password": data.password}
        )
    except Exception as exc:
        raise _supabase_error(exc, "Could not sign in") from exc

    if result.session is None or result.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    profile = db.scalar(
        select(Profile).where(Profile.id == UUID(str(result.user.id)))
    )
    if profile is None:
        # The auth user exists but has no profile -- a half-finished signup.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no profile. Contact an administrator.",
        )

    if profile.account_status is AccountStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is awaiting administrator approval.",
        )
    if profile.account_status is not AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is {profile.account_status.value}.",
        )

    return result.session, profile


def refresh_session(refresh_token: str) -> object:
    # Same reasoning as login: refreshing establishes a user session.
    supabase = new_auth_client()
    try:
        result = supabase.auth.refresh_session(refresh_token)
    except Exception as exc:
        raise _supabase_error(exc, "Could not refresh the session") from exc

    if result.session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )
    return result.session
