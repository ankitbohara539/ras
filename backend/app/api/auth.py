from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.profile import Profile
from app.schema.auth import (
    LoginRequest,
    MessageResponse,
    ProfileResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
)
from app.services.auth_service import (
    login_user,
    refresh_session,
    register_user,
    resend_verification,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    profile, requires_approval, requires_verification = register_user(db, data)

    if requires_verification and requires_approval:
        message = (
            f"We sent a verification link to {profile.email}. Verify your email; "
            "your authority account then also needs administrator approval."
        )
    elif requires_verification:
        message = (
            f"We sent a verification link to {profile.email}. "
            "Open it to activate your account, then sign in."
        )
    elif requires_approval:
        message = "Your authority account is awaiting administrator approval."
    else:
        message = "Account created. You can sign in now."

    return RegisterResponse(
        profile=ProfileResponse.model_validate(profile),
        requires_approval=requires_approval,
        requires_verification=requires_verification,
        message=message,
    )


@router.post("/resend-verification", response_model=MessageResponse)
def resend(data: ResendVerificationRequest) -> MessageResponse:
    resend_verification(data.email)
    # Same answer whether or not the address exists -- see resend_verification.
    return MessageResponse(
        message=(
            "If that address has an account waiting for verification, "
            "a new link is on its way."
        )
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    session, profile = login_user(db, data)

    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=getattr(session, "expires_in", None),
        profile=ProfileResponse.model_validate(profile),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    session = refresh_session(data.refresh_token)
    profile = db.get(Profile, UUID(str(session.user.id)))

    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=getattr(session, "expires_in", None),
        profile=ProfileResponse.model_validate(profile),
    )
