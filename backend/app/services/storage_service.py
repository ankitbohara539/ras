"""Photo upload to Supabase Storage.

Bytes go through FastAPI rather than a browser-direct signed URL, because the
backend needs the bytes anyway to compute the perceptual hash that feeds the
matcher. A direct upload would need a second confirmation round trip to hand
the hash back.
"""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.supabase import get_supabase

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
}

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTOS_PER_TICKET = 4


async def read_and_validate(upload: UploadFile) -> bytes:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported image type {upload.content_type!r}. "
                f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}."
            ),
        )

    payload = await upload.read()
    if len(payload) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Each photo must be 8MB or smaller.",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file is empty.",
        )

    return payload


def upload_photo(
    payload: bytes, ticket_id: uuid.UUID, content_type: str
) -> str:
    """Store the bytes and return the storage path."""
    settings = get_settings()
    extension = ALLOWED_CONTENT_TYPES.get(content_type, ".jpg")
    path = str(PurePosixPath(str(ticket_id)) / f"{uuid.uuid4().hex}{extension}")

    try:
        get_supabase().storage.from_(settings.supabase_photo_bucket).upload(
            path,
            payload,
            {"content-type": content_type, "upsert": "false"},
        )
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
        if "not found" in message.lower() or "bucket" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Storage bucket {settings.supabase_photo_bucket!r} does not "
                    "exist. Create it in Supabase Dashboard -> Storage."
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not upload the photo: {message}",
        ) from exc

    return path


def signed_url(path: str, expires_in: int = 3600) -> str | None:
    """A time-limited URL for a private bucket.

    The bucket is private, so photos are never world-readable by guessing a
    path -- the API hands out short-lived links instead.
    """
    settings = get_settings()
    try:
        result = get_supabase().storage.from_(
            settings.supabase_photo_bucket
        ).create_signed_url(path, expires_in)
    except Exception:
        return None

    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signed_url")
    return None
