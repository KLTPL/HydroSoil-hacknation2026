import struct
import zlib

import numpy as np
from affine import Affine

from retencja_api.terrain.flow import encode_png, flow_lines, relief_rgba
from retencja_api.terrain.nmt import Dem

RES = 2.0


def _dem(z: np.ndarray) -> Dem:
    return Dem(elevation=z, transform=Affine(RES, 0, 500_000, 0, -RES, 400_000))


def _valley(n: int = 80) -> np.ndarray:
    """Slope falling east with a V-shaped valley along the middle row."""
    rows, cols = np.mgrid[0:n, 0:n]
    return 100.0 - cols * 0.05 + np.abs(rows - n // 2) * 0.1


def test_runoff_follows_the_valley_and_leaves_the_area():
    lines = flow_lines(_dem(_valley()))

    assert lines, "a valley collecting 80 cells x 2 m must carry visible runoff"
    main = max(lines, key=lambda f: f.area_m2)
    assert main.end == "exit"
    xs = [x for x, _ in main.line.coords]
    assert xs == sorted(xs), "flow runs downhill, eastward"


def test_runoff_into_a_depression_pools_there():
    z = _valley()
    z[38:43, 50:56] -= 1.0  # pit in the valley floor

    ends = {f.end for f in flow_lines(_dem(z))}

    assert "pool" in ends


def test_confluences_split_segments_and_link_downstream():
    lines = flow_lines(_dem(_valley()))

    for f in lines:
        if f.end == "join":
            assert f.next_index is not None
            downstream = lines[f.next_index]
            assert downstream.line.coords[0] == f.line.coords[-1]


def test_relief_png_is_a_valid_rgba_image():
    z = _valley(40)
    z[5, 5] = np.nan

    rgba, spread = relief_rgba(_dem(z))
    png = encode_png(rgba)

    assert rgba.shape == (40, 40, 4)
    assert rgba[5, 5, 3] == 0 and rgba[10, 10, 3] == 255
    assert spread > 0
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (40, 40)
    idat_len = struct.unpack(">I", png[33:37])[0]
    raw = zlib.decompress(png[41 : 41 + idat_len])
    assert len(raw) == 40 * (1 + 40 * 4)
