"""Weather risk classification.

Thresholds come straight from the assessment brief. Each band's lower bound is inclusive and the
band above starts where it ends, so fractional readings (e.g. 34.6 mph) never fall into a gap:

    Wind (mph)      Low <25 | Moderate 25-<35 | High 35-<45 | Severe 45-<55 | No Travel >=55
    Rain (in/hr)    Low <0.10 | Moderate 0.10-<0.25 | High 0.25-<0.50 | Severe 0.50-1.00 | No Travel >1.00
    Snow (in/hr)    Low <0.5 | Moderate 0.5-<1.0 | High 1.0-<2.0 | Severe 2.0-3.0 | No Travel >3.0

The brief states the upper edge of Severe for rain and snow as inclusive (1.00 and 3.0 are Severe,
only values above them are No Travel), so those two edges are inclusive.

Load rules then tighten the *wind* result for heavy trucks:
    wind >= 55 mph                  -> No Travel (any load)
    45 <= wind < 55 and load > 30k  -> No Travel
    35 <= wind < 45 and load > 40k  -> at least Severe
The overall level of a checkpoint is the worst of the three conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return {0: "Low", 1: "Moderate", 2: "High", 3: "Severe", 4: "No Travel"}[int(self)]

    @property
    def key(self) -> str:
        return self.name.lower()


# (upper bound, level); a value is in the first band whose bound it is strictly below.
_WIND_BANDS = [(25, RiskLevel.LOW), (35, RiskLevel.MODERATE), (45, RiskLevel.HIGH), (55, RiskLevel.SEVERE)]
# Rain/snow: Severe includes its upper edge, so it is handled separately after these bands.
_RAIN_BANDS = [(0.10, RiskLevel.LOW), (0.25, RiskLevel.MODERATE), (0.50, RiskLevel.HIGH)]
_RAIN_SEVERE_MAX = 1.00
_SNOW_BANDS = [(0.5, RiskLevel.LOW), (1.0, RiskLevel.MODERATE), (2.0, RiskLevel.HIGH)]
_SNOW_SEVERE_MAX = 3.0

LOAD_NO_TRAVEL_WIND_45_LB = 30_000
LOAD_SEVERE_WIND_35_LB = 40_000


def _band(value: float, bands: list[tuple[float, RiskLevel]]) -> RiskLevel | None:
    for upper, level in bands:
        if value < upper:
            return level
    return None


def classify_wind(mph: float) -> RiskLevel:
    level = _band(mph, _WIND_BANDS)  # note: LOW == 0 is falsy, so never use `or` here
    return RiskLevel.NO_TRAVEL if level is None else level


def classify_rain(in_per_hr: float) -> RiskLevel:
    level = _band(in_per_hr, _RAIN_BANDS)
    if level is not None:
        return level
    return RiskLevel.SEVERE if in_per_hr <= _RAIN_SEVERE_MAX else RiskLevel.NO_TRAVEL


def classify_snow(in_per_hr: float) -> RiskLevel:
    level = _band(in_per_hr, _SNOW_BANDS)
    if level is not None:
        return level
    return RiskLevel.SEVERE if in_per_hr <= _SNOW_SEVERE_MAX else RiskLevel.NO_TRAVEL


@dataclass(frozen=True)
class Assessment:
    level: RiskLevel
    wind_level: RiskLevel
    rain_level: RiskLevel
    snow_level: RiskLevel
    drivers: list[str] = field(default_factory=list)  # human-readable reasons
    load_adjusted: bool = False  # True when a load rule changed the wind result


def classify(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> Assessment:
    """Overall risk for one checkpoint reading, including the load-based wind rules."""
    wind_level = classify_wind(wind_mph)
    drivers: list[str] = []
    load_adjusted = False

    if wind_mph >= 55:
        wind_level = RiskLevel.NO_TRAVEL
    elif 45 <= wind_mph < 55 and load_lb > LOAD_NO_TRAVEL_WIND_45_LB:
        wind_level = RiskLevel.NO_TRAVEL
        load_adjusted = True
        drivers.append(f"Wind {wind_mph:.0f} mph with a {load_lb:,.0f} lb load (over 30,000 lb) is No Travel")
    elif 35 <= wind_mph < 45 and load_lb > LOAD_SEVERE_WIND_35_LB:
        wind_level = max(wind_level, RiskLevel.SEVERE)
        load_adjusted = True
        drivers.append(f"Wind {wind_mph:.0f} mph with a {load_lb:,.0f} lb load (over 40,000 lb) is raised to Severe")

    rain_level = classify_rain(rain_in_hr)
    snow_level = classify_snow(snow_in_hr)

    if wind_level >= RiskLevel.MODERATE and not load_adjusted:
        drivers.append(f"Wind {wind_mph:.0f} mph: {wind_level.label}")
    if rain_level >= RiskLevel.MODERATE:
        drivers.append(f"Rain {rain_in_hr:.2f} in/hr: {rain_level.label}")
    if snow_level >= RiskLevel.MODERATE:
        drivers.append(f"Snow {snow_in_hr:.2f} in/hr: {snow_level.label}")

    overall = max(wind_level, rain_level, snow_level)
    return Assessment(overall, wind_level, rain_level, snow_level, drivers, load_adjusted)