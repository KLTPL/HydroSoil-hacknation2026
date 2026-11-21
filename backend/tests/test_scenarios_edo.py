from datetime import date, timedelta

import numpy as np

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.scenarios import SCENARIO_DAYS, build_scenarios
from retencja_api.drought.edo import dekad_start, previous_dekad
from retencja_api.meteo.openmeteo import DailyWeather
from retencja_api.models import EdoDrought, ModuleResult
from retencja_api.progress import module_progress

CROP = CROP_PARAMS["kukurydza_ziarno"]


def _history(day: date, years: int) -> DailyWeather:
    """Ten past summers whose rain grows with the year, so 2016 is driest."""
    start = date(day.year - years - 1, 11, 1)
    days = [start + timedelta(days=i) for i in range((day - start).days + 1)]
    rain = np.array([0.3 * (d.year - day.year + years + 1) for d in days])
    return DailyWeather(
        days=days,
        precipitation=rain,
        et0=np.full(len(days), 4.0),
        tmax=np.full(len(days), 25.0),
        soil_moisture=np.full(len(days), 0.3),
        latitude=52.0,
        longitude=17.0,
    )


def _by_key(scenarios):
    return {s.key: s for s in scenarios.items}


def test_scenarios_rank_dry_typical_wet_and_show_what_helps():
    day = date(2026, 6, 20)
    scenarios = build_scenarios(_history(day, 10), CROP, 120.0, 60.0, day, 10, 8.0)
    s = _by_key(scenarios)
    assert scenarios.start == day + timedelta(days=1)
    assert (scenarios.end - scenarios.start).days == SCENARIO_DAYS - 1
    assert s["dry"].analog_year == 2017  # second driest of 2016–2025
    assert s["no_rain"].rain_mm == 0
    assert s["no_rain"].stress_days >= s["dry"].stress_days >= s["typical"].stress_days
    assert s["typical"].stress_days >= s["wet"].stress_days
    assert s["irrigated"].stress_days <= s["dry"].stress_days
    assert s["irrigated"].available_pct_end > s["dry"].available_pct_end
    assert s["more_humus"].available_pct_end > s["dry"].available_pct_end
    first = s["no_rain"].first_stress_day
    assert first is not None and scenarios.start <= first <= scenarios.end


def test_no_scenarios_outside_the_growing_season():
    day = date(2026, 12, 1)
    assert build_scenarios(_history(day, 10), CROP, 120.0, 0.0, day, 10, 8.0) is None


def test_small_humus_gain_skips_that_scenario():
    day = date(2026, 6, 20)
    scenarios = build_scenarios(_history(day, 10), CROP, 120.0, 60.0, day, 10, 0.2)
    assert "more_humus" not in _by_key(scenarios)


def test_cdi_dekads():
    assert dekad_start(date(2019, 7, 25)) == date(2019, 7, 21)
    assert dekad_start(date(2019, 7, 10)) == date(2019, 7, 1)
    assert previous_dekad(date(2019, 7, 11)) == date(2019, 7, 1)
    assert previous_dekad(date(2019, 3, 1)) == date(2019, 2, 21)


def test_edo_progress_line():
    edo = EdoDrought(dekad=date(2019, 7, 21), cdi_class=2, label="Warning", drought=True)
    result = ModuleResult[EdoDrought](status="ok", data=edo, duration_ms=5)
    assert module_progress("edo", result).fact == "dekada od 21.07.2019: Warning"
