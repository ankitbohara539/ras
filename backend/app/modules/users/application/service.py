from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.shared.infrastructure.models import User, UserPreference


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    avatar_url: str | None = Field(default=None, max_length=500)
    preferred_language: str | None = Field(default=None, pattern="^(en|ne)$")


class PreferenceUpdate(BaseModel):
    language: str | None = Field(default=None, pattern="^(en|ne)$")
    text_scale: str | None = Field(default=None, pattern="^(normal|large|x-large)$")
    high_contrast: bool | None = None
    reduced_motion: bool | None = None
    text_to_speech: bool | None = None


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_profile(self, user_id: str, payload: ProfileUpdate) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User was not found.")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value.strip() if isinstance(value, str) else value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def preferences(self, user_id: str) -> UserPreference:
        preferences = await self.db.get(UserPreference, user_id)
        if preferences is None:
            preferences = UserPreference(user_id=user_id)
            self.db.add(preferences)
            await self.db.commit()
            await self.db.refresh(preferences)
        return preferences

    async def update_preferences(
        self, user_id: str, payload: PreferenceUpdate
    ) -> UserPreference:
        preferences = await self.preferences(user_id)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in changes.items():
            setattr(preferences, field, value)
        if "language" in changes:
            user = await self.db.get(User, user_id)
            if user is None:
                raise NotFoundError("User was not found.")
            user.preferred_language = changes["language"]
        await self.db.commit()
        await self.db.refresh(preferences)
        return preferences
