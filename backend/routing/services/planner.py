"""Orchestrates one trip plan: routes -> checkpoints with ETAs -> weather at each ETA -> risk -> ranking.

The weather for every checkpoint is fetched once as an hourly series covering at least the 48 hour
slider window, so the same data answers both "what will it be like when the truck gets here" (read at
the ETA hour) and the heatmap (read at hour 0..48 after departure) without a second round of API calls.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings

from . import recommend, routes as routing, weather
from .geo import (
    LatLon,
    checkpoint_miles,
    cumulative_miles,
    decimate,
    point_at,
    segment_bounds,
    slice_polyline,
)
from .risk import RiskLevel, classify


class PlanError(ValueError):
    """The request cannot be planned (bad input or outside the forecast range)."""


@dataclass(frozen=True)
class PlanRequest:
    origin: LatLon
    destination: LatLon
    departure: datetime  # timezone-aware
    load_lb: float
    interval_mi: int = settings.DEFAULT_CHECKPOINT_INTERVAL
    origin_label: str = ""
    destination_label: str = ""


def build_plan(req: PlanRequest, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    departure = req.departure.astimezone(timezone.utc)
    notes: list[str] = []

    if departure < now - timedelta(hours=24):
        raise PlanError("Departure is more than a day in the past. Pick a current or future time.")
    horizon = now + timedelta(days=settings.MAX_FORECAST_DAYS_AHEAD)
    if departure > horizon:
        raise PlanError(f"Forecasts only reach {settings.MAX_FORECAST_DAYS_AHEAD} days ahead. Pick an earlier departure.")
    if req.interval_mi not in settings.ALLOWED_CHECKPOINT_INTERVALS:
        raise PlanError(f"Checkpoint spacing must be one of {list(settings.ALLOWED_CHECKPOINT_INTERVALS)} miles.")

    candidate_routes = routing.get_routes(req.origin, req.destination)
    if len(candidate_routes) < routing.WANTED_ROUTES:
        notes.append(f"Only {len(candidate_routes)} distinct route(s) exist for this trip.")

    # 1. checkpoints and ETAs for every route
    prepared = [_prepare_route(r, req, departure) for r in candidate_routes]

    # 2. one hourly series per weather grid cell, long enough for the slowest trip and the slider
    start = weather.floor_hour(departure)
    longest_h = max(p["route"].duration_s for p in prepared) / 3600
    wanted_hours = max(settings.HEATMAP_HOURS, math.ceil(longest_h) + 2)
    available_hours = int((horizon - start).total_seconds() // 3600)
    hours = max(1, min(wanted_hours, available_hours))
    all_points = [(cp["lat"], cp["lon"]) for p in prepared for cp in p["checkpoints"]]
    series = weather.fetch_hourly(all_points, start, hours)

    # 3. risk at each checkpoint's ETA
    out_routes = []
    scores = []
    for n, p in enumerate(prepared, start=1):
        route_out, score = _assess_route(n, p, series, req, notes)
        out_routes.append(route_out)
        scores.append(score)

    # 4. recommendation
    order = recommend.rank(scores)
    best = order[0]
    for position, idx in enumerate(order, start=1):
        out_routes[idx]["rank"] = position
        out_routes[idx]["recommended"] = position == 1
    out_routes[best]["explanation"] = recommend.explain(best=scores[best], others=[scores[i] for i in order[1:]])
    fastest = min(range(len(out_routes)), key=lambda i: out_routes[i]["duration_s"])
    out_routes[fastest]["fastest"] = True

    if scores[best].no_travel_miles > 0:
        notes.append("No Travel conditions are forecast on every route at the times you would pass through. Consider a different departure time.")

    return {
        "meta": {
            "origin": {"lat": req.origin[0], "lon": req.origin[1], "label": req.origin_label},
            "destination": {"lat": req.destination[0], "lon": req.destination[1], "label": req.destination_label},
            "departure": departure.isoformat(),
            "load_lb": req.load_lb,
            "checkpoint_interval_mi": req.interval_mi,
            "weather_source": "mock" if settings.PROVIDERS_MODE == "mock" else "Open-Meteo",
            "wind_metric": settings.WIND_METRIC,
            "notes": notes,
        },
        "recommended_route_id": out_routes[best]["id"],
        "routes": out_routes,
        "heatmap": _build_heatmap(prepared, series, req, start, hours),
    }


# ---------------------------------------------------------------------------------------------------
def _prepare_route(route: routing.RawRoute, req: PlanRequest, departure: datetime) -> dict:
    cum = cumulative_miles(route.coords)
    geo_total = cum[-1]
    marks = checkpoint_miles(route.distance_mi, req.interval_mi)
    bounds = segment_bounds(marks)
    scale = geo_total / route.distance_mi if route.distance_mi else 1.0

    checkpoints = []
    for i, (mark, (b0, b1)) in enumerate(zip(marks, bounds)):
        frac = min(1.0, mark / route.distance_mi) if route.distance_mi else 0.0
        lat, lon = point_at(route.coords, cum, mark * scale)
        checkpoints.append(
            {
                "index": i,
                "mile": round(mark, 1),
                "lat": lat,
                "lon": lon,
                "eta": departure + timedelta(seconds=route.duration_s * frac),
                "segment_miles": b1 - b0,
                "geo_from": b0 * scale,
                "geo_to": b1 * scale,
            }
        )
    return {"route": route, "coords": route.coords, "cum": cum, "checkpoints": checkpoints}


def _assess_route(n: int, p: dict, series: dict, req: PlanRequest, notes: list[str]) -> tuple[dict, recommend.RouteScore]:
    route: routing.RawRoute = p["route"]
    segments: list[tuple[RiskLevel, float]] = []
    checkpoints_out = []
    geometry_segments = []
    spacing = max(0.1, route.distance_mi / 2500)  # keep roughly 2,500 vertices per route for the browser
    beyond_forecast = False

    for cp in p["checkpoints"]:
        s = series[weather.grid_key(cp["lat"], cp["lon"])]
        idx = s.index_for(cp["eta"])
        in_range = s.covers(cp["eta"])
        beyond_forecast |= not in_range
        wind, rain, snow = s.wind_mph[idx], s.rain_in_hr[idx], s.snow_in_hr[idx]
        a = classify(wind, rain, snow, req.load_lb)
        segments.append((a.level, cp["segment_miles"]))

        checkpoints_out.append(
            {
                "index": cp["index"],
                "mile": cp["mile"],
                "lat": round(cp["lat"], 5),
                "lon": round(cp["lon"], 5),
                "eta": cp["eta"].isoformat(),
                "level": a.level.key,
                "level_label": a.level.label,
                "level_score": int(a.level),
                "wind_mph": round(wind, 1),
                "rain_in_hr": round(rain, 3),
                "snow_in_hr": round(snow, 3),
                "drivers": a.drivers,
                "load_adjusted": a.load_adjusted,
                "forecast_available": in_range,
            }
        )
        piece = slice_polyline(p["coords"], p["cum"], cp["geo_from"], cp["geo_to"])
        geometry_segments.append(
            {
                "level": a.level.key,
                "from_mile": round(cp["mile"] - cp["segment_miles"] / 2, 1),
                "geometry": [[round(la, 5), round(lo, 5)] for la, lo in decimate(piece, spacing)],
            }
        )

    if beyond_forecast:
        notes.append(f"Route {n}: part of the trip is past the available forecast; the last forecast hour was used.")

    score = recommend.score_route(segments, route.duration_s, route.distance_mi)
    arrival = p["checkpoints"][-1]["eta"]
    lats = [pt[0] for pt in p["coords"]]
    lons = [pt[1] for pt in p["coords"]]
    out = {
        "id": n,
        "label": f"Route {n}",
        "distance_mi": round(route.distance_mi, 1),
        "duration_s": round(route.duration_s),
        "arrival": arrival.isoformat(),
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "summary": {
            "miles_by_level": {lvl.key: round(m, 1) for lvl, m in score.miles_by_level.items()},
            "avg_risk": round(score.avg_risk, 2),
            "max_level": max(c["level_score"] for c in checkpoints_out),
            "max_level_label": RiskLevel(max(c["level_score"] for c in checkpoints_out)).label,
            "checkpoint_count": len(checkpoints_out),
        },
        "segments": geometry_segments,
        "checkpoints": checkpoints_out,
        "rank": None,
        "recommended": False,
        "fastest": False,
        "explanation": "",
    }
    return out, score


def _build_heatmap(prepared: list[dict], series: dict, req: PlanRequest, start: datetime, hours: int) -> dict:
    """Risk per grid cell for each hour after departure (client-side slider reads straight from this)."""
    slider_hours = min(settings.HEATMAP_HOURS, hours)
    cells: dict[tuple[float, float], dict] = {}
    for p in prepared:
        for cp in p["checkpoints"]:
            cell = weather.grid_key(cp["lat"], cp["lon"])
            if cell in cells:
                continue
            s = series[cell]
            levels, winds, rains, snows = [], [], [], []
            for h in range(slider_hours + 1):
                i = min(h, len(s.wind_mph) - 1)
                a = classify(s.wind_mph[i], s.rain_in_hr[i], s.snow_in_hr[i], req.load_lb)
                levels.append(int(a.level))
                winds.append(round(s.wind_mph[i], 1))
                rains.append(round(s.rain_in_hr[i], 2))
                snows.append(round(s.snow_in_hr[i], 2))
            cells[cell] = {"lat": cell[0], "lon": cell[1], "level": levels, "wind": winds, "rain": rains, "snow": snows}
    return {"start": start.isoformat(), "hours": slider_hours, "points": list(cells.values())}