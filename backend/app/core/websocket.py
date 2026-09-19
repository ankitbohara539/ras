import asyncio
from contextlib import suppress

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.core.events import event_bus, event_envelope
from app.core.security import decode_access_token
from app.modules.auth.application.service import user_roles
from app.shared.infrastructure.models import RefreshSession, User, UserStatus

router = APIRouter()


@router.websocket("/ws")
async def websocket_gateway(websocket: WebSocket) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")
    if origin is None or origin.rstrip("/") not in settings.allowed_origins:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Origin not allowed")
        return
    token = websocket.cookies.get(settings.access_cookie_name)
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return
    try:
        payload = decode_access_token(token)
        async with AsyncSessionFactory() as db:
            session = await db.scalar(
                select(RefreshSession).where(
                    RefreshSession.id == payload["sid"], RefreshSession.revoked_at.is_(None)
                )
            )
            user = await db.get(User, payload["sub"])
            if session is None or user is None or user.status != UserStatus.ACTIVE:
                raise ValueError("inactive session")
            roles = await user_roles(db, user.id)
    except (jwt.PyJWTError, KeyError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid session")
        return
    await websocket.accept()
    channels = [f"user:{user.id}", *[f"role:{role.value}" for role in roles]]
    subscriptions = [(channel, await event_bus.subscribe(channel)) for channel in channels]

    async def sender() -> None:
        while True:
            tasks = [asyncio.create_task(queue.get()) for _, queue in subscriptions]
            done, pending = await asyncio.wait(tasks, timeout=25, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            if not done:
                await websocket.send_json(event_envelope({"type": "system.ping"}))
                continue
            await websocket.send_json(next(iter(done)).result())

    async def receiver() -> None:
        while True:
            await websocket.receive_text()

    send_task = asyncio.create_task(sender())
    receive_task = asyncio.create_task(receiver())
    try:
        _, pending = await asyncio.wait(
            [send_task, receive_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        receive_task.cancel()
        for channel, queue in subscriptions:
            with suppress(Exception):
                await event_bus.unsubscribe(channel, queue)
