import numpy as np
from affine import Affine
from shapely.geometry import Polygon, box

from retencja_api.assessment.parcel_shape import parcel_shape
from retencja_api.terrain.nmt import Dem
from retencja_api.terrain.slope import slope_stats

RES = 2.0
X0, Y0 = 500_000.0, 400_000.0


def test_square_is_compact_not_a_strip():
    s = parcel_shape(box(0, 0, 200, 200))
    assert not s.narrow_strip and not s.winding
    assert s.width_m == s.length_m == 200
    assert abs(s.compactness - np.pi / 4) < 0.01


def test_straight_strip_running_north_south():
    s = parcel_shape(box(0, 0, 15, 400))
    assert s.narrow_strip and not s.winding
    assert abs(s.width_m - 15) < 1 and abs(s.length_m - 400) < 10
    assert s.axis_azimuth_deg in (0, 179)


def test_bent_strip_keeps_its_width_and_is_winding():
    # 15 m wide L: 300 m east, then 300 m north.
    bent = Polygon([(0, 0), (315, 0), (315, 300), (300, 300), (300, 15), (0, 15)])
    s = parcel_shape(bent)
    assert s.narrow_strip and s.winding
    assert abs(s.width_m - 15) < 2
    assert s.box_width_m > 100


def _dem(z: np.ndarray) -> Dem:
    return Dem(elevation=z, transform=Affine(RES, 0, X0, 0, -RES, Y0))


def test_plane_falling_east():
    _rows, cols = np.mgrid[0:100, 0:100]
    z = 100.0 - cols * RES * 0.05  # 5 % towards the east
    parcel = box(X0 + 40, Y0 - 160, X0 + 160, Y0 - 40)  # 120 m square in the middle
    s = slope_stats(_dem(z), parcel)
    assert abs(s.mean_pct - 5) < 0.2
    assert s.fall_azimuth_deg == 90
    assert s.steep_share == 0
    assert 100 <= s.outflow_edge_m <= 140  # the eastern (lower) edge
    assert s.runon_area_ha > 0  # the strip west of the parcel drains onto it


def test_steep_slope_and_parcel_lower_than_surroundings():
    rows, _cols = np.mgrid[0:100, 0:100]
    z = 100.0 + rows * RES * 0.15  # 15 % falling north
    z[40:60, 40:60] -= 2  # parcel cells sunk by 2 m
    parcel = box(X0 + 80, Y0 - 120, X0 + 120, Y0 - 80)
    s = slope_stats(_dem(z), parcel)
    assert s.steep_share > 0.8
    assert s.fall_azimuth_deg == 0
    assert s.relative_height_m < -1


def test_parcel_outside_the_dem_gives_none():
    z = np.full((10, 10), np.nan)
    assert slope_stats(_dem(z), box(X0, Y0 - 20, X0 + 20, Y0)) is None
