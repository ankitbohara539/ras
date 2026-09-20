"""Hazard geometry and the safer-route planner's decisions.

Routing is faked: `directions` returns a straight line normally and a detour
when asked to avoid something, so the tests pin down what the planner does
with the answers, not what OpenRouteService returns.
"""

from datetime import UTC, datetime

import pytest

from app.core.routing import Route, RoutingError
from app.services import route_service
from app.services.hazard_service import (
    ALL_MODES,
    Hazard,
    distance_to_line_m,
    hazards_on_route,
    is_night,
)

START = (27.7000, 85.3000)
END = (27.7000, 85.3100)  # ~1 km due east
STRAIGHT = [START, (27.7000, 85.3050), END]
# Swings ~330 m north around the middle.
DETOUR = [START, (27.7030, 85.3030), (27.7030, 85.3070), END]


def hazard(id, lat, lon, radius=60, severity="high", modes=ALL_MODES, avoid=True, night_only=False):
    return Hazard(
        id=id,
        source="ticket",
        kind="flooding",
        title=f"Hazard {id}",
        severity=severity,
        latitude=lat,
        longitude=lon,
        radius_m=radius,
        modes=frozenset(modes),
        night_only=night_only,
        active_now=True,
        avoid=avoid,
    )


class TestGeometry:
    def test_point_on_the_line_is_zero_away(self) -> None:
        assert distance_to_line_m(27.7000, 85.3050, STRAIGHT) < 1

    def test_point_beside_the_line(self) -> None:
        # 0.001 deg latitude is ~111 m.
        assert distance_to_line_m(27.7010, 85.3050, STRAIGHT) == pytest.approx(111, abs=3)

    def test_hazards_on_route_uses_radius_plus_slack(self) -> None:
        near = hazard("near", 27.7006, 85.3050, radius=60)  # ~67 m off, within 60+20
        far = hazard("far", 27.7020, 85.3050, radius=60)  # ~222 m off
        assert [h.id for h in hazards_on_route(STRAIGHT, [near, far])] == ["near"]

    def test_night_is_nepal_time(self) -> None:
        # 13:00 UTC is 18:45 in Nepal; 06:00 UTC is 11:45.
        assert is_night(datetime(2026, 9, 19, 13, 0, tzinfo=UTC))
        assert not is_night(datetime(2026, 9, 19, 6, 0, tzinfo=UTC))


@pytest.fixture
def fake_world(monkeypatch):
    world = {"hazards": [], "calls": [], "wheelchair_fails": False}

    def fake_directions(mode, start, end, avoid_rings=None):
        world["calls"].append((mode, bool(avoid_rings)))
        if mode == "wheelchair" and world["wheelchair_fails"]:
            raise RoutingError("Could not find routable point", 2010)
        line = DETOUR if avoid_rings else STRAIGHT
        duration = 900.0 if avoid_rings else 720.0
        return Route(line=line, distance_m=1000.0, duration_s=duration)

    monkeypatch.setattr(route_service, "directions", fake_directions)
    monkeypatch.setattr(route_service, "provider", lambda: world.get("provider", "ors"))
    monkeypatch.setattr(
        route_service, "list_hazards", lambda db, *box, night: list(world["hazards"])
    )
    return world


class TestPlanner:
    def test_recommends_the_detour_around_a_hazard(self, fake_world) -> None:
        fake_world["hazards"] = [hazard("flood", 27.7000, 85.3050)]
        plan = route_service.plan(None, START, END, "walk", night=False)

        assert plan.recommended == "safer"
        assert [h.id for h in plan.fastest.hazards] == ["flood"]
        assert plan.safer is not None and plan.safer.hazards == []
        assert "avoids 1 reported hazard" in plan.notes[0]
        assert "3 min longer" in plan.notes[0]

    def test_clear_route_needs_no_detour(self, fake_world) -> None:
        plan = route_service.plan(None, START, END, "walk", night=False)
        assert plan.recommended == "fastest"
        assert plan.safer is None
        assert plan.notes[0] == "No reported hazards on this route right now."
        assert fake_world["calls"] == [("walk", False)]

    def test_hazard_for_other_modes_is_ignored(self, fake_world) -> None:
        # A wheelchair barrier does not re-route a car.
        fake_world["hazards"] = [hazard("steps", 27.7000, 85.3050, modes={"wheelchair"})]
        plan = route_service.plan(None, START, END, "drive", night=False)
        assert plan.recommended == "fastest" and plan.safer is None

    def test_shown_but_not_avoided(self, fake_world) -> None:
        # A warning-level alert is on the map, but does not force a detour.
        fake_world["hazards"] = [hazard("warning", 27.7000, 85.3050, avoid=False)]
        plan = route_service.plan(None, START, END, "walk", night=False)
        assert plan.safer is None
        assert [h.id for h in plan.fastest.hazards] == ["warning"]

    def test_hazard_at_the_destination_is_flagged_not_avoided(self, fake_world) -> None:
        fake_world["hazards"] = [hazard("at-end", *END, radius=100)]
        plan = route_service.plan(None, START, END, "walk", night=False)
        assert plan.safer is None
        assert any("start or destination" in note for note in plan.notes)

    def test_wheelchair_falls_back_to_walking(self, fake_world) -> None:
        fake_world["wheelchair_fails"] = True
        fake_world["hazards"] = [hazard("barrier", 27.7000, 85.3050, modes={"wheelchair"})]
        plan = route_service.plan(None, START, END, "wheelchair", night=False)

        assert plan.profile_used == "walk"
        assert any("wheelchair route" in note for note in plan.notes)
        # The barrier is still steered around on the walking route.
        assert plan.recommended == "safer"

    def test_broken_streetlight_only_counts_at_night(self, fake_world) -> None:
        dark = hazard("dark", 27.7000, 85.3050, severity="medium", night_only=True)
        fake_world["hazards"] = [dark]
        # list_hazards is what sets active_now; the planner only uses active ones.
        dark.active_now = False
        assert route_service.plan(None, START, END, "walk", night=False).safer is None
        dark.active_now = True
        assert route_service.plan(None, START, END, "walk", night=True).recommended == "safer"

    def test_basic_routing_says_so(self, fake_world) -> None:
        fake_world["provider"] = "osrm"
        fake_world["hazards"] = [hazard("barrier", 27.7000, 85.3050, modes={"wheelchair"})]
        plan = route_service.plan(None, START, END, "wheelchair", night=False)

        assert plan.profile_used == "walk"
        assert any("full routing service" in note for note in plan.notes)
        assert any("Basic routing" in note for note in plan.notes)
