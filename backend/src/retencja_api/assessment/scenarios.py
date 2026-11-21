"""What-if scenarios: how the crop's water supply develops over the next weeks.

The root-zone model is run forward from today's modelled soil water, replaying the
weather of the same calendar days from each of the past years (analog years). The driest,
a typical and a wet year are reported, plus a rainless run and two runs that show what
irrigation now or more organic matter in the soil would change in a dry spell.
"""

from datetime import date, timedelta

import numpy as np

from retencja_api.assessment.crop_params import CropParams
from retencja_api.assessment.water_balance import STRONG_STRESS_KS, run_root_zone, same_date
from retencja_api.meteo.openmeteo import DailyWeather
from retencja_api.models import Scenario, Scenarios

SCENARIO_DAYS = 30
MIN_HUMUS_GAIN_MM = 5.0  # below this the "more humus" run barely differs from "dry"


def _analogs(
    weather: DailyWeather, day: date, years: int
) -> list[tuple[int, np.ndarray, np.ndarray]]:
    """(year, precipitation, ET0) of the SCENARIO_DAYS after the same date in past years."""
    out = []
    for year in range(day.year - years, day.year):
        i0 = weather.index(same_date(day, year)) + 1
        i1 = i0 + SCENARIO_DAYS
        if i0 < 0 or i1 > len(weather.days):
            continue
        p, e = weather.precipitation[i0:i1], weather.et0[i0:i1]
        if np.isfinite(p).all() and np.isfinite(e).all():
            out.append((year, p, e))
    return out


def _run(
    key: str,
    label: str,
    year: int | None,
    days: list[date],
    precipitation: np.ndarray,
    et0: np.ndarray,
    crop: CropParams,
    taw_mm: float,
    start_depletion_mm: float,
) -> Scenario:
    depletion, ks = run_root_zone(days, precipitation, et0, crop, taw_mm, start_depletion_mm)
    stressed = [d for d, k in zip(days, ks, strict=True)
                if k < STRONG_STRESS_KS and crop.in_season(d)]
    return Scenario(
        key=key,
        label=label,
        analog_year=year,
        rain_mm=round(float(precipitation.sum()), 1),
        et0_mm=round(float(et0.sum()), 1),
        first_stress_day=stressed[0] if stressed else None,
        stress_days=len(stressed),
        available_pct_end=round(100 * (1 - depletion[-1] / taw_mm), 1),
        refill_mm=round(float(depletion[-1]), 1),
    )


def build_scenarios(
    weather: DailyWeather,
    crop: CropParams,
    taw_mm: float,
    depletion_mm: float,
    day: date,
    years: int,
    humus_gain_mm: float,
) -> Scenarios | None:
    """None when the crop is out of season for the whole horizon or history is missing."""
    days = [day + timedelta(days=k) for k in range(1, SCENARIO_DAYS + 1)]
    if not any(crop.in_season(d) for d in days):
        return None
    analogs = sorted(_analogs(weather, day, years), key=lambda a: float(a[1].sum()))
    if len(analogs) < 3:
        return None
    n = len(analogs)
    # The second-driest of ten years is roughly a dry spell that comes every five years.
    dry = analogs[1 if n >= 5 else 0]
    typical = analogs[n // 2]
    wet = analogs[-2 if n >= 5 else -1]

    def run(key, label, analog, precipitation=None, taw=taw_mm, start=depletion_mm):
        year, p, e = analog
        return _run(key, label, year, days, p if precipitation is None else precipitation,
                    e, crop, taw, start)

    median_et0 = np.median(np.stack([a[2] for a in analogs]), axis=0)
    items = [
        _run("no_rain", f"Bez deszczu przez {SCENARIO_DAYS} dni", None, days,
             np.zeros(SCENARIO_DAYS), median_et0, crop, taw_mm, depletion_mm),
        run("dry", f"Sucho, jak w {dry[0]} r.", dry),
        run("typical", f"Typowo, jak w {typical[0]} r.", typical),
        run("wet", f"Mokro, jak w {wet[0]} r.", wet),
        run("irrigated", f"Nawadniasz teraz, potem sucho jak w {dry[0]} r.", dry, start=0.0),
    ]
    if humus_gain_mm >= MIN_HUMUS_GAIN_MM:
        items.append(run("more_humus", f"+1 % próchnicy, sucho jak w {dry[0]} r.", dry,
                         taw=taw_mm + humus_gain_mm))
    return Scenarios(
        start=days[0], end=days[-1], humus_gain_mm=round(humus_gain_mm, 1), items=items
    )
