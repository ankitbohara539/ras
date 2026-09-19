"""Authentication built on Supabase Auth, with roles held in `profiles`.

Supabase owns credentials and token issuing. This module owns the application
side: creating the matching profile row and deciding whether the account is
usable straight away or has to wait for an admin.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.supabase import new_auth_client
from app.models.enums import AccountStatus, UserRole
from app.models.geography import Ward
from app.models.profile import Profile
from app.schema.auth import LoginRequest, RegisterRequest


# The login error the frontend matches on to show "resend verification email".
EMAIL_NOT_VERIFIED = "Please verify your email first. Check your inbox for the link we sent."


def _verify_redirect() -> str:
    """Where the link in the verification email lands: the login page, which
    then says "email verified, sign in". Must be listed under Supabase ->
    Authentication -> URL Configuration -> Redirect URLs."""
    return f"{get_settings().frontend_url.rstrip('/')}/login?verified=1"


def _supabase_error(exc: Exception, fallback: str) -> HTTPException:
    """Turn a Supabase client error into a proper HTTP response.

    Without this, a wrong password surfaces as a 500 instead of a 401.
    """
    message = getattr(exc, "message", None) or str(exc)
    lowered = message.lower()
    code = str(getattr(exc, "code", "") or "").lower()

    if code == "email_not_confirmed" or "email not confirmed" in lowered:
        # 403 with a stable detail the app recognises, so it can offer to
        # resend the verification email instead of just showing an error.
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=EMAIL_NOT_VERIFIED,
        )
    if code in {"over_email_send_rate_limit", "over_request_rate_limit"} or "rate limit" in lowered:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many emails were sent just now. Wait a few minutes and try again.",
        )
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


def register_user(db: Session, data: RegisterRequest) -> tuple[Profile, bool, bool]:
    """Create an auth user plus its profile.

    Returns (profile, needs_approval, needs_verification).

    Goes through Supabase's ordinary sign-up so its "Confirm email" setting
    applies: with it on, Supabase emails a verification link and refuses to
    sign the user in until it is clicked; with it off, the account works at
    once. (The previous admin.create_user call marked every email verified
    on the spot, which silently bypassed that setting.)
    """
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

    # A throwaway client: with confirmation off, sign_up returns a session
    # and stores it on the client, like sign-in does.
    supabase = new_auth_client()
    try:
        result = supabase.auth.sign_up(
            {
                "email": data.email,
                "password": data.password,
                "options": {
                    "data": {"full_name": data.full_name},
                    "email_redirect_to": _verify_redirect(),
                },
            }
        )
    except Exception as exc:
        raise _supabase_error(exc, "Could not create the account") from exc

    if result.user is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase did not return a user.",
        )

    # With confirmation on, signing up an address that already exists does
    # not error -- Supabase returns a stand-in user with no identities, so as
    # not to reveal which emails are registered. Our profile table knows.
    if not result.user.identities or db.get(Profile, UUID(str(result.user.id))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    needs_verification = result.user.email_confirmed_at is None

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

    return profile, needs_approval, needs_verification


def resend_verification(email: str) -> None:
    """Send the sign-up verification email again.

    Deliberately silent about whether the address exists or is already
    verified -- the endpoint answers the same either way -- so it cannot be
    used to find out who has an account. Rate limits are the one error worth
    passing on, because the user can act on it.
    """
    try:
        new_auth_client().auth.resend(
            {
                "type": "signup",
                "email": email,
                "options": {"email_redirect_to": _verify_redirect()},
            }
        )
    except Exception as exc:
        error = _supabase_error(exc, "Could not send the email")
        if error.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise error from exc


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
