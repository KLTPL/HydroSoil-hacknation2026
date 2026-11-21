import numpy as np
from affine import Affine
from shapely.geometry import LineString, box

from retencja_api.terrain.ditches import (
    MIN_SPACING_M,
    WEIR_HEAD_M,
    plan_ditch,
    plan_ditches,
)
from retencja_api.terrain.nmt import Dem


def _sloped_dem(slope: float) -> Dem:
    """1000 × 200 m, 2 m cells, rising eastwards by `slope` m/m; origin (0, 200)."""
    cols = np.arange(500) * 2.0 + 1.0
    elevation = np.tile(100 + slope * cols, (100, 1))
    return Dem(elevation, Affine(2, 0, 0, 0, -2, 200))


def test_weir_count_follows_ditch_gradient():
    line = LineString([(10, 100), (990, 100)])
    steep = plan_ditch(line, "ditch", _sloped_dem(0.005))
    assert steep is not None
    spacing = WEIR_HEAD_M / 0.005  # 100 m of backwater per weir
    assert abs(steep.slope - 0.005) < 1e-4
    assert len(steep.weirs) == int(np.ceil(980 / spacing))
    # First weir sits at the downstream (western, lower) end.
    assert steep.weirs[0].x < 20

    flat = plan_ditch(line, "ditch", _sloped_dem(0.0))
    assert flat is not None
    assert len(flat.weirs) == 1  # one weir holds the whole flat stretch
    assert flat.soil_m3[0] < flat.soil_m3[1]


def test_upstream_drawn_line_still_starts_downstream():
    line = LineString([(990, 100), (10, 100)])
    plan = plan_ditch(line, "ditch", _sloped_dem(0.002))
    assert plan is not None
    assert plan.weirs[0].x < 20


def test_short_ditches_and_far_ditches_are_ignored(monkeypatch):
    monkeypatch.setattr(
        "retencja_api.terrain.ditches.lonlat_to_metric", lambda lon, lat: (lon, lat)
    )
    dem = _sloped_dem(0.003)
    parcel = box(100, 50, 600, 150)
    ways = [
        {"kind": "ditch", "coords": [(0, 100), (900, 100)]},  # crosses the parcel
        {"kind": "ditch", "coords": [(300, 190), (900, 190)]},  # 40 m away
        {"kind": "drain", "coords": [(200, 100), (230, 100)]},  # too short
    ]
    plans = plan_ditches(ways, parcel, dem)
    assert len(plans) == 1
    assert plans[0].length_m > 500
    assert MIN_SPACING_M <= plans[0].length_m
