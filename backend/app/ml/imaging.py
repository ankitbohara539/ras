"""Image similarity via perceptual hashing.

What this actually detects, measured (see scripts/test_photos.py):

    same photo, re-sent            distance  0   similarity 1.00
    recompressed to q=45           distance  0   similarity 1.00
    resized to 400x300             distance  0   similarity 1.00
    same scene, camera moved       distance 26   similarity 0.00
    a completely different scene   distance 28   similarity 0.00

So pHash reliably recognises *the same photograph* again -- re-sent,
re-compressed, resized, mildly cropped -- and does not recognise two
photographs taken independently of the same object. On that second case it
scores no better than chance.

That still catches a real pattern: one photo circulating in a ward WhatsApp
group and being attached by several people. It does not catch two neighbours
each photographing the same pothole. Recognising the object rather than the
file needs an image embedding (CLIP or similar, ~1.5GB of torch), which is a
deliberate non-goal here.

This is why image similarity is only 20% of the blend, and why the weights
renormalise when photos are absent: the signal must never be load-bearing.
"""

from __future__ import annotations

import io

import imagehash
from PIL import Image, UnidentifiedImageError

# A 64-bit pHash: two identical images differ by 0, unrelated ones by ~32.
HASH_BITS = 64
# Beyond this Hamming distance, treat the images as unrelated rather than
# letting a weak signal drift the blended score upward.
MAX_MEANINGFUL_DISTANCE = 22


def compute_phash(image_bytes: bytes) -> str | None:
    """Return the perceptual hash as hex, or None if the bytes are not an image."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return str(imagehash.phash(image.convert("RGB")))
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def image_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.size
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def hamming_distance(hash_a: str, hash_b: str) -> int | None:
    """Bit distance between two hashes.

    The int() is load-bearing: imagehash subtraction yields a numpy integer,
    which propagates into the blended score as np.float64. psycopg2 has no
    adapter for that and renders it literally as "np.float64(1.0)", producing
    invalid SQL. Coerce at the boundary rather than downstream.
    """
    try:
        return int(imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b))
    except (ValueError, TypeError):
        return None


def phash_similarity(hash_a: str | None, hash_b: str | None) -> float:
    """Similarity in [0, 1]. Returns 0.0 when either side has no photo.

    Zero rather than None so a missing photo never inflates the blend -- a
    report without a picture should not score as if its picture matched.
    """
    if not hash_a or not hash_b:
        return 0.0

    distance = hamming_distance(hash_a, hash_b)
    if distance is None or distance > MAX_MEANINGFUL_DISTANCE:
        return 0.0

    return float(1.0 - (distance / MAX_MEANINGFUL_DISTANCE))


def best_phash_similarity(
    hashes_a: list[str | None], hashes_b: list[str | None]
) -> float:
    """Best pairwise match between two photo sets.

    Reports carry several photos; one matching pair is enough evidence.
    """
    best = 0.0
    for a in hashes_a:
        for b in hashes_b:
            best = max(best, phash_similarity(a, b))
            if best >= 1.0:
                return 1.0
    return float(best)
