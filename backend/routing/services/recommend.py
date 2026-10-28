"""Route ranking.

Order of preference (from the brief):
  1. fewest Severe miles          (No Travel miles count as worse than Severe and are compared first)
  2. fewest High miles
  3. lowest average risk
  4. shortest travel time

Comparison is lexicographic. Mile totals are quantised by the checkpoint spacing, and the softer
metrics are rounded (avg risk to 2 dp, time to the minute) so float noise cannot decide a ranking.
"""
from __future__ import annotations

from dataclasses import dataclass

from .risk import RiskLevel


@dataclass(frozen=True)
class RouteScore:
    miles_by_level: dict[RiskLevel, float]
    avg_risk: float  # mile-weighted mean of the 0-4 level scale
    duration_s: float
    distance_mi: float

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level.get(RiskLevel.NO_TRAVEL, 0.0)

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level.get(RiskLevel.SEVERE, 0.0)

    @property
    def high_miles(self) -> float:
        return self.miles_by_level.get(RiskLevel.HIGH, 0.0)

    def sort_key(self) -> tuple:
        return (
            round(self.no_travel_miles, 1),
            round(self.severe_miles, 1),
            round(self.high_miles, 1),
            round(self.avg_risk, 2),
            round(self.duration_s / 60),
        )


def score_route(segments: list[tuple[RiskLevel, float]], duration_s: float, distance_mi: float) -> RouteScore:
    """``segments`` is a list of (risk level, miles) covering the whole route."""
    miles = {lvl: 0.0 for lvl in RiskLevel}
    for level, length in segments:
        miles[level] += length
    total = sum(miles.values()) or 1.0
    avg = sum(int(level) * m for level, m in miles.items()) / total
    return RouteScore(miles, avg, duration_s, distance_mi)


def rank(scores: list[RouteScore]) -> list[int]:
    """Indices of ``scores`` from best to worst."""
    return sorted(range(len(scores)), key=lambda i: scores[i].sort_key())


def explain(best: RouteScore, others: list[RouteScore]) -> str:
    """One-sentence reason the best route won, naming the first criterion that separated it."""
    if best.no_travel_miles > 0:
        return (
            f"All options cross No Travel conditions; this one has the least ({best.no_travel_miles:.0f} mi). "
            "Consider delaying departure."
        )
    if not others:
        return "Only one route was available."

    def fmt_time(s: float) -> str:
        return f"{int(s // 3600)}h {int(s % 3600 // 60):02d}m"

    runner_up = min(others, key=lambda s: s.sort_key())
    if round(best.severe_miles, 1) < round(runner_up.severe_miles, 1):
        return f"Fewest Severe miles: {best.severe_miles:.0f} vs {runner_up.severe_miles:.0f} on the next best route."
    if round(best.high_miles, 1) < round(runner_up.high_miles, 1):
        return f"Fewest High-risk miles: {best.high_miles:.0f} vs {runner_up.high_miles:.0f} on the next best route."
    if round(best.avg_risk, 2) < round(runner_up.avg_risk, 2):
        return f"Lowest average weather risk ({best.avg_risk:.2f} vs {runner_up.avg_risk:.2f}) with no more Severe or High miles."
    if best.severe_miles == 0 and best.high_miles == 0 and runner_up.severe_miles == 0 and runner_up.high_miles == 0 and best.avg_risk == runner_up.avg_risk:
        return f"Weather is comparable on every route, so the fastest one wins ({fmt_time(best.duration_s)})."
    return f"Equal weather risk to the alternatives, and the shortest travel time ({fmt_time(best.duration_s)})."