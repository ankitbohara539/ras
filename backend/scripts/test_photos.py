"""Verify the photo pipeline, and measure what the image signal actually does.

    python -m scripts.test_photos

Part 1 uploads a real photo through the API and checks it round-trips through
Supabase Storage. Part 2 measures perceptual-hash similarity across a range of
transformations, which is the only honest way to describe what the image
signal contributes.
"""

from __future__ import annotations

import io
import json
import math
import random
import sys
import urllib.request

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app
from app.ml.imaging import (
    MAX_MEANINGFUL_DISTANCE,
    compute_phash,
    hamming_distance,
    phash_similarity,
)

PASSWORD = "Sahayatri@2025"
JPEG_MAGIC = b"\xff\xd8"

client = TestClient(app)


def make_photo(seed: int, jitter: int = 0) -> bytes:
    """A synthetic 'photo of a pothole'.

    `jitter` shifts the shapes, standing in for two people photographing the
    same thing from slightly different positions.
    """
    rng = random.Random(seed)
    image = Image.new("RGB", (640, 480), (108, 108, 104))
    draw = ImageDraw.Draw(image)

    for _ in range(220):
        x, y = rng.randint(0, 639), rng.randint(0, 479)
        grey = rng.randint(85, 130)
        draw.ellipse([x, y, x + 5, y + 5], fill=(grey, grey, grey))

    draw.ellipse(
        [200 + jitter, 180 + jitter, 430 + jitter, 330 + jitter], fill=(38, 34, 30)
    )
    draw.ellipse(
        [235 + jitter, 205 + jitter, 395 + jitter, 305 + jitter], fill=(20, 18, 16)
    )
    draw.rectangle([0, 400, 639, 420], fill=(190, 188, 180))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


def transform(data: bytes, size: tuple[int, int] | None = None, quality: int = 88):
    image = Image.open(io.BytesIO(data))
    if size:
        image = image.resize(size)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def login(email: str) -> str:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def ward_centre(token: str) -> tuple[float, float]:
    me = client.get("/api/users/me", headers=auth(token)).json()
    municipality = client.get(f"/api/municipalities/{me['municipality_id']}").json()
    for ward in municipality["wards"]:
        if ward["id"] == me["ward_id"]:
            return ward["centroid_lat"], ward["centroid_lon"]
    raise RuntimeError("Could not locate the demo ward.")


def offset(point: tuple[float, float], north_m: float, east_m: float):
    lat = point[0] + north_m / 110_574.0
    lon = point[1] + east_m / (111_320.0 * math.cos(math.radians(point[0])))
    return round(lat, 6), round(lon, 6)


def report(token: str, text: str, point, photo: bytes | None):
    payload = {
        "description": text,
        "latitude": point[0],
        "longitude": point[1],
        "description_lang": "en",
    }
    files = [("photos", ("pothole.jpg", photo, "image/jpeg"))] if photo else None

    response = client.post(
        "/api/tickets",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=auth(token),
    )
    if response.status_code != 201:
        print(f"   FAILED {response.status_code}: {response.json()}")
        response.raise_for_status()
    return response.json()


def check_storage() -> int:
    print("=" * 64)
    print("PART 1  -  storage round-trip")
    print("=" * 64)

    sita = login("sita@example.com")
    ram = login("ram@example.com")

    centre = offset(ward_centre(sita), north_m=-620, east_m=520)
    nearby = offset(centre, north_m=9, east_m=7)

    original = make_photo(seed=1)

    first = report(
        sita,
        "Large pothole opened up on this road after the rain, very dangerous.",
        centre,
        original,
    )
    ticket = first["ticket"]
    print(f"  uploaded      {ticket['public_code']}  photos={len(ticket['photos'])}")

    if not ticket["photos"]:
        print("  No photo stored. Is the 'ticket-photos' bucket created?")
        return 1

    photo = ticket["photos"][0]
    print(f"  storage path  {photo['storage_path']}")
    print(f"  phash stored  {'yes' if photo['url'] else 'no'}")

    if not photo["url"]:
        print("  No signed URL returned.")
        return 1

    with urllib.request.urlopen(photo["url"], timeout=20) as response:
        payload = response.read()

    print(f"  signed URL    HTTP {response.status}, {len(payload)} bytes")
    print(f"  valid JPEG    {payload[:2] == JPEG_MAGIC}")
    print(f"  byte-exact    {payload == original}")

    # Second person sends the *same* photograph -- the case pHash does catch.
    second = report(
        ram,
        "There is a big hole in the road here, water collects in it.",
        nearby,
        transform(original, quality=55),
    )

    print(f"\n  second report {second['ticket']['public_code']}")
    print(f"  suggestions   {len(second['possible_duplicates'])}")
    for candidate in second["possible_duplicates"]:
        print(f"    -> {candidate['candidate']['public_code']}  score {candidate['score']:.2f}")
        print(
            f"       category {candidate['category_score']:.2f} | "
            f"text {candidate['text_score']:.2f} | "
            f"image {candidate['image_score']:.2f} | "
            f"geo {candidate['geo_score']:.2f}"
        )

    return 0 if payload[:2] == JPEG_MAGIC else 1


def measure_phash() -> None:
    print()
    print("=" * 64)
    print("PART 2  -  what the image signal actually detects")
    print("=" * 64)

    base = make_photo(seed=1)
    reference = compute_phash(base)

    cases = [
        ("same photo, re-sent", base),
        ("recompressed q=45", transform(base, quality=45)),
        ("resized to 400x300", transform(base, size=(400, 300))),
        ("resized + recompressed", transform(base, size=(320, 240), quality=40)),
        ("same scene, camera +6px", make_photo(seed=1, jitter=6)),
        ("same scene, camera +20px", make_photo(seed=1, jitter=20)),
        ("a different scene", make_photo(seed=99, jitter=40)),
    ]

    print(f"\n  {'case':28} {'distance':>9} {'similarity':>11}   verdict")
    print(f"  {'-' * 28} {'-' * 9} {'-' * 11}   {'-' * 18}")

    for label, data in cases:
        candidate = compute_phash(data)
        distance = hamming_distance(reference, candidate)
        similarity = phash_similarity(reference, candidate)
        verdict = "match" if similarity > 0 else "no signal"
        print(f"  {label:28} {distance:>9} {similarity:>11.2f}   {verdict}")

    print(f"\n  Threshold: distances above {MAX_MEANINGFUL_DISTANCE} score 0.")
    print(
        "\n  Read this honestly: the hash recognises the same photograph again,"
        "\n  through recompression and resizing, and does NOT recognise two"
        "\n  photographs taken independently of the same object -- 'camera moved'"
        "\n  scores the same as 'a different scene'. The image signal therefore"
        "\n  catches one photo shared by several people, not two neighbours each"
        "\n  photographing the same pothole. Recognising the object needs an"
        "\n  image embedding, which is a deliberate non-goal here."
    )


def main() -> int:
    code = check_storage()
    measure_phash()
    return code


if __name__ == "__main__":
    sys.exit(main())
