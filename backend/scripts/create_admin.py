"""Create or safely promote the initial administrator."""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

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


async def create_or_promote(email: str, full_name: str) -> None:
    normalized = email.strip().lower()
    async with AsyncSessionFactory() as db:
        admin_role = await db.scalar(select(Role).where(Role.code == RoleCode.ADMIN))
        if admin_role is None:
            raise RuntimeError("Run alembic upgrade head before creating an administrator.")
        user = await db.scalar(select(User).where(User.email_normalized == normalized))
        action = "admin.promoted"
        if user is None:
            password = getpass.getpass("Initial admin password: ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation or len(password) < 12:
                raise ValueError("Passwords must match and contain at least 12 characters.")
            user = User(
                full_name=full_name.strip(),
                email=email.strip(),
                email_normalized=normalized,
                password_hash=hash_password(password),
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            await db.flush()
            db.add(UserPreference(user_id=user.id))
            action = "admin.created"
        existing = await db.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id, UserRole.role_id == admin_role.id
            )
        )
        if existing:
            print("Administrator already exists; no changes made.")
            return
        user.status = UserStatus.ACTIVE
        db.add(UserRole(user_id=user.id, role_id=admin_role.id, assigned_by=None))
        db.add(
            AuditLog(
                actor_user_id=None,
                action=action,
                target_type="user",
                target_id=user.id,
                metadata_json={"source": "create_admin_cli"},
            )
        )
        await db.commit()
        print(f"Administrator ready: {normalized}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Platform Administrator")
    args = parser.parse_args()
    asyncio.run(create_or_promote(args.email, args.name))
