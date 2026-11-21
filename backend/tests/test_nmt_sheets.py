import numpy as np
import rasterio
from affine import Affine

from retencja_api.config import DEM_SHEET_PROBE_STEP_M
from retencja_api.terrain.nmt_sheets import (
    Sheet,
    mosaic_sheets,
    parse_index,
    pick_sheets,
    probe_points,
)

_INDEX_HTML = """
var skor_NMT_wg_akt = [];
skor_NMT_wg_akt.push({url:"https://x/1_A.asc",godlo:"A", aktualnosc:"2022-04-27",
 format:"ARC/INFO ASCII GRID", ukladWspolrzednychPoziomych:"PL-1992", zrDanych:"Skaning laserowy"});
skor_NMT_wg_akt.push({url:"https://x/2_A.asc",godlo:"A", aktualnosc:"2025-04-30",
 format:"ARC/INFO ASCII GRID", ukladWspolrzednychPoziomych:"PL-1992", zrDanych:"Zdj. lotnicze"});
skor_NMT_wg_akt.push({url:"https://x/3_B.asc",godlo:"B", aktualnosc:"2021-04-28",
 format:"ARC/INFO ASCII GRID", ukladWspolrzednychPoziomych:"PL-2000", zrDanych:"Zdj. cyfrowe"});
"""


def test_parse_index_keeps_pl1992_ascii_sheets():
    sheets = parse_index(_INDEX_HTML)

    assert [s.url for s in sheets] == ["https://x/1_A.asc", "https://x/2_A.asc"]
    assert sheets[0] == Sheet("https://x/1_A.asc", "A", laser=True, date="2022-04-27")
    assert not sheets[1].laser


def test_pick_prefers_lidar_over_newer_photogrammetry_one_per_section():
    sheets = [
        Sheet("photo-new", "A", laser=False, date="2025-01-01"),
        Sheet("lidar-old", "A", laser=True, date="2019-01-01"),
        Sheet("lidar-new", "A", laser=True, date="2022-01-01"),
        Sheet("b", "B", laser=False, date="2020-01-01"),
        Sheet("b", "B", laser=False, date="2020-01-01"),
    ]

    assert [s.url for s in pick_sheets(sheets)] == ["lidar-new", "b"]


def test_probe_points_cover_corners_and_are_dense_enough():
    points = probe_points((0, 0, 2500, 300))
    xs = sorted({x for x, _ in points})
    ys = sorted({y for _, y in points})

    assert (0, 0) in points and (2500, 300) in points
    assert max(np.diff(xs)) <= DEM_SHEET_PROBE_STEP_M
    assert ys == [0, 300]


def _sheet(path, data: np.ndarray, left: float, top: float) -> None:
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:2180",
        "transform": Affine(1, 0, left, 0, -1, top),
        "nodata": -9999.0,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype("float32"), 1)


def test_mosaic_averages_to_grid_and_fills_gaps_in_priority_order(tmp_path):
    # Best sheet covers the west half; its first column is nodata (sheet edge).
    west = np.arange(20 * 10, dtype=float).reshape(20, 10)
    west[:, 0] = -9999.0
    _sheet(tmp_path / "west.tif", west, 0, 20)
    # Lower-priority sheet covers everything with a constant.
    _sheet(tmp_path / "all.tif", np.full((20, 20), 5.0), 0, 20)

    dem = mosaic_sheets([tmp_path / "west.tif", tmp_path / "all.tif"], (0, 0, 20, 20), 2)

    assert dem.elevation.shape == (10, 10)
    assert dem.transform == Affine(2, 0, 0, 0, -2, 20)
    # 2×2 block average of the best sheet where it has data.
    assert dem.elevation[0, 1] == np.mean(west[0:2, 2:4])
    # Its nodata pixel is ignored by the average (only the valid neighbours count).
    assert dem.elevation[0, 0] == np.mean(west[0:2, 1])
    # East half comes from the fallback sheet.
    assert np.all(dem.elevation[:, 5:] == 5.0)
    assert not np.isnan(dem.elevation).any()
