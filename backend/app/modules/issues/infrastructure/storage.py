import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings


class ObjectStoragePort(ABC):
    @abstractmethod
    async def save(self, content: bytes, extension: str) -> str: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class LocalObjectStorage(ObjectStoragePort):
    def __init__(self, base_path: str) -> None:
        self.base = Path(base_path).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, extension: str) -> str:
        key = str(uuid4()) + extension.lower()
        target = (self.base / key).resolve()
        if self.base not in target.parents:
            raise ValueError("Unsafe storage target")
        await asyncio.to_thread(target.write_bytes, content)
        return key

    async def delete(self, key: str) -> None:
        target = (self.base / key).resolve()
        if self.base in target.parents and target.exists():
            await asyncio.to_thread(target.unlink)


def get_object_storage() -> ObjectStoragePort:
    settings = get_settings()
    if settings.object_storage_provider != "local":
        raise RuntimeError("Configure an S3-compatible storage adapter for this provider.")
    return LocalObjectStorage(settings.object_storage_path)
