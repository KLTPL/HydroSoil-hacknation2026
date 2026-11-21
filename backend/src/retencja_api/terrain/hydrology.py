"""Grid hydrology: depression filling and D8 flow routing.

Depressions are filled with the epsilon priority-flood algorithm (Barnes et al. 2014),
which also leaves a strictly drainable surface for flow routing. NaN cells and the
grid edge act as outlets.
"""

import heapq
import math

import numpy as np

# Vertical increment on filled flats (m); keeps every cell drainable, negligible vs. depths.
FLAT_EPSILON = 1e-5


def _neighbour_offsets(width: int) -> list[int]:
    return [-width - 1, -width, -width + 1, -1, 1, width - 1, width, width + 1]


def fill_depressions(z: np.ndarray) -> np.ndarray:
    """Return the DEM with every depression raised to its spill level (+ epsilon slope)."""
    padded = np.pad(z.astype(np.float64), 1, constant_values=np.nan)
    h, w = padded.shape
    flat = padded.ravel()
    filled = flat.copy()
    closed = np.isnan(flat)

    # Seeds: valid cells touching NaN (padding included) — water leaves the grid there.
    nan_adjacent = np.zeros_like(closed)
    for offset in _neighbour_offsets(w):
        nan_adjacent |= np.roll(closed, -offset)
    seeds = np.flatnonzero(~closed & nan_adjacent)

    heap = [(flat[i], int(i)) for i in seeds]
    heapq.heapify(heap)
    closed[seeds] = True

    closed_list = closed.tolist()
    z_list = flat.tolist()
    filled_list = filled.tolist()
    offsets = _neighbour_offsets(w)
    while heap:
        level, idx = heapq.heappop(heap)
        for off in offsets:
            n = idx + off
            if closed_list[n]:
                continue
            closed_list[n] = True
            elevation = z_list[n]
            if elevation <= level:
                elevation = level + FLAT_EPSILON
            filled_list[n] = elevation
            heapq.heappush(heap, (elevation, n))

    out = np.array(filled_list).reshape(h, w)
    return out[1:-1, 1:-1]


def d8_receivers(surface: np.ndarray) -> np.ndarray:
    """Flat index of each cell's steepest-descent neighbour; self for outlets/pits/NaN."""
    h, w = surface.shape
    padded = np.pad(surface, 1, constant_values=np.nan)
    rows, cols = np.mgrid[0:h, 0:w]
    best_slope = np.zeros((h, w))
    receiver = (rows * w + cols).ravel().reshape(h, w)

    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            neighbour = padded[1 + dr : 1 + dr + h, 1 + dc : 1 + dc + w]
            slope = (surface - neighbour) / math.hypot(dr, dc)
            better = slope > best_slope  # False for NaN on either side
            best_slope = np.where(better, slope, best_slope)
            target = (rows + dr) * w + (cols + dc)
            receiver = np.where(better, target, receiver)
    return receiver.ravel()


def terminal_cells(receiver: np.ndarray, stop: np.ndarray) -> np.ndarray:
    """For each cell, the first `stop` cell (or outlet) on its downstream path.

    Uses pointer jumping: O(n log path_length) instead of walking every path.
    """
    r = np.where(stop.ravel(), np.arange(receiver.size), receiver)
    while True:
        nxt = r[r]
        if np.array_equal(nxt, r):
            return r
        r = nxt
