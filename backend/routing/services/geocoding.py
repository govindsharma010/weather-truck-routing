"""Place search: Photon (typeahead friendly) with a Nominatim fallback. Both are free and key-less."""
from __future__ import annotations

import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

from . import mock

logger = logging.getLogger(__name__)

_LATLON_RE = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


class GeocodingError(RuntimeError):
    pass


def parse_latlon(text: str) -> tuple[float, float] | None:
    """Accept raw "lat, lon" input so drivers can paste coordinates."""
    m = _LATLON_RE.match(text)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def search(query: str, limit: int = 5) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []
    direct = parse_latlon(query)
    if direct:
        return [{"label": f"{direct[0]:.4f}, {direct[1]:.4f}", "lat": direct[0], "lon": direct[1]}]

    key = f"geo:{settings.PROVIDERS_MODE}:{query.lower()}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    if settings.PROVIDERS_MODE == "mock":
        results = mock.geocode(query, limit)
    else:
        try:
            results = _photon(query, limit)
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("photon failed (%s); falling back to nominatim", exc)
            try:
                results = _nominatim(query, limit)
            except (requests.RequestException, ValueError) as exc2:
                raise GeocodingError(f"Location search is unavailable right now: {exc2}") from exc2

    cache.set(key, results, settings.GEOCODE_CACHE_SECONDS)
    return results


def _headers() -> dict:
    return {"User-Agent": settings.HTTP_USER_AGENT, "Accept-Language": "en"}


def _photon(query: str, limit: int) -> list[dict]:
    resp = requests.get(
        settings.PHOTON_URL,
        # Photon has no country filter, so bias to the continental US where the weather thresholds apply.
        params={"q": query, "limit": limit, "lang": "en", "lat": 39.5, "lon": -98.35},
        headers=_headers(),
        timeout=settings.HTTP_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    out = []
    for feat in resp.json()["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        p = feat["properties"]
        parts = [p.get("name"), p.get("city") if p.get("city") != p.get("name") else None, p.get("state"), p.get("country")]
        out.append({"label": ", ".join(x for x in parts if x), "lat": lat, "lon": lon})
    return out


def _nominatim(query: str, limit: int) -> list[dict]:
    resp = requests.get(
        settings.NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": limit},
        headers=_headers(),
        timeout=settings.HTTP_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return [{"label": r["display_name"], "lat": float(r["lat"]), "lon": float(r["lon"])} for r in resp.json()]