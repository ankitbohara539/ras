from fastapi import APIRouter
from fastapi import Depends

from app.core.security import get_current_user

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("/me")
def me(user=Depends(get_current_user)):

    return {
        "id": user.id,
        "email": user.email
    }