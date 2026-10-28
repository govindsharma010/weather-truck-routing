import pytest
from django.core.cache import cache

from routing.services import routes as routing
from routing.services.geo import destination_point


def test_via_routes_fill_up_to_three(monkeypatch, settings):
    settings.PROVIDERS_MODE = "live"
    origin, dest = (41.88, -87.63), (38.63, -90.2)
    base_line = [origin, dest]

    def fake_osrm(waypoints, alternatives):
        if len(waypoints) == 2:  # the direct request only yields one route
            return [{"coords": base_line, "distance_m": 480_000, "duration_s": 17_000}]
        via = waypoints[1]
        return [{"coords": [origin, via, dest], "distance_m": 560_000, "duration_s": 20_000}]

    monkeypatch.setattr(routing, "_osrm_route", fake_osrm)
    cache.clear()
    found = routing.get_routes(origin, dest)
    assert len(found) == 3
    assert found == sorted(found, key=lambda r: r.duration_s)
    assert found[0].duration_s == pytest.approx(17_000 * settings.TRUCK_TIME_FACTOR)


def test_duplicate_alternatives_are_dropped(monkeypatch, settings):
    settings.PROVIDERS_MODE = "live"
    origin, dest = (41.88, -87.63), (38.63, -90.2)
    line = [origin, destination_point(origin, 200, 100), dest]
    dup = {"coords": line, "distance_m": 481_000, "duration_s": 17_100}
    monkeypatch.setattr(routing, "_osrm_alternatives", lambda o, d: [dict(dup), dict(dup)])
    monkeypatch.setattr(routing, "_add_via_routes", lambda r, o, d: r)
    cache.clear()
    assert len(routing.get_routes(origin, dest)) == 1