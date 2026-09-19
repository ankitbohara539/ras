from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.docs import API_DESCRIPTION, OPENAPI_TAGS, configure_openapi
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import RateLimitMiddleware

settings = get_settings()
configure_logging()
documentation_enabled = settings.app_env == "development"

app = FastAPI(
    title=settings.app_name,
    summary="Smart-community reporting, civic services, alerts, and emergency coordination",
    description=API_DESCRIPTION,
    version="0.2.0",
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "CivicGrid API support"},
    servers=[{"url": "/", "description": "Current API server"}],
    docs_url="/docs" if documentation_enabled else None,
    redoc_url="/redoc" if documentation_enabled else None,
    openapi_url="/openapi.json" if documentation_enabled else None,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "tagsSorter": "alpha",
        "operationsSorter": "method",
    },
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)
app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_prefix)
configure_openapi(
    app,
    api_prefix=settings.api_prefix,
    access_cookie_name=settings.access_cookie_name,
    refresh_cookie_name=settings.refresh_cookie_name,
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request contains invalid data.",
                "request_id": getattr(request.state, "request_id", ""),
                "details": error.errors(),
            }
        },
    )


@app.get("/", tags=["system"], summary="Discover the API")
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/health/live"}


@app.get(settings.api_prefix, tags=["system"], summary="Discover the versioned API")
async def api_index() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": app.version,
        "api_prefix": settings.api_prefix,
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "health": "/health/ready",
        "registration": f"POST {settings.api_prefix}/auth/register",
    }
