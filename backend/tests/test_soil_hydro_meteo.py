from datetime import date

import numpy as np
import pytest

from retencja_api.hydro.imgw import warnings_for
from retencja_api.meteo.nasa_power import extraterrestrial_radiation, penman_monteith
from retencja_api.soil.soilgrids import available_water, build_profile, soil_category


def test_available_water_is_larger_for_loam_than_sand():
    sand = available_water(0.9, 0.04, 1.0)
    loam = available_water(0.4, 0.2, 2.5)
    assert 0.03 < sand < 0.1
    assert loam > sand


def test_organic_matter_increases_available_water():
    assert available_water(0.6, 0.1, 3.0) > available_water(0.6, 0.1, 1.0)


@pytest.mark.parametrize(
    ("sand", "clay", "category"),
    [(90, 3, "I"), (75, 8, "II"), (40, 15, "III"), (20, 35, "IV")],
)
def test_soil_category(sand, clay, category):
    assert soil_category(sand, clay)[1] == category


def test_build_profile_from_soilgrids_units():
    raw = {"clay": [100.0] * 5, "sand": [700.0] * 5, "soc": [120.0] * 5}  # g/kg, dg/kg
    profile = build_profile(raw)
    assert profile.layers[0].clay_pct == 10.0
    assert profile.layers[0].organic_carbon_pct == 1.2
    assert profile.category == "III"
    assert 60 < profile.awc_mm_per_m < 200


def test_extraterrestrial_radiation_matches_fao56_example():
    # FAO-56 example 8: 3 September, 20°S → Ra = 32.2 MJ m⁻² day⁻¹
    assert extraterrestrial_radiation([date(2015, 9, 3)], -20.0)[0] == pytest.approx(32.2, 0.01)


def test_penman_monteith_is_plausible_for_a_polish_summer_day():
    one = np.array
    et0 = penman_monteith(
        [date(2025, 7, 1)], 52.0, 100.0, one([20.0]), one([26.0]), one([14.0]), one([65.0]),
        one([2.0]), one([22.0]),
    )
    assert 3.5 < et0[0] < 5.5


WARNINGS = [
    {
        "numer": "21", "zdarzenie": "Susza hydrologiczna", "prawdopodobienstwo": "90",
        "data_od": "2026-04-17 08:46:51", "data_do": "9999-12-31 23:59:59", "biuro": "BPH",
        "przebieg": "Niskie przepływy.",
        "obszary": [{"wojewodztwo": "łódzkie", "opis": "łódzkie, Warta górna"}],
    },
    {
        "numer": "5", "zdarzenie": "Wezbranie z przekroczeniem stanów ostrzegawczych",
        "prawdopodobienstwo": "80", "data_od": "", "data_do": "", "biuro": "BPH",
        "przebieg": "", "obszary": [{"wojewodztwo": "łódzkie", "opis": "łódzkie"}],
    },
]


def test_warnings_for_matches_voivodeship():
    status = warnings_for("Łódzkie", WARNINGS)
    assert len(status.drought_warnings) == 1
    assert status.drought_warnings[0].valid_to is None
    assert status.other_warnings == 1
    assert warnings_for("mazowieckie", WARNINGS).drought_warnings == []


def test_land_cover_flags_built_up_parcel():
    from retencja_api.assessment.diagnosis import land_warnings
    from retencja_api.landcover.worldcover import summarize

    arena = summarize({50: 70, 30: 20, 10: 10})
    assert not arena.is_agricultural
    assert arena.classes[0].name == "zabudowa"
    assert "nie wygląda na rolniczą" in land_warnings(arena)[0]

    field = summarize({40: 90, 30: 5, 50: 5})
    assert field.is_agricultural and field.agricultural_share == 0.95
    assert land_warnings(field) == []
