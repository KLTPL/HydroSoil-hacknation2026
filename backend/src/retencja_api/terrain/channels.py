"""Ditches and drainage channels detected in the LIDAR terrain model.

A ditch shows up in 1–2 m LIDAR as a narrow line of cells lying clearly below their
surroundings (negative topographic position) that also collects flow from upslope.
Each detected channel is traced downstream along D8 flow directions into a line.
"""

import numpy as np
from rasterio import features
from shapely.geometry import LineString

from retencja_api.terrain.hydrology import d8_receivers, fill_depressions
from retencja_api.terrain.nmt import Dem

RELIEF_WINDOW_M = 20.0  # neighbourhood for local relief
MIN_INCISION_M = 0.25  # channel bottom at least this far below the surroundings
MIN_CATCHMENT_M2 = 2_000.0  # a ditch collects water from at least this area
MIN_CHANNEL_LENGTH_M = 60.0
MAX_CHANNEL_WIDTH_M = 8.0  # wider incisions are depressions or roads, not ditches
MAX_GAP_CELLS = 3  # culverts and noise may interrupt a traced channel


def local_relief(z: np.ndarray, window_cells: int) -> np.ndarray:
    """z minus the NaN-aware mean of a square window (integral-image box filter)."""
    r = window_cells // 2
    valid = np.isfinite(z)
    values = np.where(valid, z, 0.0)

    def box_sum(a: np.ndarray) -> np.ndarray:
        padded = np.pad(a, ((r + 1, r), (r + 1, r)))
        s = padded.cumsum(0).cumsum(1)
        n = 2 * r + 1
        return s[n:, n:] - s[:-n, n:] - s[n:, :-n] + s[:-n, :-n]

    mean = box_sum(values) / np.maximum(box_sum(valid.astype(float)), 1)
    return np.where(valid, z - mean, np.nan)


def flow_accumulation(filled: np.ndarray, receiver: np.ndarray) -> np.ndarray:
    """Number of cells draining through each cell (incl. itself)."""
    flat = np.nan_to_num(filled.ravel(), nan=-np.inf)
    order = np.argsort(-flat, kind="stable").tolist()
    recv = receiver.tolist()
    acc = [1.0] * len(recv)
    for i in order:
        j = recv[i]
        if j != i:
            acc[j] += acc[i]
    return np.array(acc).reshape(filled.shape)


def _trace(start: int, receiver: np.ndarray, member: np.ndarray) -> list[int]:
    """Follow flow downstream from `start` while on the channel (short gaps allowed)."""
    path, gap, current = [start], 0, start
    seen = {start}
    while True:
        nxt = int(receiver[current])
        if nxt == current or nxt in seen:
            break
        seen.add(nxt)
        gap = 0 if member[nxt] else gap + 1
        if gap > MAX_GAP_CELLS:
            break
        path.append(nxt)
        current = nxt
    while path and not member[path[-1]]:
        path.pop()
    return path


def detect_channels(dem: Dem) -> list[LineString]:
    """Channel centre lines in the DEM's CRS, longest first."""
    z = dem.elevation
    res = dem.resolution
    w = z.shape[1]
    relief = local_relief(z, max(3, int(RELIEF_WINDOW_M / res) | 1))
    filled = fill_depressions(z)
    receiver = d8_receivers(filled)
    accumulation = flow_accumulation(filled, receiver) * res**2
    channel = (relief < -MIN_INCISION_M) & (accumulation >= MIN_CATCHMENT_M2)
    if not channel.any():
        return []

    parts = features.shapes(channel.astype(np.uint8), mask=channel, connectivity=8)
    labels = features.rasterize(
        ((geom, k) for k, (geom, _) in enumerate(parts, start=1)), out_shape=z.shape,
        dtype=np.int32,
    )
    member = channel.ravel()
    flat_labels = labels.ravel()
    acc = accumulation.ravel()
    lines = []
    for k in range(1, int(flat_labels.max()) + 1):
        cells = np.flatnonzero(flat_labels == k)
        if cells.size * res < MIN_CHANNEL_LENGTH_M:
            continue
        head = int(cells[np.argmin(acc[cells])])  # most upstream cell of the channel
        path = _trace(head, receiver, member)
        length = (len(path) - 1) * res
        if length < MIN_CHANNEL_LENGTH_M or cells.size * res**2 / length > MAX_CHANNEL_WIDTH_M:
            continue
        rows, cols = np.divmod(np.array(path), w)
        xs, ys = dem.transform @ (cols + 0.5, rows + 0.5)
        lines.append(LineString(np.column_stack([xs, ys])).simplify(res))
    return sorted(lines, key=lambda line: -line.length)
