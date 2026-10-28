"""Hourly weather lookup (Open-Meteo, free and key-less) with batching, retries and caching.

One request per ~50 locations returns hourly wind / rain / snow for the whole trip window, so each
checkpoint can be evaluated at its own ETA without extra calls. Locations are snapped to a 0.1 degree
grid (~7 mi, finer than the model's resolution) so overlapping routes share cache entries.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

import requests
from django.conf import settings
from django.core.cache import cache

from . import mock

logger = logging.getLogger(__name__)

GRID_DEGREES = 0.1
BATCH_SIZE = 50
MAX_WORKERS = 4


class WeatherError(RuntimeError):
    pass


@dataclass(frozen=True)
class HourlySeries:
    """Hourly readings starting at ``t0`` (UTC). Rain/snow in inches per hour, wind in mph."""

    t0: datetime
    wind_mph: tuple[float, ...]
    rain_in_hr: tuple[float, ...]
    snow_in_hr: tuple[float, ...]

    def index_for(self, when: datetime) -> int:
        """Index of the hourly reading nearest to ``when``, clamped to the available range."""
        idx = round((when - self.t0).total_seconds() / 3600)
        return max(0, min(len(self.wind_mph) - 1, idx))

    def covers(self, when: datetime) -> bool:
        idx = round((when - self.t0).total_seconds() / 3600)
        return 0 <= idx < len(self.wind_mph)


def grid_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(round(lat / GRID_DEGREES) * GRID_DEGREES, 2), round(round(lon / GRID_DEGREES) * GRID_DEGREES, 2))


def floor_hour(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def fetch_hourly(points: Iterable[tuple[float, float]], start: datetime, hours: int) -> dict[tuple[float, float], HourlySeries]:
    """Hourly series for each distinct grid cell, covering ``hours`` hours from ``start`` (UTC, hour-aligned)."""
    start = floor_hour(start)
    cells = sorted({grid_key(lat, lon) for lat, lon in points})
    result: dict[tuple[float, float], HourlySeries] = {}
    missing: list[tuple[float, float]] = []

    for cell in cells:
        cached = cache.get(_cache_key(cell, start, hours))
        if cached is not None:
            result[cell] = cached
        else:
            missing.append(cell)

    if missing:
        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        if settings.PROVIDERS_MODE == "mock":
            fetched = [mock.hourly_batch(b, start, hours) for b in batches]
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                fetched = list(pool.map(lambda b: _fetch_batch(b, start, hours), batches))
        for batch in fetched:
            for cell, series in batch.items():
                result[cell] = series
                cache.set(_cache_key(cell, start, hours), series, settings.WEATHER_CACHE_SECONDS)
    return result


def _cache_key(cell: tuple[float, float], start: datetime, hours: int) -> str:
    return f"wx:{settings.WIND_METRIC}:{cell[0]:.2f}:{cell[1]:.2f}:{start:%Y%m%d%H}:{hours}"


def _fetch_batch(cells: Sequence[tuple[float, float]], start: datetime, hours: int) -> dict[tuple[float, float], HourlySeries]:
    end = start + timedelta(hours=hours)
    params = {
        "latitude": ",".join(f"{c[0]:.2f}" for c in cells),
        "longitude": ",".join(f"{c[1]:.2f}" for c in cells),
        "hourly": "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "GMT",
        "start_date": f"{start:%Y-%m-%d}",
        "end_date": f"{end:%Y-%m-%d}",
    }
    payload = _get_json(settings.OPEN_METEO_URL, params)
    entries = payload if isinstance(payload, list) else [payload]
    if len(entries) != len(cells):
        raise WeatherError(f"Weather service returned {len(entries)} locations for {len(cells)} requested")
    return {cell: _parse_entry(entry, start, hours) for cell, entry in zip(cells, entries)}


def _parse_entry(entry: dict, start: datetime, hours: int) -> HourlySeries:
    hourly = entry["hourly"]
    times = hourly["time"]
    t0 = datetime.fromisoformat(times[0]).replace(tzinfo=timezone.utc)
    wind_key = "wind_gusts_10m" if settings.WIND_METRIC == "gusts" else "wind_speed_10m"

    def col(name: str) -> list[float]:
        return [float(v) if v is not None else 0.0 for v in hourly[name]]

    wind = col(wind_key)
    rain = [r + s for r, s in zip(col("rain"), col("showers"))]
    snow = col("snowfall")

    offset = max(0, round((start - t0).total_seconds() / 3600))
    sl = slice(offset, offset + hours + 1)
    return HourlySeries(start, tuple(wind[sl]), tuple(rain[sl]), tuple(snow[sl]))


def _get_json(url: str, params: dict, attempts: int = 3):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = requests.get(
                url,
                params=params,
                headers={"User-Agent": settings.HTTP_USER_AGENT},
                timeout=settings.HTTP_TIMEOUT_SECONDS,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise WeatherError(f"Weather service returned HTTP {resp.status_code}")
            if resp.status_code >= 400:
                detail = resp.json().get("reason", resp.text[:200]) if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:200]
                raise WeatherError(f"Weather request rejected: {detail}")
            return resp.json()
        except (requests.RequestException, WeatherError) as exc:
            last = exc
            logger.warning("weather attempt %d/%d failed: %s", attempt + 1, attempts, exc)
            if isinstance(exc, WeatherError) and "rejected" in str(exc):
                break  # 4xx will not get better with a retry
            time.sleep(0.6 * (2**attempt))
    raise WeatherError(f"Could not load weather data: {last}")