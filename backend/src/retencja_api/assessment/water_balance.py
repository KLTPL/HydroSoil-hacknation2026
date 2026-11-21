"""Water situation at the parcel on the analysis date, compared with the same date in
earlier years: climatic water balance (IUNG method, 60-day window) and a daily
root-zone soil water balance (FAO-56 single crop coefficient, Allen et al.)."""

from datetime import date, timedelta

import numpy as np

from retencja_api.assessment.crop_params import CropParams
from retencja_api.meteo.openmeteo import DailyWeather
from retencja_api.models import Comparison, RiskMonth, WaterBalance, WeatherWindow, YearValue

KBW_WINDOW_DAYS = 60  # IUNG SMSR assesses six consecutive 10-day periods
STRESS_LOOKBACK_DAYS = 30
HOT_DAY_C = 30.0
RISK_MONTHS = range(4, 10)  # April–September
# Strong water stress: the crop transpires at less than half its potential rate.
# Calibrated so known drought summers (2015, 2018, 2019) stand out from normal ones.
STRONG_STRESS_KS = 0.5
STRESS_MONTH_MIN_DAYS = 15  # a month counts as dry when the crop was stressed this long


def same_date(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:  # 29 February
        return day.replace(year=year, day=28)


def compare(values: dict[int, float], year: int) -> Comparison:
    """Rank `values[year]` among all years with data (1 = lowest)."""
    earlier = {y: v for y, v in values.items() if y < year and np.isfinite(v)}
    current = values[year]
    ordered = sorted([current, *earlier.values()])
    return Comparison(
        value=round(current, 2),
        normal=round(float(np.mean(list(earlier.values()))), 2) if earlier else current,
        rank=ordered.index(current) + 1,
        years=len(ordered),
        history=[YearValue(year=y, value=round(v, 2)) for y, v in sorted(earlier.items())],
    )


def run_root_zone(
    days: list[date],
    precipitation: np.ndarray,
    et0: np.ndarray,
    crop: CropParams,
    taw_mm: float,
    start_depletion_mm: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Daily root-zone depletion (mm below field capacity) and water stress coefficient Ks.

    Rain above what the soil can hold is lost to drainage or runoff.
    """
    raw = crop.depletion_p * taw_mm
    precipitation = np.nan_to_num(precipitation)
    et0 = np.nan_to_num(et0)
    depletion = np.empty(len(days))
    ks = np.empty(len(days))
    dr = start_depletion_mm
    for i, day in enumerate(days):
        k = 1.0 if dr <= raw else max(0.0, (taw_mm - dr) / (taw_mm - raw))
        dr = min(max(dr - precipitation[i] + k * crop.kc(day) * et0[i], 0.0), taw_mm)
        depletion[i] = dr
        ks[i] = k
    return depletion, ks


def simulate_root_zone(
    weather: DailyWeather, crop: CropParams, taw_mm: float
) -> tuple[np.ndarray, np.ndarray]:
    """Whole-series run starting at field capacity; winter recharge refills the soil anyway."""
    return run_root_zone(weather.days, weather.precipitation, weather.et0, crop, taw_mm)


def _window_sum(series: np.ndarray, end: int, days: int) -> float:
    return float(np.nansum(series[end - days + 1 : end + 1]))


def _by_year(weather: DailyWeather, day: date, years: int, fn) -> dict[int, float]:
    out = {}
    for year in range(day.year - years, day.year + 1):
        i = weather.index(same_date(day, year))
        if KBW_WINDOW_DAYS <= i < len(weather.days):
            out[year] = fn(i)
    return out


def risk_calendar(
    weather: DailyWeather, ks: np.ndarray, crop: CropParams, last_year: int, years: int
) -> list[RiskMonth]:
    """For each month, in how many of the past full years the crop suffered strong water
    stress on at least STRESS_MONTH_MIN_DAYS days."""
    out = []
    for month in RISK_MONTHS:
        stress_per_year = []
        for year in range(last_year - years + 1, last_year + 1):
            start = date(year, month, 1)
            end = date(year + (month == 12), month % 12 + 1, 1)
            i0, i1 = weather.index(start), weather.index(end)
            if i0 < 0 or i1 > len(weather.days):
                continue
            stressed = sum(
                1
                for i in range(i0, i1)
                if ks[i] < STRONG_STRESS_KS and crop.in_season(weather.days[i])
            )
            stress_per_year.append(stressed)
        if stress_per_year:
            out.append(
                RiskMonth(
                    month=month,
                    years_with_stress=sum(d >= STRESS_MONTH_MIN_DAYS for d in stress_per_year),
                    years=len(stress_per_year),
                    mean_stress_days=round(float(np.mean(stress_per_year)), 1),
                )
            )
    return out


def open_canopy_et0(weather: DailyWeather, crop: CropParams, last_year: int, years: int) -> float:
    """Mean ET0 between sowing (or regrowth) and canopy closure, when bare soil evaporates."""
    totals = []
    for year in range(last_year - years + 1, last_year + 1):
        start, _, mid, *_ = crop.stages(year)
        i0, i1 = weather.index(start), weather.index(mid)
        if 0 <= i0 and i1 <= len(weather.days):
            totals.append(float(np.nansum(weather.et0[i0:i1])))
    return round(float(np.mean(totals)), 1) if totals else 0.0


def assess_water(
    weather: DailyWeather, crop: CropParams, awc_mm_per_m: float, day: date, years: int
) -> WaterBalance:
    end = weather.index(day)
    if not 0 <= end < len(weather.days):
        raise ValueError(f"No weather data for {day}")
    taw = awc_mm_per_m * crop.root_depth_m
    depletion, ks = simulate_root_zone(weather, crop, taw)
    kbw = weather.precipitation - weather.et0

    def window(series: np.ndarray, threshold: float | None = None) -> Comparison:
        def value(i: int) -> float:
            if threshold is None:
                return _window_sum(series, i, KBW_WINDOW_DAYS)
            chunk = series[i - KBW_WINDOW_DAYS + 1 : i + 1]
            return float(np.sum(chunk >= threshold))

        return compare(_by_year(weather, day, years, value), day.year)

    available = _by_year(weather, day, years, lambda i: 100 * (1 - depletion[i] / taw))
    soil_moisture = _by_year(weather, day, years, lambda i: float(weather.soil_moisture[i]))
    reanalysis = (
        compare(soil_moisture, day.year)
        if np.isfinite(soil_moisture.get(day.year, np.nan))
        else None
    )
    recent = range(max(0, end - STRESS_LOOKBACK_DAYS + 1), end + 1)
    return WaterBalance(
        window=WeatherWindow(
            start=day - timedelta(days=KBW_WINDOW_DAYS - 1),
            end=day,
            precipitation_mm=window(weather.precipitation),
            et0_mm=window(weather.et0),
            kbw_mm=window(kbw),
            hot_days=window(weather.tmax, HOT_DAY_C),
        ),
        in_season=crop.in_season(day),
        kc=round(crop.kc(day), 2),
        taw_mm=round(taw, 1),
        raw_mm=round(crop.depletion_p * taw, 1),
        available_pct=compare(available, day.year),
        stress_days_30=sum(
            1 for i in recent if ks[i] < STRONG_STRESS_KS and crop.in_season(weather.days[i])
        ),
        reanalysis_soil_moisture=reanalysis,
        soil_moisture_source=weather.soil_moisture_source,
        risk_calendar=risk_calendar(weather, ks, crop, day.year - 1, years),
        critical_stage=crop.critical,
        open_canopy_et0_mm=open_canopy_et0(weather, crop, day.year - 1, years),
        grid_lat=weather.latitude,
        grid_lon=weather.longitude,
    )
