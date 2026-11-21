"""Edge cases found by the production audit (docs/metody-i-walidacja.md, section d)."""

from datetime import date

from test_diagnosis import _cmp, _vegetation
from test_diagnosis import _water as _diag_water
from test_recommendations import SANDY, _water

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.diagnosis import diagnose
from retencja_api.assessment.recommendations import recommend
from retencja_api.assessment.water_balance import compare
from retencja_api.landcover.worldcover import summarize
from retencja_api.models import VegetationObservation, VegetationState

WHEAT = CROP_PARAMS["zboza_ozime"]


def test_full_soil_in_every_year_is_typical_not_driest():
    c = compare({y: 100.0 for y in range(2015, 2026)}, 2025)
    assert c.rank == 6 and c.years == 11


def test_satellite_needs_three_years_and_a_closed_canopy():
    few_years = _vegetation(0.1, 0.3).model_copy(update={"ndmi": _cmp(0.1, 0.3, 1).model_copy(
        update={"years": 2})})
    bare = VegetationState(
        current=VegetationObservation(year=2025, date=date(2025, 6, 15), ndvi=0.2, ndmi=0.0,
                                      clear_pct=99),
        history=[], ndvi=_cmp(0.2, 0.7, 1), ndmi=_cmp(0.0, 0.3, 1), window_days=10,
        missing_years=[],
    )
    for veg in (few_years, bare):
        d = diagnose(WHEAT, 10, _diag_water(60, 6), None, veg, None, None, [])
        sat = next(s for s in d.signals if s.key == "satellite")
        assert sat.verdict == "missing" and sat.note


def test_ripening_cereal_is_not_compared_by_satellite():
    veg = _vegetation(0.1, 0.3)
    late = veg.model_copy(update={"current": veg.current.model_copy(
        update={"date": date(2025, 7, 20)})})
    d = diagnose(WHEAT, 10, _diag_water(60, 6), None, late, None, None, [])
    assert next(s for s in d.signals if s.key == "satellite").verdict == "missing"


def test_wet_sources_cancel_dry_ones():
    # Soil model wettest of 11 years, ERA5-Land driest: one vote each way.
    d = diagnose(WHEAT, 10, _diag_water(80, 11, reanalysis_rank=1), None, None, None, None, [])
    assert d.level == "none"


def test_non_farmland_gets_retention_advice_only():
    forest = summarize({10: 90, 40: 10})
    recs = recommend(WHEAT, 5, _water(20), SANDY, None, None, None, forest)
    assert all(r.category == "retention" for r in recs)
    assert any(r.key == "irrigation" for r in recommend(WHEAT, 5, _water(20), SANDY, None, None))


def test_humus_rich_soil_gets_no_humus_advice():
    rich = SANDY.model_copy(update={"organic_carbon_pct": 6.5})
    assert all(r.key != "organic_matter" for r in recommend(WHEAT, 5, _water(80), rich, None,
                                                             None))


def test_irrigation_doses_follow_the_dose():
    small = next(r for r in recommend(WHEAT, 5, _water(85 - 75), None, None, None)
                 if r.key == "irrigation")
    assert "dawkach po ok." in small.action
    tiny_water = _water(40).model_copy(update={"taw_mm": 30.0})
    one = next(r for r in recommend(WHEAT, 5, tiny_water, None, None, None)
               if r.key == "irrigation")
    assert "jednorazowo" in one.action
