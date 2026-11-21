import io
import itertools

import numpy as np
import rasterio
from affine import Affine

from retencja_api.config import DEM_STRIP_MAX_M2
from retencja_api.terrain.nmt import _mosaic, snap_bounds, split_strips


def _tiff(data: np.ndarray, left: float, top: float, res: float) -> bytes:
    buf = io.BytesIO()
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:2180",
        "transform": Affine(res, 0, left, 0, -res, top),
    }
    with rasterio.MemoryFile() as mem:
        with mem.open(**profile) as dst:
            dst.write(data.astype("float32"), 1)
        buf.write(mem.read())
    return buf.getvalue()


def test_snap_bounds_expands_to_resolution_grid():
    assert snap_bounds((100.5, 201.0, 150.1, 249.9), 2) == (100, 200, 152, 250)


def test_small_area_is_one_strip():
    assert split_strips((0, 0, 100, 100), 2) == [(0, 0, 100, 100)]


def test_large_area_splits_into_contiguous_strips_within_limit():
    bounds = (0, 0, 1000, 1000)

    strips = split_strips(bounds, 2)

    assert len(strips) > 1
    assert strips[0][3] == 1000 and strips[-1][1] == 0
    for upper, lower in itertools.pairwise(strips):
        assert upper[1] == lower[3]  # no gaps or overlaps
    assert all((s[2] - s[0]) * (s[3] - s[1]) <= DEM_STRIP_MAX_M2 for s in strips)


def test_mosaic_places_strips_by_georeference_and_masks_nodata():
    north = np.full((5, 10), 10.0)
    south = np.full((5, 10), 20.0)
    south[0, 0] = -9999.0

    dem = _mosaic([_tiff(north, 0, 20, 2), _tiff(south, 0, 10, 2)], (0, 0, 20, 20), 2)

    assert dem.elevation.shape == (10, 10)
    assert dem.transform == Affine(2, 0, 0, 0, -2, 20)
    assert np.all(dem.elevation[:5] == 10.0)
    assert np.isnan(dem.elevation[5, 0])
    assert dem.elevation[9, 9] == 20.0
