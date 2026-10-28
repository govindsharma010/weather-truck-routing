"""Deterministic offline stand-ins for the geocoder, router and weather API (PROVIDERS_MODE=mock).

They exist so the whole app can be demoed and tested without network access. The weather is a pair
of moving storm cells over the central US plus a little background noise, so routes genuinely differ
in risk and the heatmap slider has something to animate.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .geo import LatLon, bearing_deg, destination_point, haversine_mi

CITIES = {
    "chicago, il": (41.8781, -87.6298),
    "st. louis, mo": (38.6270, -90.1994),
    "denver, co": (39.7392, -104.9903),
    "dallas, tx": (32.7767, -96.7970),
    "kansas city, mo": (39.0997, -94.5786),
    "omaha, ne": (41.2565, -95.9345),
    "minneapolis, mn": (44.9778, -93.2650),
    "indianapolis, in": (39.7684, -86.1581),
    "nashville, tn": (36.1627, -86.7816),
    "oklahoma city, ok": (35.4676, -97.5164),
    "salt lake city, ut": (40.7608, -111.8910),
    "seattle, wa": (47.6062, -122.3321),
    "los angeles, ca": (34.0522, -118.2437),
    "atlanta, ga": (33.7490, -84.3880),
    "houston, tx": (29.7604, -95.3698),
}


def geocode(query: str, limit: int = 5) -> list[dict]:
    q = query.strip().lower()
    hits = [(name, ll) for name, ll in CITIES.items() if q and q in name]
    return [{"label": name.title(), "lat": ll[0], "lon": ll[1]} for name, ll in hits[:limit]]


def routes(origin: LatLon, dest: LatLon) -> list[dict]:
    """Three plausible alternatives: direct, northern bow, southern bow (bowed great-circle paths)."""
    direct = haversine_mi(origin, dest)
    brg = bearing_deg(origin, dest)
    out = []
    for name, bow, circuity in (("direct", 0.0, 1.15), ("north", 0.09, 1.2), ("south", -0.11, 1.22)):
        pts = []
        n = max(12, int(direct / 8))
        for i in range(n + 1):
            f = i / n
            base = destination_point(origin, brg, direct * f)
            lateral = bow * direct * math.sin(math.pi * f)
            pts.append(destination_point(base, brg - 90, lateral))
        pts[0], pts[-1] = origin, dest
        # A road is longer than the crow-flies line; scale distance via duration only (geometry stays as drawn).
        dist_m = direct * circuity * 1609.344 * (1 + abs(bow))
        out.append({"coords": pts, "distance_m": dist_m, "duration_s": dist_m / 29.0})  # ~65 mph
    return out


def _storm(lat: float, lon: float, t_hours: float, cx: float, cy: float, vx: float, vy: float, radius: float) -> float:
    """Gaussian storm intensity (0..1) for a cell centred at (cx, cy) drifting by (vx, vy) deg/h."""
    dx = lon - (cx + vx * t_hours)
    dy = lat - (cy + vy * t_hours)
    return math.exp(-(dx * dx + dy * dy) / (2 * radius * radius))


def hourly_batch(cells, start: datetime, hours: int):
    from .weather import HourlySeries  # local import: weather imports this module

    out = {}
    for lat, lon in cells:
        wind, rain, snow = [], [], []
        for h in range(hours + 1):
            t = (start + timedelta(hours=h) - datetime(2026, 1, 1, tzinfo=timezone.utc)).total_seconds() / 3600
            s1 = _storm(lat, lon, h, -99.0, 38.5, 0.18, 0.02, 2.6)  # fast moving front, central plains
            s2 = _storm(lat, lon, h, -86.0, 43.5, -0.08, -0.05, 2.2)  # slower lake-effect cell
            noise = 0.5 + 0.5 * math.sin(lat * 3.1 + lon * 1.7 + t / 5.0)
            wind.append(6 + 12 * noise + 46 * s1 + 22 * s2)
            rain.append(max(0.0, 1.15 * s1 - 0.12 + 0.03 * noise) if lat < 42.5 else 0.0)
            snow.append(max(0.0, 3.4 * s2 - 0.35) if lat >= 42.5 else 0.0)
        out[(lat, lon)] = HourlySeries(
            start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start,
            tuple(round(w, 1) for w in wind),
            tuple(round(r, 3) for r in rain),
            tuple(round(s, 3) for s in snow),
        )
    return out