"""Seed predictable local-development users for every RBAC role.

This script intentionally resets these dedicated accounts to their documented
passwords on every run. It refuses to run in staging or production.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.security import hash_password
from app.shared.infrastructure.models import (
    AuditLog,
    Role,
    RoleCode,
    User,
    UserPreference,
    UserRole,
    UserStatus,
)


DEVELOPMENT_USERS = (
    (RoleCode.ADMIN, "CivicGrid Administrator", "admin@demo.civicgrid.dev", "CivicGridAdmin@2026!", "admin@civicgrid.local"),
    (RoleCode.AUTHORITY, "Municipal Authority", "authority@demo.civicgrid.dev", "CivicGridAuthority@2026!", "authority@civicgrid.local"),
    (RoleCode.RESPONDER, "Emergency Responder", "responder@demo.civicgrid.dev", "CivicGridResponder@2026!", "responder@civicgrid.local"),
    (RoleCode.CITIZEN, "Community Citizen", "citizen@demo.civicgrid.dev", "CivicGridCitizen@2026!", "citizen@civicgrid.local"),
)


async def seed_development_users() -> None:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise RuntimeError("Development users cannot be seeded outside development or test.")

    async with AsyncSessionFactory() as db:
        roles = {role.code: role for role in (await db.scalars(select(Role))).all()}
        missing = [role.value for role, *_ in DEVELOPMENT_USERS if role not in roles]
        if missing:
            raise RuntimeError(
                f"Missing roles: {', '.join(missing)}. Run alembic upgrade head first."
            )

        for role_code, full_name, email, password, legacy_email in DEVELOPMENT_USERS:
            normalized = email.lower()
            user = await db.scalar(select(User).where(User.email_normalized == normalized))
            if user is None:
                user = await db.scalar(
                    select(User).where(User.email_normalized == legacy_email.lower())
                )
            action = "development_user.updated"
            if user is None:
                user = User(
                    full_name=full_name,
                    email=email,
                    email_normalized=normalized,
                    password_hash=hash_password(password),
                    status=UserStatus.ACTIVE,
                )
                db.add(user)
                await db.flush()
                action = "development_user.created"
            else:
                user.full_name = full_name
                user.email = email
                user.email_normalized = normalized
                user.password_hash = hash_password(password)
                user.status = UserStatus.ACTIVE

            if await db.get(UserPreference, user.id) is None:
                db.add(UserPreference(user_id=user.id))

            role = roles[role_code]
            assignment = await db.scalar(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == role.id,
                )
            )
            if assignment is None:
                db.add(UserRole(user_id=user.id, role_id=role.id, assigned_by=None))

            db.add(
                AuditLog(
                    actor_user_id=None,
                    action=action,
                    target_type="user",
                    target_id=user.id,
                    metadata_json={"source": "seed_development_users", "role": role_code.value},
                )
            )

        await db.commit()

    print("Development users are ready:")
    for role, _name, email, password, _legacy_email in DEVELOPMENT_USERS:
        print(f"  {role.value:<9} {email:<34} {password}")


if __name__ == "__main__":
    asyncio.run(seed_development_users())
