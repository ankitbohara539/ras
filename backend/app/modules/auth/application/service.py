from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.email import EmailService, password_reset_email
from app.core.exceptions import AppError, AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_ip,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.auth.domain.schemas import RegisterRequest
from app.shared.infrastructure.models import (
    PasswordResetToken,
    RefreshSession,
    Role,
    RoleCode,
    User,
    UserPreference,
    UserRole,
    UserStatus,
    utcnow,
)


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_max_age: int
    refresh_max_age: int


async def user_roles(db: AsyncSession, user_id: str) -> list[RoleCode]:
    result = await db.execute(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return list(result.scalars().all())


class AuthService:
    def __init__(self, db: AsyncSession, email_service: EmailService) -> None:
        self.db = db
        self.email_service = email_service
        self.settings = get_settings()

    async def register(self, request: RegisterRequest) -> None:
        normalized = request.email.strip().lower()
        if await self.db.scalar(select(User.id).where(User.email_normalized == normalized)):
            raise ConflictError("An account with this email already exists.")
        citizen_role = await self.db.scalar(select(Role).where(Role.code == RoleCode.CITIZEN))
        if citizen_role is None:
            raise AppError("CONFIGURATION_ERROR", "Reference roles have not been seeded.", 503)
        user = User(
            full_name=request.full_name.strip(),
            email=request.email.strip(),
            email_normalized=normalized,
            password_hash=hash_password(request.password),
            status=UserStatus.ACTIVE,
        )
        self.db.add(user)
        await self.db.flush()
        self.db.add_all(
            [
                UserRole(user_id=user.id, role_id=citizen_role.id),
                UserPreference(user_id=user.id),
            ]
        )
        await self.db.commit()

    async def login(
        self, email: str, password: str, user_agent: str | None, ip_address: str | None
    ) -> TokenPair:
        user = await self.db.scalar(select(User).where(User.email_normalized == email.strip().lower()))
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if user.status != UserStatus.ACTIVE:
            raise AppError("ACCOUNT_SUSPENDED", "This account is not active.", 403)
        roles = await user_roles(self.db, user.id)
        return await self._create_session(user, roles, user_agent, ip_address)

    async def _create_session(
        self,
        user: User,
        roles: list[RoleCode],
        user_agent: str | None,
        ip_address: str | None,
        family_id: str | None = None,
    ) -> TokenPair:
        raw_refresh = generate_opaque_token()
        session = RefreshSession(
            user_id=user.id,
            family_id=family_id or str(uuid4()),
            token_hash=hash_token(raw_refresh),
            expires_at=utcnow() + timedelta(days=self.settings.refresh_token_days),
            user_agent=(user_agent or "")[:500] or None,
            ip_hash=hash_ip(ip_address),
        )
        self.db.add(session)
        await self.db.flush()
        access = create_access_token(user.id, session.id, [role.value for role in roles])
        await self.db.commit()
        return TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
            access_max_age=self.settings.jwt_access_token_minutes * 60,
            refresh_max_age=self.settings.refresh_token_days * 86_400,
        )

    async def rotate(
        self, raw_refresh: str, user_agent: str | None, ip_address: str | None
    ) -> TokenPair:
        session = await self.db.scalar(
            select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw_refresh))
        )
        if session is None:
            raise AuthenticationError("The refresh session is invalid.")
        if session.revoked_at is not None:
            await self.db.execute(
                update(RefreshSession)
                .where(RefreshSession.family_id == session.family_id, RefreshSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
            await self.db.commit()
            raise AuthenticationError("Refresh token reuse was detected. Sign in again.")
        if session.expires_at <= utcnow():
            raise AuthenticationError("The refresh session has expired.")
        user = await self.db.get(User, session.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("The account is not active.")
        session.revoked_at = utcnow()
        session.last_used_at = utcnow()
        roles = await user_roles(self.db, user.id)
        pair = await self._create_session(user, roles, user_agent, ip_address, session.family_id)
        replacement = await self.db.scalar(
            select(RefreshSession)
            .where(RefreshSession.family_id == session.family_id)
            .order_by(RefreshSession.created_at.desc())
        )
        session.replaced_by_id = replacement.id if replacement else None
        await self.db.commit()
        return pair

    async def logout(self, raw_refresh: str | None) -> None:
        if raw_refresh:
            session = await self.db.scalar(
                select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw_refresh))
            )
            if session and session.revoked_at is None:
                session.revoked_at = utcnow()
                await self.db.commit()

    async def forgot_password(self, email: str) -> None:
        user = await self.db.scalar(select(User).where(User.email_normalized == email.strip().lower()))
        if user is None or user.status == UserStatus.DISABLED:
            return
        await self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=utcnow())
        )
        raw_token = generate_opaque_token()
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        await self.db.commit()
        reset_url = f"{self.settings.frontend_url}/reset-password?token={raw_token}"
        try:
            await self.email_service.send(user.email, *password_reset_email(reset_url))
        except Exception:
            return

    async def reset_password(self, raw_token: str, password: str) -> None:
        token = await self.db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
        )
        if token is None or token.used_at is not None or token.expires_at <= utcnow():
            raise AppError("INVALID_RESET_TOKEN", "This reset link is invalid or expired.", 400)
        user = await self.db.get(User, token.user_id)
        if user is None:
            raise AppError("INVALID_RESET_TOKEN", "This reset link is invalid or expired.", 400)
        token.used_at = utcnow()
        user.password_hash = hash_password(password)
        await self.db.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await self.db.commit()
