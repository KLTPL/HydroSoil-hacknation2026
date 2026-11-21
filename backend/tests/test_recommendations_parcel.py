"""Recommendations fitted to the parcel's shape, slope, soil and crop group."""

from datetime import date

from test_recommendations import DITCH, SANDY, _terrain, _water

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.diagnosis import diagnose
from retencja_api.assessment.recommendations import recommend
from retencja_api.models import (
    Comparison,
    ParcelShape,
    Range,
    RetentionSite,
    RetentionSummary,
    TerrainSlope,
    VegetationObservation,
    VegetationState,
)

ARABLE = CROP_PARAMS["zboza_ozime"]


def _shape(width: float, length: float, axis: int, narrow: bool) -> ParcelShape:
    return ParcelShape(length_m=length, width_m=width, box_width_m=width,
                       elongation=length / width, compactness=0.5, axis_azimuth_deg=axis,
                       narrow_strip=narrow, winding=False)


def _slope(mean: float, fall: int | None, steep_share: float = 0.0, steep_ha: float = 0.0,
           relative: float = 0.0) -> TerrainSlope:
    return TerrainSlope(mean_pct=mean, p90_pct=mean * 2, steep_share=steep_share,
                        steep_ha=steep_ha, fall_azimuth_deg=fall, relative_height_m=relative,
                        outflow_edge_m=200, outflow_area_ha=3.0, runon_area_ha=0.5)


SITE = RetentionSite(
    id=1, kind="pond", area_m2=400, max_depth_m=0.8, storage_m3=200, catchment_ha=1.0,
    runoff_m3=Range(low=15, high=75), retained_m3=Range(low=15, high=75), parcel_share=0.5,
    geometry={"type": "Polygon", "coordinates": []},
)


def _hilly(ditches=(), sites=(), slope=None):
    t = _terrain(list(ditches))
    return t.model_copy(update={
        "slope": slope,
        "sites": list(sites),
        "summary": RetentionSummary(site_count=len(sites), storage_m3=200,
                                    retained_m3=Range(low=15, high=75)),
    })


def _water_etc(available: float = 80):
    return _water(available).model_copy(update={"season_etc_mm": 400.0})


def _keys(recs):
    return [r.key for r in recs]


def test_downhill_narrow_strip_gets_cross_strips_and_no_pond():
    terrain = _hilly(sites=[SITE], slope=_slope(8, fall=180))
    strip = _shape(15, 400, axis=0, narrow=True)  # runs north–south, slope falls south
    recs = recommend(ARABLE, 0.6, _water_etc(), SANDY, None, terrain, strip)
    keys = _keys(recs)
    assert "narrow_strip" in keys
    assert not {"contour_tillage", "slope_buffer", "shelterbelt"} & set(keys)
    advice = next(r for r in recs if r.key == "narrow_strip")
    assert "w poprzek pasa" in advice.action and "sąsiad" in advice.action
    assert "ok. 10 miedz" in advice.action  # 400 m / 40 m spacing on an 8 % slope
    ponds = next(r for r in recs if r.key == "ponds")
    assert "nie kop" in ponds.action and ponds.formalities is None


def test_strip_across_the_slope_is_told_to_cooperate_not_to_dig():
    terrain = _hilly(slope=_slope(8, fall=90))
    recs = recommend(ARABLE, 0.6, _water_etc(), None, None, terrain,
                     _shape(15, 400, axis=0, narrow=True))
    advice = next(r for r in recs if r.key == "narrow_strip")
    assert "nie ma miejsca na oczko" in advice.action and advice.effect_m3 is None


def test_wide_sloping_field_gets_slope_measures_in_retention_first_order():
    slope = _slope(6, fall=90, steep_share=0.2, steep_ha=1.0)
    recs = recommend(ARABLE, 5, _water_etc(), SANDY, None, _hilly([DITCH], slope=slope),
                     _shape(200, 250, axis=0, narrow=False))
    keys = _keys(recs)
    for key in ("steep_grass", "slope_buffer", "ditch_buffer", "shelterbelt",
                "contour_tillage", "cover_crops"):
        assert key in keys, key
    steep = next(r for r in recs if r.key == "steep_grass")
    assert steep.effect_m3 == Range(low=30, high=60)  # 1 ha × 30 mm × 0.1–0.2
    contour = next(r for r in recs if r.key == "contour_tillage")
    assert "północ–południe" in contour.action  # slope falls east → work north–south
    belt = next(r for r in recs if r.key == "shelterbelt")
    assert "poziomicy" in belt.action
    # 250 m belt protecting the 200 m width (≤ 150 m reach): 3.75 ha × 400 mm × 5–15 %
    assert belt.effect_m3 == Range(low=750, high=2250)


def test_flat_field_has_no_slope_measures():
    recs = recommend(ARABLE, 5, _water_etc(), SANDY, None, _hilly(slope=_slope(0.5, None)),
                     _shape(200, 250, axis=0, narrow=False))
    assert not {"steep_grass", "slope_buffer", "contour_tillage"} & set(_keys(recs))
    belt = next(r for r in recs if r.key == "shelterbelt")
    assert "dłuższej krawędzi od strony zachodniej" in belt.action


def test_grassland_gets_sward_advice_instead_of_tillage():
    meadow = CROP_PARAMS["laki"]
    slope = _slope(6, fall=90, steep_share=0.2, steep_ha=1.0)
    recs = recommend(meadow, 5, _water_etc(), SANDY, None, _hilly([DITCH], slope=slope),
                     _shape(200, 250, axis=0, narrow=False))
    keys = set(_keys(recs))
    assert "grass_management" in keys
    assert not {"mulch", "cover_crops", "crop_timing", "contour_tillage", "steep_grass",
                "ditch_buffer", "slope_buffer"} & keys
    om = next(r for r in recs if r.key == "organic_matter")
    assert "nie zaorywuj darni" in om.action


def test_orchard_mulches_the_rows_and_irrigates_by_drip():
    orchard = CROP_PARAMS["drzewa_owocowe"]
    recs = recommend(orchard, 2, _water(10), SANDY, None, None)
    keys = _keys(recs)
    assert "crop_timing" not in keys and "cover_crops" not in keys
    mulch = next(r for r in recs if r.key == "mulch")
    assert "pod drzewami" in mulch.action
    assert "kroplowo" in next(r for r in recs if r.key == "irrigation").action


def test_organic_soil_gets_wetland_advice():
    peat = SANDY.model_copy(update={"organic_carbon_pct": 9.0})
    recs = recommend(ARABLE, 4, _water_etc(), peat, None, None)
    wet = next(r for r in recs if r.key == "wetland")
    assert wet.category == "retention" and "Nie pogłębiaj rowów" in wet.action
    assert wet.effect_m3 == Range(low=800, high=1600)  # 4 ha × 0.2 m × 0.1–0.2
    assert "wetland" not in _keys(recommend(ARABLE, 4, _water_etc(), SANDY, None, None))


def test_irrigation_shows_parcel_volume_cost_and_permit_limit():
    recs = recommend(ARABLE, 10, _water(20), None, None, None)
    rec = next(r for r in recs if r.key == "irrigation")
    est = rec.irrigation
    assert est.water_m3 == round(120 * 0.8 * 10 * 10) == rec.effect_m3.high
    assert est.cost_pln == Range(low=round(9600 * 0.5, -1), high=round(9600 * 2.0, -1))
    assert est.yearly_limit_m3 == 5 * 365 and est.over_limit
    assert "5 m³ na dobę" in rec.formalities and "źródło wody" in rec.formalities


def test_grassland_ndmi_drop_without_dry_soil_is_read_as_mowing():
    obs = VegetationObservation(year=2025, date=date(2025, 6, 15), ndvi=0.5, ndmi=0.1,
                                clear_pct=98)
    cmp = Comparison(value=0.1, normal=0.3, rank=1, years=11, history=[])
    veg = VegetationState(current=obs, history=[], ndvi=cmp, ndmi=cmp, window_days=20,
                          missing_years=[])
    meadow = diagnose(CROP_PARAMS["laki"], 5, _water(80), None, veg, None, None, [])
    sat = next(s for s in meadow.signals if s.key == "satellite")
    assert sat.verdict == "normal" and "pokosie" in sat.note
    assert any("pokosie" in x for x in meadow.limitations)
    wheat = diagnose(ARABLE, 5, _water(80), None, veg, None, None, [])
    assert next(s for s in wheat.signals if s.key == "satellite").verdict == "dry"
