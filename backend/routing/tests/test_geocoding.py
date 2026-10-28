from django.core.cache import cache

from routing.services import geocoding


def test_parse_latlon():
    assert geocoding.parse_latlon("41.88, -87.63") == (41.88, -87.63)
    assert geocoding.parse_latlon("41.88,-87.63") == (41.88, -87.63)
    assert geocoding.parse_latlon("99, 0") is None  # latitude out of range
    assert geocoding.parse_latlon("chicago") is None


def test_pasted_coordinates_need_no_network():
    result = geocoding.search("41.88, -87.63")
    assert result[0]["lat"] == 41.88 and result[0]["lon"] == -87.63


def test_short_queries_return_nothing():
    assert geocoding.search("a") == []


def test_mock_search_finds_city(settings):
    settings.PROVIDERS_MODE = "mock"
    cache.clear()
    assert geocoding.search("denv")[0]["label"] == "Denver, Co"