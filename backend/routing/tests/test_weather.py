from datetime import datetime, timezone

import pytest
from django.core.cache import cache

from routing.services import weather


def _om_entry(day="2026-10-24", wind=None, rain=None, snow=None):
    times = [f"{day}T{h:02d}:00" for h in range(24)]
    return {
        "hourly": {
            "time": times,
            "wind_speed_10m": wind or [10.0] * 24,
            "wind_gusts_10m": [v * 1.5 for v in (wind or [10.0] * 24)],
            "rain": rain or [0.0] * 24,
            "showers": [0.01] * 24,
            "snowfall": snow or [0.0] * 24,
        }
    }


def test_grid_key_snaps_nearby_points_together():
    assert weather.grid_key(41.88, -87.63) == weather.grid_key(41.9, -87.6) == (41.9, -87.6)


def test_open_meteo_batch_parsing(monkeypatch, settings):
    settings.PROVIDERS_MODE = "live"
    calls = []

    def fake_get_json(url, params, attempts=3):
        calls.append(params)
        n = len(params["latitude"].split(","))
        entry = _om_entry(wind=[float(h) for h in range(24)], rain=[0.2] * 24)
        return [entry for _ in range(n)] if n > 1 else entry

    monkeypatch.setattr(weather, "_get_json", fake_get_json)
    cache.clear()
    start = datetime(2026, 10, 24, 6, 30, tzinfo=timezone.utc)
    out = weather.fetch_hourly([(41.88, -87.63), (41.9, -87.6), (39.74, -104.99)], start, 10)

    assert len(calls) == 1 and calls[0]["precipitation_unit"] == "inch" and calls[0]["wind_speed_unit"] == "mph"
    series = out[weather.grid_key(41.88, -87.63)]
    assert series.t0 == datetime(2026, 10, 24, 6, tzinfo=timezone.utc)  # floored to the hour
    assert series.wind_mph[0] == 6.0 and len(series.wind_mph) == 11  # starts at 06:00 and spans 10h
    assert series.rain_in_hr[0] == pytest.approx(0.21)  # rain + showers
    # ETA lookup rounds to the nearest hour
    assert series.index_for(datetime(2026, 10, 24, 8, 40, tzinfo=timezone.utc)) == 3


def test_single_location_response_shape(monkeypatch, settings):
    settings.PROVIDERS_MODE = "live"
    monkeypatch.setattr(weather, "_get_json", lambda url, params, attempts=3: _om_entry())
    cache.clear()
    out = weather.fetch_hourly([(30.0, -90.0)], datetime(2026, 10, 24, 0, tzinfo=timezone.utc), 5)
    assert len(out) == 1


def test_mock_mode_covers_48_hours(settings):
    settings.PROVIDERS_MODE = "mock"
    cache.clear()
    out = weather.fetch_hourly([(41.9, -87.6)], datetime(2026, 10, 24, 6, tzinfo=timezone.utc), 48)
    series = next(iter(out.values()))
    assert len(series.wind_mph) == 49 and len(series.rain_in_hr) == 49