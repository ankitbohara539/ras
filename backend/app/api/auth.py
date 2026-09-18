from fastapi import APIRouter

from app.schema.auth import RegisterRequest
from app.services.auth_service import (
    register_user,
    login_user
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

@router.post("/register")
def register(data: RegisterRequest):

    result = register_user(
        data.email,
        data.password
    )

    return {
        "id": result.user.id,
        "email": result.user.email
    }


@router.post("/login")
def login(data: RegisterRequest):

    result = login_user(
        data.email,
        data.password
    )

    return {
        "access_token":
        result.session.access_token,

        "refresh_token":
        result.session.refresh_token,

        "user_id":
        result.user.id
    }