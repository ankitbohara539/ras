from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_profile
from app.db.session import get_db
from app.models.profile import Profile
from app.schema.auth import ProfileResponse
from app.schema.user import ProfileUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=ProfileResponse)
def me(profile: Profile = Depends(get_current_profile)) -> ProfileResponse:
    return ProfileResponse.model_validate(profile)


@router.patch("/me", response_model=ProfileResponse)
def update_me(
    data: ProfileUpdateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update the caller's own profile.

    Role, account_status and scope are deliberately absent -- those are
    changed only by an admin, never by the account holder.
    """
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.flush()
    return ProfileResponse.model_validate(profile)
