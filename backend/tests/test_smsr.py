"""Official agricultural drought criterion (IUNG SMSR) and the IUNG soil category map."""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
from shapely.geometry import box
from test_diagnosis import _water
from test_recommendations import SANDY

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.diagnosis import diagnose
from retencja_api.assessment.smsr import THRESHOLDS, last_period, smsr_check
from retencja_api.drought.smsr_gmina import gmina_teryt, parse, with_official
from retencja_api.meteo.openmeteo import DailyWeather
from retencja_api.models import SmsrCheck
from retencja_api.soil.iung import sample_points, with_iung_category

WHEAT = CROP_PARAMS["zboza_ozime"]
PAGE = Path(__file__).parent / "data" / "smsr_kruszwica_2025.html"


def _weather(start: date, end: date, rain: float, et0: float) -> DailyWeather:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    n = len(days)
    return DailyWeather(days=days, precipitation=np.full(n, rain), et0=np.full(n, et0),
                        tmax=np.full(n, 25.0), soil_moisture=np.full(n, 0.3),
                        latitude=52.0, longitude=17.0)


def test_threshold_table_has_every_crop_and_category():
    assert len(THRESHOLDS) == 14
    assert all(set(t) == {"I", "II", "III", "IV"} for t in THRESHOLDS.values())
    assert all(len(row) == 14 for t in THRESHOLDS.values() for row in t.values())
    assert THRESHOLDS["zboza_ozime"]["I"][0] == -129  # 21.III–20.V, rozp. MRiRW 2019


def test_last_complete_period():
    assert last_period(date(2025, 6, 15)) == (date(2025, 4, 11), date(2025, 6, 10))
    assert last_period(date(2025, 5, 19)) is None  # the first period ends on 20 May
    assert last_period(date(2025, 11, 20)) is None  # SMSR ends on 30 September


def test_kbw_below_threshold_is_drought():
    dry = _weather(date(2025, 3, 1), date(2025, 6, 15), rain=0.5, et0=4.0)  # −3.5 mm/day
    check = smsr_check(dry, "zboza_ozime", "I", date(2025, 6, 15))
    assert check.kbw_mm == round(-3.5 * 61) and check.threshold_mm == -137 and check.drought
    assert smsr_check(dry, "laki", "I", date(2025, 6, 15)) is None  # grassland: no SMSR


def test_gmina_table_is_parsed_and_overrides_the_computed_result():
    table = parse(PAGE.read_text(encoding="utf-8"))
    assert table["I"]["zboza_ozime"][:2] == ["+", "-"]
    computed = SmsrCheck(period_start=date(2025, 3, 21), period_end=date(2025, 5, 20),
                         soil_category="I", kbw_mm=-100, threshold_mm=-129, drought=False)
    official = with_official(computed, table, "zboza_ozime")
    assert official.drought and official.official
    assert with_official(computed, table, "laki") == computed


def test_gmina_teryt_from_parcel_id():
    assert gmina_teryt("040706_5.0016.51/1") == "0407063"  # rural part of a mixed gmina
    assert gmina_teryt("121009_2.0004.1557/2") == "1210092"
    assert gmina_teryt("146510_8.0502.1/3") is None  # Warsaw district


def test_official_drought_sets_the_level_and_its_absence_caps_it():
    def with_smsr(drought: bool, official: bool):
        water = _water(20, 1, reanalysis_rank=1)
        water.smsr = SmsrCheck(period_start=date(2025, 4, 11), period_end=date(2025, 6, 10),
                               soil_category="III", kbw_mm=-80, threshold_mm=-196,
                               drought=drought, official=official)
        return diagnose(WHEAT, 10, water, None, None, None, None, [])

    assert with_smsr(drought=False, official=True).level == "watch"
    assert with_smsr(drought=False, official=False).level == "moderate"  # not capped
    calm = _water(80, 6)
    calm.smsr = SmsrCheck(period_start=date(2025, 4, 11), period_end=date(2025, 6, 10),
                          soil_category="III", kbw_mm=-250, threshold_mm=-196, drought=True,
                          official=True)
    assert diagnose(WHEAT, 10, calm, None, None, None, None, []).level == "moderate"


def test_iung_category_replaces_texture_category():
    assert sample_points(box(0, 0, 300, 300))
    assert len(sample_points(box(0, 0, 300, 300))) == 9
    cat = with_iung_category(SANDY, 4)
    assert cat.category == "IV" and cat.category_source == "IUNG"
    peat = with_iung_category(SANDY, 5)
    assert peat.organic_soil and peat.category == SANDY.category
    assert with_iung_category(SANDY, 11) == SANDY  # forest: keep the texture category
