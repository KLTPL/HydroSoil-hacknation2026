from datetime import date, timedelta

import numpy as np

from retencja_api.assessment.crop_params import CROP_PARAMS, KC_OFF_SEASON
from retencja_api.assessment.water_balance import (
    assess_water,
    compare,
    same_date,
    simulate_root_zone,
)
from retencja_api.meteo.openmeteo import DailyWeather, parse_daily

CROP = CROP_PARAMS["zboza_ozime"]


def _weather(start: date, days: int, rain: float, et0: float) -> DailyWeather:
    return DailyWeather(
        days=[start + timedelta(days=i) for i in range(days)],
        precipitation=np.full(days, rain),
        et0=np.full(days, et0),
        tmax=np.full(days, 20.0),
        soil_moisture=np.full(days, 0.3),
        latitude=52.0,
        longitude=18.0,
    )


def test_compare_ranks_driest_year_first():
    result = compare({2020: 10.0, 2021: 30.0, 2022: 20.0, 2023: 5.0}, 2023)
    assert result.rank == 1
    assert result.years == 4
    assert result.normal == 20.0
    assert [h.year for h in result.history] == [2020, 2021, 2022]


def test_same_date_handles_leap_day():
    assert same_date(date(2024, 2, 29), 2023) == date(2023, 2, 28)


def test_kc_follows_stages():
    assert CROP.kc(date(2025, 1, 10)) == KC_OFF_SEASON
    assert CROP.kc(date(2025, 6, 1)) == CROP.kc_mid
    assert CROP.kc_ini < CROP.kc(date(2025, 5, 1)) < CROP.kc_mid


def test_root_zone_dries_without_rain_and_refills_with_it():
    taw = 100.0
    dry = _weather(date(2025, 6, 1), 60, rain=0.0, et0=5.0)
    depletion, ks = simulate_root_zone(dry, CROP, taw)
    assert depletion[-1] <= taw
    assert depletion[-1] > CROP.depletion_p * taw  # crop under stress
    assert ks[-1] < 1.0
    assert np.all(np.diff(depletion) >= 0)

    wet = _weather(date(2025, 6, 1), 60, rain=10.0, et0=5.0)
    depletion, ks = simulate_root_zone(wet, CROP, taw)
    assert depletion.max() == 0.0
    assert ks.min() == 1.0


def test_assess_water_compares_with_earlier_years():
    weather = _weather(date(2014, 11, 1), 4000, rain=1.0, et0=2.0)
    weather.precipitation[weather.index(date(2025, 4, 20)) : weather.index(date(2025, 6, 16))] = 0
    result = assess_water(weather, CROP, 150.0, date(2025, 6, 15), 10)

    assert result.window.precipitation_mm.rank == 1
    assert result.window.kbw_mm.value < result.window.kbw_mm.normal
    assert result.available_pct.rank == 1
    assert result.in_season
    assert result.taw_mm == 150.0 * CROP.root_depth_m
    assert [m.month for m in result.risk_calendar] == [4, 5, 6, 7, 8, 9]


def test_parse_daily_turns_missing_values_into_nan():
    payload = {
        "latitude": 52.0,
        "longitude": 18.0,
        "daily": {
            "time": ["2025-06-01", "2025-06-02"],
            "precipitation_sum": [1.0, None],
            "et0_fao_evapotranspiration": [3.0, 3.1],
            "temperature_2m_max": [25.0, 26.0],
            "soil_moisture_0_to_100cm_mean": [None, 0.3],
        },
    }
    weather = parse_daily(payload)
    assert np.isnan(weather.precipitation[1])
    assert np.isnan(weather.soil_moisture[0])
    assert weather.last_complete_day() == date(2025, 6, 1)
