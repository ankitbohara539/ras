from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.email import EmailService, get_email_service
from app.modules.auth.application.service import AuthService
from app.modules.auth.domain.schemas import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.modules.auth.presentation.dependencies import CurrentUser

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


def set_auth_cookies(response: Response, access: str, refresh: str, access_age: int, refresh_age: int) -> None:
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
    }
    response.set_cookie(
        settings.access_cookie_name,
        access,
        max_age=access_age,
        path="/",
        **common,
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh,
        max_age=refresh_age,
        path=f"{settings.api_prefix}/auth",
        **common,
    )


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    await AuthService(db, email).register(payload)
    return MessageResponse(message="Account created. You can sign in immediately.")


@router.post("/login", response_model=MessageResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    pair = await AuthService(db, email).login(
        payload.email,
        payload.password,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    set_auth_cookies(
        response, pair.access_token, pair.refresh_token, pair.access_max_age, pair.refresh_max_age
    )
    return MessageResponse(message="Signed in.")


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        from app.core.exceptions import AuthenticationError

        raise AuthenticationError("No refresh session was provided.")
    pair = await AuthService(db, email).rotate(
        refresh_token,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    set_auth_cookies(
        response, pair.access_token, pair.refresh_token, pair.access_max_age, pair.refresh_max_age
    )
    return MessageResponse(message="Session refreshed.")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    await AuthService(db, email).logout(request.cookies.get(settings.refresh_cookie_name))
    response.delete_cookie(settings.access_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path=f"{settings.api_prefix}/auth")
    return MessageResponse(message="Signed out.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    await AuthService(db, email).forgot_password(payload.email)
    return MessageResponse(message="If the account exists, password reset instructions have been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: Annotated[EmailService, Depends(get_email_service)],
) -> MessageResponse:
    await AuthService(db, email).reset_password(payload.token, payload.password)
    return MessageResponse(message="Password updated. Sign in with your new password.")


@router.get("/me", response_model=CurrentUserResponse)
async def me(current: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(
        {**current.user.__dict__, "roles": current.roles}
    )
