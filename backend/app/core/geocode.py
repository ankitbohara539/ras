"""Coordinates to a human place name, via OpenStreetMap Nominatim.

"27.68412, 85.34571" means nothing to a ward officer; "Tinkune Chowk,
Koteshwor, Kathmandu" tells them which crew to send. Everything here is best
effort: a geocoder that is down or slow must never stop a report from being
filed, so every failure comes back as None and the coordinates stand alone.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class Place:
    # Short and readable: "Tinkune Chowk, Koteshwor, Kathmandu".
    place_name: str
    # Everything Nominatim knows, down to the postcode and country.
    display_name: str
    # OSM tags Nepal's wards as city_district "Kathmandu-07": the real ward,
    # which the seeded ward centroids (a generated grid) cannot tell us.
    ward_area: str | None = None  # "Kathmandu"
    ward_number: int | None = None  # 7
    # "Kathmandu Metropolitan City", "Lalitpur", ...
    city: str | None = None


# Nominatim's usage policy: at most one request a second. Coordinates are
# rounded to 5 decimals (~1m) for the cache key, so a citizen nudging the pin
# back and forth does not hit the service each time.
_cache: dict[tuple[float, float, str], Place] = {}
_CACHE_LIMIT = 4096
_lock = threading.Lock()
_last_request = 0.0


def _first(address: dict, *keys: str) -> str | None:
    for key in keys:
        value = address.get(key)
        if value:
            return str(value)
    return None


_WARD_TAG = re.compile(r"^\s*(.+?)[\s-]+0*(\d{1,2})\s*$")


def _ward(address: dict) -> tuple[str | None, int | None]:
    """ "Kathmandu-07" -> ("Kathmandu", 7). Anything else -> (None, None)."""
    tag = address.get("city_district")
    if not tag:
        return None, None
    match = _WARD_TAG.match(str(tag))
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


def _short_name(payload: dict) -> str | None:
    """Pick the few address parts a person would actually say out loud."""
    address = payload.get("address") or {}

    parts = [
        # A named place beats a street: "Bhatbhateni Supermarket" is findable.
        payload.get("name")
        or _first(address, "amenity", "shop", "building", "tourism", "office"),
        _first(address, "road", "pedestrian", "footway", "path"),
        _first(address, "neighbourhood", "quarter", "hamlet"),
        _first(address, "suburb", "village"),
        # In Nepal OSM tags the ward here: "Kathmandu-32".
        _first(address, "city_district"),
        _first(address, "city", "town", "municipality", "county"),
    ]

    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen) or None


def reverse_geocode(latitude: float, longitude: float, language: str = "en") -> Place | None:
    global _last_request

    key = (round(latitude, 5), round(longitude, 5), language)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()

    with _lock:
        # Another request may have fetched this very point while we waited.
        cached = _cache.get(key)
        if cached is not None:
            return cached

        wait = 1.0 - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()

        try:
            response = httpx.get(
                settings.geocoder_url,
                params={
                    "format": "jsonv2",
                    "lat": f"{latitude:.6f}",
                    "lon": f"{longitude:.6f}",
                    "zoom": 18,
                    "addressdetails": 1,
                    "accept-language": "ne,en" if language == "ne" else "en",
                },
                headers={"User-Agent": settings.geocoder_user_agent},
                timeout=settings.geocoder_timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        if not isinstance(payload, dict) or "error" in payload:
            return None

        display = payload.get("display_name")
        short = _short_name(payload) or display
        if not short:
            return None

        address = payload.get("address") or {}
        ward_area, ward_number = _ward(address)
        place = Place(
            place_name=short[:300],
            display_name=(display or short)[:500],
            ward_area=ward_area,
            ward_number=ward_number,
            city=_first(address, "city", "town", "municipality"),
        )
        if len(_cache) >= _CACHE_LIMIT:
            _cache.clear()
        _cache[key] = place
        return place


@dataclass(frozen=True)
class SearchResult:
    name: str
    display_name: str
    latitude: float
    longitude: float


_search_cache: dict[tuple[str, str], list[SearchResult]] = {}

# Kathmandu Valley, as a preference (not a hard limit) for place search.
_VALLEY_VIEWBOX = "85.18,27.82,85.52,27.56"


def search_places(query: str, language: str = "en", limit: int = 6) -> list[SearchResult]:
    """Find places by name ("Ratna Park", "Bir Hospital"), Nepal only.

    Shares the reverse lookup's one-request-a-second budget and lock.
    """
    global _last_request

    key = (query.strip().lower(), language)
    if key in _search_cache:
        return _search_cache[key]

    settings = get_settings()
    search_url = settings.geocoder_url.rsplit("/", 1)[0] + "/search"

    with _lock:
        if key in _search_cache:
            return _search_cache[key]
        wait = 1.0 - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()

        try:
            response = httpx.get(
                search_url,
                params={
                    "format": "jsonv2",
                    "q": query,
                    "countrycodes": "np",
                    "viewbox": _VALLEY_VIEWBOX,
                    "limit": limit,
                    "accept-language": "ne,en" if language == "ne" else "en",
                },
                headers={"User-Agent": settings.geocoder_user_agent},
                timeout=settings.geocoder_timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        results = [
            SearchResult(
                name=item.get("name") or item.get("display_name", "").split(",")[0],
                display_name=item.get("display_name", ""),
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
            )
            for item in payload
            if isinstance(item, dict) and "lat" in item and "lon" in item
        ]
        if len(_search_cache) > 1000:
            _search_cache.clear()
        _search_cache[key] = results
        return results
