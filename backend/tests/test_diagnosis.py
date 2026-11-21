from datetime import date

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.diagnosis import diagnose
from retencja_api.models import (
    Comparison,
    RiskMonth,
    VegetationObservation,
    VegetationState,
    WaterBalance,
    WeatherWindow,
)

CROP = CROP_PARAMS["zboza_ozime"]
THRESHOLD = round(100 * (1 - CROP.depletion_p))


def _cmp(value: float, normal: float, rank: int) -> Comparison:
    return Comparison(value=value, normal=normal, rank=rank, years=11, history=[])


def _water(available: float, rank: int, reanalysis_rank: int | None = None) -> WaterBalance:
    return WaterBalance(
        window=WeatherWindow(
            start=date(2025, 4, 17), end=date(2025, 6, 15),
            precipitation_mm=_cmp(100, 97, 6), et0_mm=_cmp(208, 219, 5),
            kbw_mm=_cmp(-107, -122, 7), hot_days=_cmp(0, 0.3, 5),
        ),
        in_season=True, kc=1.2, taw_mm=125.0, raw_mm=69.0,
        available_pct=_cmp(available, 23, rank), stress_days_30=0,
        reanalysis_soil_moisture=(
            None if reanalysis_rank is None else _cmp(0.20, 0.33, reanalysis_rank)
        ),
        soil_moisture_source="ERA5-Land 0–100 cm",
        risk_calendar=[RiskMonth(month=6, years_with_stress=4, years=10, mean_stress_days=9)],
        critical_stage="kłoszenie", grid_lat=52.7, grid_lon=18.3, open_canopy_et0_mm=150.0,
    )


def _vegetation(ndmi: float, normal: float) -> VegetationState:
    obs = VegetationObservation(year=2025, date=date(2025, 6, 15), ndvi=0.72, ndmi=ndmi,
                                clear_pct=98)
    return VegetationState(current=obs, history=[], ndvi=_cmp(0.72, 0.80, 2),
                           ndmi=_cmp(ndmi, normal, 1), window_days=10, missing_years=[])


def test_headline_separates_crop_stress_from_comparison_with_past_years():
    # Typical soil-model value for the date, but reanalysis and satellite say drier.
    d = diagnose(CROP, 17.3, _water(22, rank=5, reanalysis_rank=1), None,
                 _vegetation(0.32, 0.46), None, None, [])
    assert d.level == "severe"
    assert d.stress_threshold_pct == THRESHOLD
    assert d.headline.startswith("Uprawa cierpi z braku wody: w strefie korzeni zostało 22 %")
    assert "2 z 4 źródeł" in d.headline
    verdicts = {s.key: s.verdict for s in d.signals}
    assert verdicts == {"soil_model": "normal", "kbw": "normal", "reanalysis": "dry",
                        "satellite": "dry"}


def test_missing_sources_are_listed_not_hidden():
    d = diagnose(CROP, 10, _water(80, rank=6), None, None, None, None, [])
    assert d.level == "none"
    assert "typowa sytuacja" in d.headline
    missing = [s.key for s in d.signals if s.verdict == "missing"]
    assert missing == ["reanalysis", "satellite"]


def test_disagreeing_sources_lower_confidence():
    wet_model = _water(40, rank=11, reanalysis_rank=1)  # wettest in the model, driest in ERA5
    d = diagnose(CROP, 10, wet_model, None, None, None, None, [])
    assert "nie są zgodne" in d.headline
    assert d.confidence == "medium"
