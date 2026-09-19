import asyncio
from abc import ABC, abstractmethod
from time import monotonic
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError


class GeocodingPort(ABC):
    @abstractmethod
    async def reverse(self, latitude: float, longitude: float, language: str) -> dict[str, Any]: ...

    @abstractmethod
    async def search(self, query: str, limit: int, language: str) -> list[dict[str, Any]]: ...


class NominatimGeocodingAdapter(GeocodingPort):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._cache: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        cache_key = path + repr(sorted(params.items()))
        if cache_key in self._cache:
            return self._cache[cache_key]
        async with self._lock:
            delay = 1.0 - (monotonic() - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        self.settings.nominatim_base_url.rstrip("/") + path,
                        params=params,
                        headers={
                            "User-Agent": self.settings.nominatim_identity,
                            "Accept": "application/json",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    self._last_request = monotonic()
            except (httpx.HTTPError, ValueError) as exc:
                raise AppError(
                    "GEO_SERVICE_UNAVAILABLE",
                    "Address lookup is temporarily unavailable. Coordinates can still be used.",
                    503,
                ) from exc
        if len(self._cache) >= 500:
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = data
        return data

    @staticmethod
    def _result(item: dict[str, Any], latitude: float, longitude: float) -> dict[str, Any]:
        address = item.get("address") or {}
        ward = address.get("ward") or address.get("city_district")
        return {
            "display_name": item.get("display_name", ""),
            "latitude": float(item.get("lat", latitude)),
            "longitude": float(item.get("lon", longitude)),
            "ward": ward,
            "address": address,
            "osm_type": item.get("osm_type"),
            "osm_id": item.get("osm_id"),
            "boundingbox": item.get("boundingbox"),
            "source": "OpenStreetMap / Nominatim",
        }

    async def reverse(self, latitude: float, longitude: float, language: str = "en") -> dict[str, Any]:
        params: dict[str, Any] = {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
            "accept-language": language,
            "zoom": 18,
        }
        if self.settings.nominatim_contact:
            params["email"] = self.settings.nominatim_contact
        data = await self._get(
            "/reverse",
            params,
        )
        return self._result(data, latitude, longitude)

    async def search(self, query: str, limit: int, language: str = "en") -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "namedetails": 1,
            "limit": limit,
            "countrycodes": self.settings.geocoding_country_codes,
            "viewbox": self.settings.geocoding_viewbox,
            "bounded": int(self.settings.geocoding_bounded),
            "accept-language": language,
            "dedupe": 1,
        }
        if self.settings.nominatim_contact:
            params["email"] = self.settings.nominatim_contact
        data = await self._get(
            "/search",
            params,
        )
        return [
            self._result(item, float(item["lat"]), float(item["lon"]))
            for item in data
        ]


geocoder: GeocodingPort = NominatimGeocodingAdapter()
