"""Geometry helpers: distances along a polyline, sampling, slicing and decimation.

All coordinates are ``(lat, lon)`` tuples in degrees. Distances are statute miles.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from typing import Sequence

EARTH_RADIUS_MI = 3958.7613

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def destination_point(origin: LatLon, bearing: float, distance_mi: float) -> LatLon:
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    brg = math.radians(bearing)
    d = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brg))
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def cumulative_miles(coords: Sequence[LatLon]) -> list[float]:
    """Running distance (miles) at each vertex; first entry is 0."""
    cum = [0.0]
    for prev, cur in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_mi(prev, cur))
    return cum


def point_at(coords: Sequence[LatLon], cum: Sequence[float], mile: float) -> LatLon:
    """Linearly interpolated position ``mile`` miles along the polyline (clamped to its ends)."""
    if mile <= 0:
        return coords[0]
    if mile >= cum[-1]:
        return coords[-1]
    i = bisect_right(cum, mile) - 1
    span = cum[i + 1] - cum[i]
    t = 0.0 if span == 0 else (mile - cum[i]) / span
    return (
        coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t,
        coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t,
    )


def checkpoint_miles(total_miles: float, interval_mi: float) -> list[float]:
    """Mile markers 0, interval, 2*interval ... plus the destination.

    A final marker closer than 20% of the interval to the previous one is merged into the
    destination so we never create a sliver checkpoint.
    """
    if total_miles <= 0:
        return [0.0]
    marks = [0.0]
    m = interval_mi
    while m < total_miles - 1e-9:
        marks.append(m)
        m += interval_mi
    if len(marks) > 1 and total_miles - marks[-1] < 0.2 * interval_mi:
        marks.pop()
    marks.append(total_miles)
    return marks


def segment_bounds(marks: Sequence[float]) -> list[tuple[float, float]]:
    """Stretch of road each checkpoint is responsible for.

    A checkpoint covers the road halfway to its neighbours, so mile totals per risk level add up
    to the full route length and the origin/destination only own half an interval.
    """
    bounds = []
    for i, m in enumerate(marks):
        start = 0.0 if i == 0 else (marks[i - 1] + m) / 2
        end = marks[-1] if i == len(marks) - 1 else (m + marks[i + 1]) / 2
        bounds.append((start, end))
    return bounds


def slice_polyline(coords: Sequence[LatLon], cum: Sequence[float], start: float, end: float) -> list[LatLon]:
    """Sub-polyline between two mile markers (inclusive of interpolated end points)."""
    out = [point_at(coords, cum, start)]
    lo = bisect_right(cum, start)
    hi = bisect_right(cum, end)
    out.extend(coords[lo:hi] if hi > lo else [])
    last = point_at(coords, cum, end)
    if out[-1] != last:
        out.append(last)
    return out


def decimate(coords: Sequence[LatLon], min_spacing_mi: float) -> list[LatLon]:
    """Drop vertices closer than ``min_spacing_mi`` to the previously kept one (keeps both ends)."""
    if len(coords) <= 2:
        return list(coords)
    kept = [coords[0]]
    for pt in coords[1:-1]:
        if haversine_mi(kept[-1], pt) >= min_spacing_mi:
            kept.append(pt)
    kept.append(coords[-1])
    return kept


def mean_nearest_distance_mi(a: Sequence[LatLon], b: Sequence[LatLon], samples: int = 40, dense: int = 800) -> float:
    """Average distance from evenly spaced points on ``a`` to the closest point of ``b``.

    ``b`` is resampled to ``dense`` evenly spaced points first, so the result measures distance to the
    polyline itself rather than to its (possibly sparse) vertices. Cheap shape-similarity measure used
    to reject near-duplicate alternative routes.
    """
    cum_a = cumulative_miles(a)
    cum_b = cumulative_miles(b)
    if cum_a[-1] == 0 or cum_b[-1] == 0:
        return 0.0
    b_pts = [point_at(b, cum_b, cum_b[-1] * k / (dense - 1)) for k in range(dense)]
    dists = []
    for k in range(samples):
        p = point_at(a, cum_a, cum_a[-1] * k / (samples - 1))
        dists.append(min(haversine_mi(p, q) for q in b_pts))
    return sum(dists) / len(dists)