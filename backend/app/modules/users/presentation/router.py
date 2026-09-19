from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.domain.schemas import CurrentUserResponse
from app.modules.auth.presentation.dependencies import CurrentUser
from app.modules.users.application.service import PreferenceUpdate, ProfileUpdate, UserService

router = APIRouter(prefix="/users", tags=["users"])


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    language: str
    text_scale: str
    high_contrast: bool
    reduced_motion: bool
    text_to_speech: bool


@router.get("/me", response_model=CurrentUserResponse)
async def get_profile(current: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate({**current.user.__dict__, "roles": current.roles})


@router.patch("/me", response_model=CurrentUserResponse)
async def update_profile(
    payload: ProfileUpdate,
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUserResponse:
    user = await UserService(db).update_profile(current.id, payload)
    return CurrentUserResponse.model_validate({**user.__dict__, "roles": current.roles})


@router.get("/me/preferences", response_model=PreferenceResponse)
async def get_preferences(
    current: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> PreferenceResponse:
    return PreferenceResponse.model_validate(await UserService(db).preferences(current.id))


@router.patch("/me/preferences", response_model=PreferenceResponse)
async def update_preferences(
    payload: PreferenceUpdate,
    current: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreferenceResponse:
    result = await UserService(db).update_preferences(current.id, payload)
    return PreferenceResponse.model_validate(result)
