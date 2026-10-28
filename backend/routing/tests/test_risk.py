import pytest

from routing.services.risk import RiskLevel as L, classify, classify_rain, classify_snow, classify_wind


@pytest.mark.parametrize(
    "mph,expected",
    [(0, L.LOW), (24.9, L.LOW), (25, L.MODERATE), (34, L.MODERATE), (34.9, L.MODERATE), (35, L.HIGH),
     (44, L.HIGH), (44.9, L.HIGH), (45, L.SEVERE), (54, L.SEVERE), (54.9, L.SEVERE), (55, L.NO_TRAVEL), (80, L.NO_TRAVEL)],
)
def test_wind_bands(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "rate,expected",
    [(0, L.LOW), (0.09, L.LOW), (0.10, L.MODERATE), (0.24, L.MODERATE), (0.25, L.HIGH), (0.49, L.HIGH),
     (0.50, L.SEVERE), (1.00, L.SEVERE), (1.01, L.NO_TRAVEL)],
)
def test_rain_bands(rate, expected):
    assert classify_rain(rate) == expected


@pytest.mark.parametrize(
    "rate,expected",
    [(0, L.LOW), (0.49, L.LOW), (0.5, L.MODERATE), (0.99, L.MODERATE), (1.0, L.HIGH), (1.99, L.HIGH),
     (2.0, L.SEVERE), (3.0, L.SEVERE), (3.01, L.NO_TRAVEL)],
)
def test_snow_bands(rate, expected):
    assert classify_snow(rate) == expected


def test_overall_is_worst_condition():
    a = classify(wind_mph=10, rain_in_hr=0.3, snow_in_hr=2.5, load_lb=10_000)
    assert a.level == L.SEVERE and a.snow_level == L.SEVERE and a.rain_level == L.HIGH


def test_wind_55_is_no_travel_for_any_load():
    assert classify(55, 0, 0, 1_000).level == L.NO_TRAVEL


@pytest.mark.parametrize("load,expected", [(30_000, L.SEVERE), (30_001, L.NO_TRAVEL), (45_000, L.NO_TRAVEL)])
def test_wind_45_to_54_load_rule(load, expected):
    a = classify(50, 0, 0, load)
    assert a.level == expected
    assert a.load_adjusted == (expected == L.NO_TRAVEL)


@pytest.mark.parametrize("load,expected", [(40_000, L.HIGH), (40_001, L.SEVERE)])
def test_wind_35_to_44_load_rule(load, expected):
    a = classify(40, 0, 0, load)
    assert a.level == expected
    assert a.load_adjusted == (expected == L.SEVERE)


def test_load_rule_never_lowers_other_conditions():
    # Heavy rain is already No Travel; a light load on a windy day does not rescue it.
    assert classify(40, 1.5, 0, 10_000).level == L.NO_TRAVEL


def test_drivers_explain_result():
    a = classify(47, 0.3, 0, 35_000)
    assert any("35,000 lb" in d for d in a.drivers)
    assert any("Rain" in d for d in a.drivers)