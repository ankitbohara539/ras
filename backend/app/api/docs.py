from __future__ import annotations

from typing import Any

from fastapi import FastAPI


API_DESCRIPTION = """
## CivicGrid API

CivicGrid is a community operations API for citizen issue reporting, civic-service
discovery, emergency response, public alerts, persisted notifications, and
role-based municipal administration.

### Authentication

1. Register with `POST /api/v1/auth/register`.
2. Sign in immediately with `POST /api/v1/auth/login`.

Login sets short-lived access and rotating refresh credentials in **HttpOnly
cookies**. Swagger requests made from this page automatically reuse cookies for
the same API host. API clients may alternatively send an access JWT as
`Authorization: Bearer <token>` on protected HTTP endpoints.

The refresh token is intentionally restricted to the authentication path. Use
`POST /api/v1/auth/refresh` to rotate the session and
`POST /api/v1/auth/logout` to revoke it.

### Roles

* **CITIZEN** — report and confirm issues, discover services, and request help.
* **AUTHORITY** — verify and assign issues, manage services, and publish alerts.
* **RESPONDER** — operate the emergency SOS response workflow.
* **ADMIN** — manage users, roles, structural data, and audit records.

Frontend visibility is not an authorization boundary. Every protected operation
is authorized again by the API.

### Errors and request tracing

Application errors use a stable envelope:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation",
    "request_id": "request-uuid"
  }
}
```

The same request identifier is returned in the `X-Request-ID` response header.
Clients may supply their own `X-Request-ID` header for distributed tracing.

### Realtime API

OpenAPI does not describe WebSocket frames. Connect to `/api/v1/ws` with the
access cookie and an allowed `Origin`. Events use the versioned envelope
documented in the project README.
"""


OPENAPI_TAGS = [
    {
        "name": "authentication",
        "description": "Immediate registration, login, rotating sessions, and SMTP password recovery.",
    },
    {
        "name": "users",
        "description": "Current-user profile and accessibility preferences.",
    },
    {
        "name": "issues",
        "description": "Community issue reporting, media, verification, assignment, history, and workflow.",
    },
    {
        "name": "civic services",
        "description": "Civic-service directory management and spatial nearby search.",
    },
    {
        "name": "emergencies",
        "description": "Emergency SOS creation and concurrency-safe responder transitions.",
    },
    {
        "name": "alerts",
        "description": "Active community alerts and authority publishing operations.",
    },
    {
        "name": "notifications",
        "description": "Persisted user notifications, unread counts, and read state.",
    },
    {
        "name": "geocoding",
        "description": "Rate-controlled, Kathmandu-bounded OpenStreetMap/Nominatim search, reverse geocoding, and official ward references.",
    },
    {
        "name": "administration",
        "description": "Admin-only user, role, area, category, and audit-log management.",
    },
    {
        "name": "health",
        "description": "Liveness and MySQL readiness probes for local operation and orchestration.",
    },
    {
        "name": "system",
        "description": "API discovery and service metadata.",
    },
]


def configure_openapi(
    app: FastAPI,
    *,
    api_prefix: str,
    access_cookie_name: str,
    refresh_cookie_name: str,
) -> None:
    """Add security and error semantics that FastAPI cannot infer from Request cookies."""

    default_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = default_openapi()
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes.update(
            {
                "accessCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": access_cookie_name,
                    "description": "HttpOnly access JWT set by the login or refresh endpoint.",
                },
                "refreshCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": refresh_cookie_name,
                    "description": "Opaque rotating refresh token, restricted to authentication endpoints.",
                },
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Alternative access JWT for non-browser API clients.",
                },
            }
        )

        schemas = components.setdefault("schemas", {})
        schemas["ApiError"] = {
            "type": "object",
            "required": ["error"],
            "properties": {
                "error": {
                    "type": "object",
                    "required": ["code", "message", "request_id"],
                    "properties": {
                        "code": {"type": "string", "example": "AUTHENTICATION_REQUIRED"},
                        "message": {"type": "string", "example": "Authentication is required."},
                        "request_id": {"type": "string", "format": "uuid"},
                        "details": {"type": "array", "items": {}},
                    },
                }
            },
        }

        public_paths = {
            "/",
            api_prefix,
            "/health/live",
            "/health/ready",
            f"{api_prefix}/auth/register",
            f"{api_prefix}/auth/login",
            f"{api_prefix}/auth/forgot-password",
            f"{api_prefix}/auth/reset-password",
        }
        refresh_paths = {
            f"{api_prefix}/auth/refresh",
            f"{api_prefix}/auth/logout",
        }
        http_methods = {"get", "post", "put", "patch", "delete", "options", "head"}
        error_schema = {
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}
            }
        }

        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in http_methods or not isinstance(operation, dict):
                    continue

                responses = operation.setdefault("responses", {})
                responses.setdefault(
                    "429",
                    {"description": "Rate limit exceeded.", **error_schema},
                )

                if path in refresh_paths:
                    operation["security"] = [{"refreshCookie": []}]
                    responses.setdefault(
                        "401",
                        {"description": "Refresh session is missing, invalid, expired, or reused.", **error_schema},
                    )
                elif path not in public_paths:
                    operation["security"] = [{"accessCookie": []}, {"bearerAuth": []}]
                    responses.setdefault(
                        "401",
                        {"description": "Authentication is missing, invalid, or expired.", **error_schema},
                    )
                    responses.setdefault(
                        "403",
                        {"description": "The authenticated user does not have the required role.", **error_schema},
                    )

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
