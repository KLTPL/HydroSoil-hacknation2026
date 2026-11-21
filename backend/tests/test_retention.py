import numpy as np
import pytest
from affine import Affine
from shapely.geometry import box

from retencja_api.config import DESIGN_RAIN_MM, RUNOFF_COEFF_RANGE
from retencja_api.terrain.nmt import Dem
from retencja_api.terrain.retention import find_sites

RES = 2.0
SIZE = 40  # grid cells per side
PIT = slice(15, 25)  # 10×10-cell pit (400 m²), above the noise-area threshold
PIT_CELLS = 10
SLOPE = 0.02  # m per cell, rising eastward
PARCEL = box(30, 30, 50, 50)  # exactly covers the pit


def _tilted_plane_with_pit() -> Dem:
    z = np.tile(np.arange(SIZE, dtype=float) * SLOPE, (SIZE, 1))
    z[PIT, PIT] -= 2.0
    return Dem(z, Affine(RES, 0, 0, 0, -RES, SIZE * RES))


def test_finds_pit_with_storage_up_to_spill_level():
    sites = find_sites(_tilted_plane_with_pit(), PARCEL)

    assert len(sites) == 1
    site = sites[0]
    spill = (PIT.start - 1) * SLOPE  # lowest rim: column west of the pit
    bottoms = [c * SLOPE - 2.0 for c in range(PIT.start, PIT.stop)]
    expected_storage = sum(spill - b for b in bottoms) * PIT_CELLS * RES**2
    assert site.kind == "pond"
    assert site.area_m2 == pytest.approx(PIT_CELLS**2 * RES**2)
    # Deepest point is the pit's west column (plane rises eastward).
    assert site.max_depth_m == pytest.approx(spill - bottoms[0], abs=1e-3)
    assert site.storage_m3 == pytest.approx(expected_storage, rel=1e-3)
    assert site.parcel_share == pytest.approx(1.0)


def test_catchment_includes_upslope_cells_and_runoff_uses_coefficients():
    site = find_sites(_tilted_plane_with_pit(), PARCEL)[0]

    east_cells = PIT_CELLS * (SIZE - PIT.stop)
    pit_and_east_rows_m2 = (PIT_CELLS**2 + east_cells) * RES**2
    # Rows directly north/south of the pit may also drain in diagonally.
    upper_bound_m2 = pit_and_east_rows_m2 + 2 * (SIZE - PIT.start + 1) * RES**2
    assert pit_and_east_rows_m2 / 1e4 <= site.catchment_ha <= upper_bound_m2 / 1e4
    catchment_m2 = site.catchment_ha * 1e4
    low, high = (catchment_m2 * DESIGN_RAIN_MM / 1000 * c for c in RUNOFF_COEFF_RANGE)
    assert site.runoff_m3 == pytest.approx((low, high))
    storage = site.storage_m3
    assert site.retained_m3 == pytest.approx((min(low, storage), min(high, storage)))


def test_ignores_depressions_off_the_parcel():
    assert find_sites(_tilted_plane_with_pit(), box(0, 0, 10, 10)) == []


def test_ignores_depressions_touching_missing_data():
    dem = _tilted_plane_with_pit()
    dem.elevation[PIT.start - 1, PIT.start - 1] = np.nan  # pit can drain into unknown terrain

    assert find_sites(dem, PARCEL) == []


def test_ignores_small_depressions_as_noise():
    dem = _tilted_plane_with_pit()
    z = np.tile(np.arange(SIZE, dtype=float) * SLOPE, (SIZE, 1))
    z[18:22, 18:22] -= 2.0  # 4×4 cells = 64 m²
    small = Dem(z, dem.transform)

    assert find_sites(small, PARCEL) == []
