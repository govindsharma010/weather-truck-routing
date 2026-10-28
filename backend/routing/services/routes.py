"""Route alternatives from OSRM (free public demo server, no key).

OSRM's ``alternatives`` option often returns only one or two routes, and the brief asks for three.
When we get fewer, we force extra candidates by routing through a via point pushed sideways from
the middle of the fastest route, then keep only candidates that are genuinely different and sane.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

from . import mock
from .geo import (
    LatLon,
    bearing_deg,
    cumulative_miles,
    destination_point,
    haversine_mi,
    mean_nearest_distance_mi,
    point_at,
)

logger = logging.getLogger(__name__)

WANTED_ROUTES = 3
METERS_PER_MILE = 1609.344
MAX_DETOUR_FACTOR = 1.6  # reject via-routes more than 60% longer than the fastest
MIN_SHAPE_DIFFERENCE_MI = 3.0  # average separation needed to count as a different route


class RoutingError(RuntimeError):
    pass


@dataclass
class RawRoute:
    coords: list[LatLon]
    distance_mi: float
    duration_s: float  # already scaled for trucks


def get_routes(origin: LatLon, dest: LatLon) -> list[RawRoute]:
    """Up to three distinct routes, fastest first."""
    key = f"routes:{settings.PROVIDERS_MODE}:{origin[0]:.4f},{origin[1]:.4f}:{dest[0]:.4f},{dest[1]:.4f}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    if haversine_mi(origin, dest) < 0.5:
        raise RoutingError("Origin and destination are the same place.")

    raw = mock.routes(origin, dest) if settings.PROVIDERS_MODE == "mock" else _osrm_alternatives(origin, dest)
    routes = [_to_route(r) for r in raw]
    routes.sort(key=lambda r: r.duration_s)
    routes = _dedupe(routes)

    if len(routes) < WANTED_ROUTES and settings.PROVIDERS_MODE != "mock":
        routes = _add_via_routes(routes, origin, dest)

    if not routes:
        raise RoutingError("No drivable route was found between those locations.")
    routes.sort(key=lambda r: r.duration_s)
    routes = routes[:WANTED_ROUTES]
    cache.set(key, routes, settings.ROUTE_CACHE_SECONDS)
    return routes


def _to_route(raw: dict) -> RawRoute:
    return RawRoute(
        coords=raw["coords"],
        distance_mi=raw["distance_m"] / METERS_PER_MILE,
        duration_s=raw["duration_s"] * settings.TRUCK_TIME_FACTOR,
    )


def _osrm_route(waypoints: list[LatLon], alternatives: bool) -> list[dict]:
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in waypoints)
    url = f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{coords}"
    params = {
        "alternatives": "3" if alternatives else "false",
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": settings.HTTP_USER_AGENT}, timeout=settings.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise RoutingError(f"Routing service is unreachable: {exc}") from exc

    data = resp.json() if resp.content else {}
    if resp.status_code != 200 or data.get("code") != "Ok":
        code = data.get("code", resp.status_code)
        if code in ("NoRoute", "NoSegment"):
            raise RoutingError("No drivable route was found between those locations.")
        raise RoutingError(f"Routing service error: {data.get('message', code)}")

    return [
        {
            "coords": [(lat, lon) for lon, lat in r["geometry"]["coordinates"]],
            "distance_m": r["distance"],
            "duration_s": r["duration"],
        }
        for r in data["routes"]
    ]


def _osrm_alternatives(origin: LatLon, dest: LatLon) -> list[dict]:
    return _osrm_route([origin, dest], alternatives=True)


def _is_duplicate(a: RawRoute, b: RawRoute) -> bool:
    if abs(a.distance_mi - b.distance_mi) / max(a.distance_mi, 1e-6) > 0.04:
        return False
    return mean_nearest_distance_mi(a.coords, b.coords) < MIN_SHAPE_DIFFERENCE_MI


def _dedupe(routes: list[RawRoute]) -> list[RawRoute]:
    kept: list[RawRoute] = []
    for r in routes:
        if not any(_is_duplicate(r, k) for k in kept):
            kept.append(r)
    return kept


def _add_via_routes(routes: list[RawRoute], origin: LatLon, dest: LatLon) -> list[RawRoute]:
    """Fill up to three routes by detouring through points offset sideways from the fastest route."""
    if not routes:
        try:
            routes = [_to_route(r) for r in _osrm_route([origin, dest], alternatives=False)]
        except RoutingError:
            return routes
    base = routes[0]
    cum = cumulative_miles(base.coords)
    total = cum[-1]
    # Push roughly 12% of the trip length sideways (bounded) so the detour is a real alternative.
    offset_mi = min(max(total * 0.12, 8.0), 70.0)

    for frac in (0.5, 0.35, 0.65):
        for side in (+90, -90):
            if len(routes) >= WANTED_ROUTES:
                return routes
            mid = point_at(base.coords, cum, total * frac)
            ahead = point_at(base.coords, cum, min(total, total * frac + 2))
            via = destination_point(mid, (bearing_deg(mid, ahead) + side) % 360, offset_mi)
            try:
                cand = _to_route(_osrm_route([origin, via, dest], alternatives=False)[0])
            except RoutingError as exc:
                logger.info("via candidate rejected: %s", exc)
                continue
            if cand.distance_mi > base.distance_mi * MAX_DETOUR_FACTOR:
                continue
            if not any(_is_duplicate(cand, k) for k in routes):
                routes.append(cand)
    return routes