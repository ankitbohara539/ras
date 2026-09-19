from fastapi import APIRouter

from app.core.websocket import router as websocket_router
from app.modules.administration.presentation.router import router as administration_router
from app.modules.alerts.presentation.router import router as alerts_router
from app.modules.auth.presentation.router import router as auth_router
from app.modules.civic_services.presentation.router import router as services_router
from app.modules.emergency.presentation.router import router as emergency_router
from app.modules.issues.presentation.router import router as issues_router
from app.modules.maps.presentation.router import router as maps_router
from app.modules.notifications.presentation.router import router as notifications_router
from app.modules.users.presentation.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(issues_router)
api_router.include_router(maps_router)
api_router.include_router(services_router)
api_router.include_router(emergency_router)
api_router.include_router(alerts_router)
api_router.include_router(notifications_router)
api_router.include_router(administration_router)
api_router.include_router(websocket_router)
