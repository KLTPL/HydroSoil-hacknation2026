import math

import numpy as np
from rasterio.transform import from_origin

from retencja_api.geo import lonlat_to_metric
from retencja_api.terrain.elevation import (
    Elevation,
    relative_heights,
    sample,
    terrarium,
)
from retencja_api.terrain.nmt import Dem


def _decode(rgba: np.ndarray) -> np.ndarray:
    r, g, b = (rgba[..., i].astype(float) for i in range(3))
    return r * 256 + g + b / 256 - 32768


def test_terrarium_round_trips_to_a_few_millimetres():
    heights = np.array([[-3.217, 0.0, 0.004, 12.5]])
    assert np.allclose(_decode(terrarium(heights)), heights, atol=1 / 256)


def test_heights_are_relative_and_fade_to_zero_at_the_edge():
    z = np.full((200, 200), 100.0)
    z[90:110, 90:110] = 98.0  # a hollow in the middle
    heights = relative_heights(Dem(elevation=z, transform=from_origin(500_000, 400_000, 2, 2)))
    assert heights[100, 100] == -2.0  # the centre is far from the edge
    assert heights[0, 0] == 0 and heights[-1, -1] == 0
    assert heights[50, 50] == 0  # median ground


def test_sample_reads_the_grid_and_is_flat_outside():
    lon, lat = 18.3, 52.6
    x, y = lonlat_to_metric(lon, lat)
    grid = np.arange(100, dtype=np.float32).reshape(10, 10)
    # Grid centred on the point, 2 m cells
    elevation = Elevation(heights=grid, transform=from_origin(x - 10, y + 10, 2, 2))
    inside = sample(elevation, np.array([lon]), np.array([lat]))
    assert math.isclose(inside[0], grid[4:6, 4:6].mean(), abs_tol=0.5)
    outside = sample(elevation, np.array([lon + 0.01]), np.array([lat]))
    assert outside[0] == 0
