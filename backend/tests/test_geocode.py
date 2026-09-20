"""OSM's ward tag is what routes a report to the right ward office, so its
parsing and the municipality-name match are worth pinning down."""

import pytest

from app.core.geocode import _short_name, _ward
from app.services.ticket_service import _name_key


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("Kathmandu-07", ("Kathmandu", 7)),
        ("Kathmandu-32", ("Kathmandu", 32)),
        ("Lalitpur-12", ("Lalitpur", 12)),
        ("Budhanilkantha-02", ("Budhanilkantha", 2)),
        ("Kathmandu 5", ("Kathmandu", 5)),
        ("Old Baneshwor", (None, None)),
        (None, (None, None)),
    ],
)
def test_ward_tag(tag, expected) -> None:
    address = {} if tag is None else {"city_district": tag}
    assert _ward(address) == expected


def test_municipality_names_match_osm() -> None:
    assert _name_key("Kathmandu Metropolitan City") == _name_key("Kathmandu")
    assert _name_key("Lalitpur Metropolitan City") == _name_key("Lalitpur")
    assert _name_key("Budhanilkantha Municipality") == _name_key("Budhanilkantha")
    assert _name_key("Kathmandu") != _name_key("Kirtipur")
    assert _name_key(None) == ""


def test_short_name_keeps_the_useful_parts() -> None:
    payload = {
        "name": "",
        "address": {
            "road": "Dashrath Marg",
            "neighbourhood": "Tripureshwar",
            "city_district": "Kathmandu-11",
            "city": "Kathmandu Metropolitan City",
            "county": "Kathmandu",
            "country": "Nepal",
        },
    }
    assert _short_name(payload) == (
        "Dashrath Marg, Tripureshwar, Kathmandu-11, Kathmandu Metropolitan City"
    )
