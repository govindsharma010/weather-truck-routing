from datetime import datetime, timedelta, timezone

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

CHI = {"lat": 41.8781, "lon": -87.6298, "label": "Chicago"}
DEN = {"lat": 39.7392, "lon": -104.9903, "label": "Denver"}


@pytest.fixture(autouse=True)
def mock_mode(settings):
    settings.PROVIDERS_MODE = "mock"
    cache.clear()


def _payload(**over):
    body = {
        "origin": CHI,
        "destination": DEN,
        "departure": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "load_lb": 42_000,
        "checkpoint_interval_mi": 25,
    }
    body.update(over)
    return body


def post(body):
    return APIClient().post("/api/plan/", body, format="json")


def test_plan_returns_three_routes_with_consistent_data():
    resp = post(_payload())
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert len(data["routes"]) == 3
    assert sum(r["recommended"] for r in data["routes"]) == 1
    assert sorted(r["rank"] for r in data["routes"]) == [1, 2, 3]

    for r in data["routes"]:
        cps = r["checkpoints"]
        assert cps[0]["mile"] == 0
        assert cps[-1]["mile"] == pytest.approx(r["distance_mi"], abs=0.1)
        etas = [c["eta"] for c in cps]
        assert etas == sorted(etas)
        # ETA of the destination checkpoint equals the route arrival.
        assert cps[-1]["eta"] == r["arrival"]
        assert sum(r["summary"]["miles_by_level"].values()) == pytest.approx(r["distance_mi"], abs=0.6)
        assert len(r["segments"]) == len(cps)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoint_spacing_options(interval):
    data = post(_payload(checkpoint_interval_mi=interval)).json()
    cps = data["routes"][0]["checkpoints"]
    assert cps[1]["mile"] == interval


def test_heatmap_covers_48_hours_and_matches_checkpoint_risk_scale():
    data = post(_payload()).json()
    hm = data["heatmap"]
    assert hm["hours"] == 48
    assert hm["points"], "heatmap needs points"
    for pt in hm["points"]:
        assert len(pt["level"]) == 49 and all(0 <= v <= 4 for v in pt["level"])


def test_heavier_load_never_lowers_risk():
    light = post(_payload(load_lb=10_000)).json()
    heavy = post(_payload(load_lb=80_000)).json()
    for lr, hr in zip(light["routes"], heavy["routes"]):
        assert hr["summary"]["avg_risk"] >= lr["summary"]["avg_risk"]


def test_validation_errors():
    assert post(_payload(load_lb=0)).status_code == 400
    assert post(_payload(checkpoint_interval_mi=30)).status_code == 400
    assert post(_payload(origin={"lat": 99, "lon": 0})).status_code == 400
    past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert post(_payload(departure=past)).status_code == 400
    far = (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()
    assert post(_payload(departure=far)).status_code == 400


def test_text_places_are_geocoded():
    resp = post(_payload(origin="Chicago", destination="Denver"))
    assert resp.status_code == 200
    assert APIClient().get("/api/geocode/", {"q": "dall"}).json()["results"][0]["label"].startswith("Dallas")


def test_same_origin_and_destination_is_rejected():
    resp = post(_payload(destination=CHI))
    assert resp.status_code == 502 and "same place" in resp.json()["error"]