from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.config import get_settings


def event_envelope(event: dict[str, Any]) -> dict[str, Any]:
    """Create the stable, versioned wire format used by every realtime adapter."""
    if "event" in event and "version" in event:
        return event
    return {
        "event": event.get("type", "notification.created"),
        "version": 1,
        "id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "data": event.get("data", {}),
    }


class EventBus(ABC):
    @abstractmethod
    async def publish(self, channel: str, event: dict[str, Any]) -> None: ...

    @abstractmethod
    async def subscribe(self, channel: str) -> asyncio.Queue[dict[str, Any]]: ...

    @abstractmethod
    async def unsubscribe(self, channel: str, queue: asyncio.Queue[dict[str, Any]]) -> None: ...


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._channels: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        payload = event_envelope(event)
        async with self._lock:
            targets = list(self._channels[channel])
        for target in targets:
            await target.put(payload)

    async def subscribe(self, channel: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._channels[channel].add(queue)
        return queue

    async def unsubscribe(self, channel: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._channels[channel].discard(queue)


class RedisEventBus(EventBus):
    def __init__(self, url: str) -> None:
        from redis.asyncio import from_url

        self._redis = from_url(url, decode_responses=True)
        self._pubsubs: dict[int, tuple[Any, asyncio.Task[None]]] = {}

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        await self._redis.publish(channel, json.dumps(event_envelope(event)))

    async def subscribe(self, channel: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)

        async def pump() -> None:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await queue.put(json.loads(message["data"]))

        task = asyncio.create_task(pump())
        self._pubsubs[id(queue)] = (pubsub, task)
        return queue

    async def unsubscribe(self, channel: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        record = self._pubsubs.pop(id(queue), None)
        if record:
            pubsub, task = record
            task.cancel()
            await pubsub.unsubscribe(channel)
            await pubsub.close()


settings = get_settings()
event_bus: EventBus = RedisEventBus(settings.redis_url) if settings.redis_url else InMemoryEventBus()
