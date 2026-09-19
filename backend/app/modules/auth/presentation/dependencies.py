from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.modules.auth.application.service import user_roles
from app.shared.infrastructure.models import RefreshSession, RoleCode, User, UserStatus


@dataclass(slots=True)
class AuthenticatedUser:
    user: User
    roles: list[RoleCode]
    session_id: str

    @property
    def id(self) -> str:
        return self.user.id


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    settings = get_settings()
    token = request.cookies.get(settings.access_cookie_name)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise AuthenticationError()
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Your session is invalid or expired.") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid access token.")
    session = await db.scalar(
        select(RefreshSession).where(
            RefreshSession.id == payload["sid"], RefreshSession.revoked_at.is_(None)
        )
    )
    user = await db.get(User, payload["sub"])
    if session is None or user is None:
        raise AuthenticationError("Your session is no longer active.")
    if user.status == UserStatus.SUSPENDED:
        raise AuthenticationError("This account is suspended.")
    if user.status != UserStatus.ACTIVE:
        raise AuthenticationError("This account is not active.")
    roles = await user_roles(db, user.id)
    return AuthenticatedUser(user=user, roles=roles, session_id=session.id)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_any_role(*allowed: RoleCode):
    async def dependency(current: CurrentUser) -> AuthenticatedUser:
        if not set(current.roles).intersection(allowed):
            raise AuthorizationError()
        return current

    return dependency


def require_role(role: RoleCode):
    return require_any_role(role)
