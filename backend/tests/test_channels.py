import numpy as np
from affine import Affine

from retencja_api.terrain.channels import detect_channels, local_relief
from retencja_api.terrain.nmt import Dem


def _field_with_ditch() -> Dem:
    """400 × 200 m field sloping south, cut by a 0.8 m deep east–west ditch."""
    rows, cols = np.mgrid[0:100, 0:200]
    z = 100 + 0.01 * (100 - rows) * 2 + 0.002 * cols * 2  # gentle slope to the south-west
    z[50:52, :] -= 0.8
    return Dem(z.astype(float), Affine(2, 0, 0, 0, -2, 200))


def test_local_relief_marks_incision():
    dem = _field_with_ditch()
    relief = local_relief(dem.elevation, 11)
    assert relief[50, 100] < -0.5
    assert abs(relief[20, 100]) < 0.1


def test_detects_ditch_as_one_long_line():
    lines = detect_channels(_field_with_ditch())
    assert lines, "ditch not detected"
    ditch = lines[0]
    assert ditch.length > 250
    ys = [y for _, y in ditch.coords]
    assert all(95 <= y <= 103 for y in ys)  # rows 50–51 → y ≈ 97–99


def test_flat_field_has_no_channels():
    z = np.full((100, 100), 50.0) + np.random.default_rng(1).normal(0, 0.03, (100, 100))
    assert detect_channels(Dem(z, Affine(2, 0, 0, 0, -2, 200))) == []
