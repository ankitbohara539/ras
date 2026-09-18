import math

from app.core.geo import bounding_box, haversine_m

# Kathmandu Durbar Square and Patan Durbar Square: ~2.6 km apart.
KATHMANDU = (27.7044, 85.3073)
PATAN = (27.6727, 85.3250)


def test_haversine_zero_distance() -> None:
    assert haversine_m(*KATHMANDU, *KATHMANDU) == 0.0


def test_haversine_known_distance() -> None:
    distance = haversine_m(*KATHMANDU, *PATAN)
    assert 3400 < distance < 4200


def test_haversine_is_symmetric() -> None:
    forward = haversine_m(*KATHMANDU, *PATAN)
    backward = haversine_m(*PATAN, *KATHMANDU)
    assert math.isclose(forward, backward)


def test_bounding_box_contains_the_radius() -> None:
    lat, lon = KATHMANDU
    radius = 500.0
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius)

    assert min_lat < lat < max_lat
    assert min_lon < lon < max_lon

    # A point exactly at the radius due north must fall inside the box.
    north_lat = max_lat
    assert haversine_m(lat, lon, north_lat, lon) >= radius - 1


def test_bounding_box_widens_in_longitude_near_the_equator() -> None:
    """Longitude degrees shrink with latitude, so the box must widen."""
    _, _, kathmandu_min_lon, kathmandu_max_lon = bounding_box(27.7, 85.3, 1000)
    _, _, equator_min_lon, equator_max_lon = bounding_box(0.0, 85.3, 1000)

    assert (kathmandu_max_lon - kathmandu_min_lon) > (equator_max_lon - equator_min_lon)
