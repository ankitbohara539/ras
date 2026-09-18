from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.emergency import router as emergency_router
from app.api.reference import router as reference_router
from app.api.routes import health
from app.api.tickets import router as tickets_router
from app.api.users import router as users_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(reference_router)
api_router.include_router(tickets_router)
api_router.include_router(emergency_router)
api_router.include_router(admin_router)
