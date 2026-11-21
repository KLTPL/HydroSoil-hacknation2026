from datetime import UTC, date, datetime

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.recommendations import CATEGORY_ORDER, recommend
from retencja_api.models import (
    Assumptions,
    Comparison,
    DitchWeirs,
    Range,
    RetentionAnalysis,
    RetentionSummary,
    RiskMonth,
    SoilLayer,
    SoilProfile,
    WaterBalance,
    WeatherWindow,
)

CROP = CROP_PARAMS["zboza_ozime"]


def _cmp(value: float, normal: float = 0.0) -> Comparison:
    return Comparison(value=value, normal=normal, rank=5, years=11, history=[])


def _water(available_pct: float, in_season: bool = True, risky: int = 0) -> WaterBalance:
    return WaterBalance(
        window=WeatherWindow(
            start=date(2025, 4, 17), end=date(2025, 6, 15), precipitation_mm=_cmp(100),
            et0_mm=_cmp(200), kbw_mm=_cmp(-100), hot_days=_cmp(1),
        ),
        in_season=in_season, kc=1.15, taw_mm=120.0, raw_mm=66.0,
        available_pct=_cmp(available_pct), stress_days_30=0, reanalysis_soil_moisture=None,
        soil_moisture_source="test",
        risk_calendar=[RiskMonth(month=6, years_with_stress=risky, years=10, mean_stress_days=5)],
        critical_stage="kłoszenie", grid_lat=52.0, grid_lon=18.0, open_canopy_et0_mm=150.0,
    )


SANDY = SoilProfile(
    texture="piasek gliniasty", category="II", category_label="podatna na suszę",
    awc_mm_per_m=90, organic_carbon_pct=0.8,
    layers=[SoilLayer(depth="0-5cm", clay_pct=6, sand_pct=78, silt_pct=16,
                      organic_carbon_pct=0.8)],
    resolution_m=250,
)


def _terrain(ditches: list[DitchWeirs]) -> RetentionAnalysis:
    return RetentionAnalysis(
        parcel_id="x", computed_at=datetime.now(UTC),
        summary=RetentionSummary(site_count=0, storage_m3=0, retained_m3=Range(low=0, high=0)),
        sites=[],
        assumptions=Assumptions(dem_source="t", resolution_m=2, design_rain_mm=30,
                                runoff_coeff=Range(low=0.05, high=0.25), min_depth_m=0.15,
                                min_area_m2=300),
        ditches=ditches, ditches_checked=True,
    )


DITCH = DitchWeirs(
    id=1, kind="ditch", length_m=400, slope_pct=0.2, weir_count=2, weir_head_m=0.5,
    channel_m3=150, soil_m3=Range(low=1000, high=3000),
    geometry={"type": "LineString", "coordinates": [[18, 52], [18.01, 52]]},
    weirs={"type": "MultiPoint", "coordinates": [[18, 52]]},
)


def test_irrigation_only_when_crop_is_stressed_and_comes_last():
    # KOWR sequence: retention and agrotechnics first, irrigation only as the last resort.
    stressed = recommend(CROP, 10, _water(20), SANDY, None, _terrain([DITCH]))
    assert stressed[-1].key == "irrigation"
    # A ditch now yields two retention measures (weirs, grass buffer), so check the whole
    # sequence rather than the first two items.
    categories = [r.category for r in stressed]
    assert categories[0] == "retention" and "soil" in categories
    assert categories == sorted(categories, key=CATEGORY_ORDER.__getitem__)
    assert stressed[-1].effect_m3.high == round(120 * 0.8 * 10 * 10)
    assert all(r.key != "irrigation" for r in recommend(CROP, 10, _water(80), None, None, None))
    off = recommend(CROP, 10, _water(20, in_season=False), None, None, None)
    assert all(r.key != "irrigation" for r in off)


def test_weirs_from_ditches_and_sorted_by_effect():
    recs = recommend(CROP, 10, _water(80), SANDY, None, _terrain([DITCH]))
    keys = [r.key for r in recs]
    assert "weirs" in keys and "organic_matter" in keys and "mulch" in keys
    weirs = next(r for r in recs if r.key == "weirs")
    assert weirs.effect_m3 == Range(low=1150, high=3150)
    assert weirs.ditch_ids == [1]
    effects = [r.effect_m3.high for r in recs if r.effect_m3]
    assert effects == sorted(effects, reverse=True)


def test_crop_timing_needs_frequent_stress():
    assert "crop_timing" not in [r.key for r in recommend(CROP, 1, _water(80), None, None, None)]
    risky = recommend(CROP, 1, _water(80, risky=4), None, None, None)
    timing = next(r for r in risky if r.key == "crop_timing")
    assert "czerwcu" in timing.why


def test_polish_plural():
    from retencja_api.assessment.recommendations import plural

    forms = ("zastawkę", "zastawki", "zastawek")
    assert [plural(n, *forms) for n in (1, 2, 4, 5, 12, 22, 25)] == [
        "zastawkę", "zastawki", "zastawki", "zastawek", "zastawek", "zastawki", "zastawek",
    ]
