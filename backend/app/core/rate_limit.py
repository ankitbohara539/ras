from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login": (10, 900),
    "/api/v1/auth/register": (5, 900),
    "/api/v1/auth/forgot-password": (3, 900),
    "/api/v1/geo/reverse": (60, 60),
    "/api/v1/geo/search": (30, 60),
    "/api/v1/emergencies/sos": (5, 600),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        settings = get_settings()
        self._redis = None
        if settings.redis_url:
            from redis.asyncio import from_url

            self._redis = from_url(settings.redis_url, decode_responses=True)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        limit = LIMITS.get(request.url.path)
        if limit:
            allowed, retry_after = await self._allowed(request, *limit)
            if not allowed:
                request_id = getattr(request.state, "request_id", "")
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests. Please try again later.",
                            "request_id": request_id,
                        }
                    },
                )
        return await call_next(request)

    async def _allowed(self, request: Request, maximum: int, window: int) -> tuple[bool, int]:
        identity = request.client.host if request.client else "unknown"
        key = hashlib.sha256(f"{identity}:{request.url.path}".encode()).hexdigest()
        if self._redis:
            redis_key = "rate:" + key
            count = await self._redis.incr(redis_key)
            if count == 1:
                await self._redis.expire(redis_key, window)
            ttl = await self._redis.ttl(redis_key)
            return count <= maximum, max(ttl, 1)
        now = time()
        queue = self._requests[key]
        while queue and queue[0] <= now - window:
            queue.popleft()
        if len(queue) >= maximum:
            return False, max(1, int(window - (now - queue[0])))
        queue.append(now)
        return True, window
