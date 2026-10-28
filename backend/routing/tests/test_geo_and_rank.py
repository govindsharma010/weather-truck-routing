import pytest

from routing.services import geo, recommend
from routing.services.risk import RiskLevel as L


def test_checkpoint_miles_basic():
    assert geo.checkpoint_miles(100, 25) == [0, 25, 50, 75, 100]


def test_checkpoint_miles_merges_sliver_before_destination():
    # 103 mi: a checkpoint at 100 would leave a 3 mi sliver, so it is merged into the destination.
    assert geo.checkpoint_miles(103, 25) == [0, 25, 50, 75, 103]


def test_checkpoint_miles_short_trip():
    assert geo.checkpoint_miles(8, 25) == [0, 8]


def test_segment_bounds_cover_whole_route_without_gaps():
    marks = geo.checkpoint_miles(137, 25)
    bounds = geo.segment_bounds(marks)
    assert bounds[0][0] == 0 and bounds[-1][1] == 137
    assert all(a[1] == b[0] for a, b in zip(bounds, bounds[1:]))
    assert sum(e - s for s, e in bounds) == pytest.approx(137)


def test_point_at_interpolates_and_clamps():
    coords = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    cum = geo.cumulative_miles(coords)
    mid = geo.point_at(coords, cum, cum[-1] / 2)
    assert mid[1] == pytest.approx(1.0, abs=1e-6)
    assert geo.point_at(coords, cum, -5) == coords[0]
    assert geo.point_at(coords, cum, 1e9) == coords[-1]


def test_slice_polyline_endpoints():
    coords = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    cum = geo.cumulative_miles(coords)
    piece = geo.slice_polyline(coords, cum, cum[-1] * 0.25, cum[-1] * 0.75)
    assert piece[0][1] == pytest.approx(0.5, abs=1e-6)
    assert piece[-1][1] == pytest.approx(1.5, abs=1e-6)
    assert (0.0, 1.0) in piece


def _score(segments, duration=3600):
    return recommend.score_route(segments, duration, sum(m for _, m in segments))


def test_severe_miles_beat_everything_else():
    fast_but_severe = _score([(L.SEVERE, 10), (L.LOW, 90)], duration=3000)
    slow_but_calm = _score([(L.MODERATE, 100)], duration=9000)
    assert recommend.rank([fast_but_severe, slow_but_calm]) == [1, 0]


def test_high_miles_break_severe_ties():
    a = _score([(L.HIGH, 30), (L.LOW, 70)])
    b = _score([(L.HIGH, 10), (L.LOW, 90)])
    assert recommend.rank([a, b]) == [1, 0]


def test_avg_risk_then_time():
    a = _score([(L.MODERATE, 50), (L.LOW, 50)], duration=4000)
    b = _score([(L.LOW, 100)], duration=5000)
    assert recommend.rank([a, b]) == [1, 0]  # lower average risk wins despite being slower
    c = _score([(L.LOW, 100)], duration=4000)
    assert recommend.rank([b, c]) == [1, 0]  # identical risk: faster wins


def test_no_travel_is_worse_than_severe():
    blocked = _score([(L.NO_TRAVEL, 5), (L.LOW, 95)])
    severe = _score([(L.SEVERE, 60), (L.LOW, 40)])
    assert recommend.rank([blocked, severe]) == [1, 0]


def test_avg_risk_is_mile_weighted():
    s = _score([(L.HIGH, 25), (L.LOW, 75)])
    assert s.avg_risk == pytest.approx(0.5)