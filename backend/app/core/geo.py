"""Distance helpers.

PostGIS is deliberately not used. Candidate tickets are already narrowed by
ward and a bounding box, so the exact distance is computed over a handful of
rows in Python -- which avoids GeoAlchemy2, geometry types in migrations, and
SRID bookkeeping for no measurable benefit at this scale.
"""

import math

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box(
    lat: float, lon: float, radius_m: float
) -> tuple[float, float, float, float]:
    """Return (min_lat, max_lat, min_lon, max_lon) enclosing the radius.

    Used as a cheap indexed SQL prefilter before exact Haversine distances.
    Slightly over-selects near the poles, which is irrelevant for Nepal.
    """
    d_lat = math.degrees(radius_m / EARTH_RADIUS_M)

    cos_lat = math.cos(math.radians(lat))
    # Guard against division blowing up at the poles.
    cos_lat = max(abs(cos_lat), 1e-6)
    d_lon = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))

    return lat - d_lat, lat + d_lat, lon - d_lon, lon + d_lon
