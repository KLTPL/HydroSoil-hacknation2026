"""What the farmer sees of the LIDAR terrain: where rain runs off, and the micro-relief.

Flow lines follow D8 steepest descent on the depression-filled surface and stop where
water enters a depression (it pools there) or leaves the analysed area. The network is
split at confluences, so each segment carries one upstream area (line width on the map).
"""

import struct
import zlib
from dataclasses import dataclass
from typing import Literal

import numpy as np
from shapely.geometry import LineString

from retencja_api.terrain.channels import flow_accumulation, local_relief
from retencja_api.terrain.hydrology import d8_receivers, fill_depressions
from retencja_api.terrain.nmt import Dem

MIN_FLOW_AREA_M2 = 800.0  # a cell draining at least this area carries visible runoff
MAX_FLOW_LINES = 600  # largest segments kept (map payload)
POOL_DEPTH_M = 0.1  # filled deeper than this = water pools; shallower pits are LIDAR noise
RELIEF_WINDOW_M = 80.0  # detrending window: shows hollows and ridges, not the regional slope

FlowEnd = Literal["pool", "exit", "join"]


@dataclass(frozen=True)
class FlowLine:
    line: LineString  # PL-1992, downstream direction
    area_m2: float  # upstream area draining through the segment's last cell
    end: FlowEnd
    next_index: int | None  # segment continuing downstream of a confluence


def flow_lines(dem: Dem) -> list[FlowLine]:
    z = dem.elevation
    h, w = z.shape
    res = dem.resolution
    valid = np.isfinite(z)
    filled = fill_depressions(z)
    receiver = d8_receivers(filled)
    area = (flow_accumulation(filled, receiver) * res**2).ravel()
    pool = (valid & (filled - z > POOL_DEPTH_M)).ravel()
    stream = valid.ravel() & ~pool & (area >= MIN_FLOW_AREA_M2)

    cells = np.flatnonzero(stream)
    targets = receiver[cells]
    feeds_stream = (targets != cells) & stream[targets]
    donors = np.bincount(targets[feeds_stream], minlength=h * w)
    # Segments start at sources (no stream above) and at confluences (2+ streams meet).
    heads = cells[(donors[cells] == 0) | (donors[cells] >= 2)]
    head_index = {int(c): i for i, c in enumerate(heads)}

    raw: list[tuple[list[int], FlowEnd, int | None]] = []
    for head in heads.tolist():
        path, current = [head], head
        end: FlowEnd = "exit"
        nxt_seg = None
        while True:
            nxt = int(receiver[current])
            if nxt == current:
                break
            if pool[nxt]:
                path.append(nxt)
                end = "pool"
                break
            if nxt in head_index:
                path.append(nxt)
                end, nxt_seg = "join", head_index[nxt]
                break
            if not stream[nxt]:
                break
            path.append(nxt)
            current = nxt
        raw.append((path, end, nxt_seg))

    order = sorted(
        (i for i, (path, _, _) in enumerate(raw) if len(path) >= 2),
        key=lambda i: -area[raw[i][0][-2]],
    )[:MAX_FLOW_LINES]
    renumber = {old: new for new, old in enumerate(order)}
    out = []
    for i in order:
        path, end, nxt_seg = raw[i]
        rows, cols = np.divmod(np.array(path), w)
        xs, ys = dem.transform @ (cols + 0.5, rows + 0.5)
        line = LineString(np.column_stack([xs, ys])).simplify(res * 0.75)
        kept_next = renumber.get(nxt_seg) if nxt_seg is not None else None
        out.append(
            FlowLine(
                line=line,
                area_m2=float(area[path[-2]]),
                end=end if end != "join" or kept_next is not None else "exit",
                next_index=kept_next,
            )
        )
    return out


# Hollows (water collects) in water blue; higher ground stays clear over the hillshade base map.
HOLLOW_RGB = (24, 96, 200)
HOLLOW_MAX_ALPHA = 190
EDGE_FEATHER_M = 60.0  # the image fades out towards its edges, so no rectangle shows


def _edge_fade(shape: tuple[int, int], res: float) -> np.ndarray:
    """1 inside, falling smoothly to 0 at the image border over EDGE_FEATHER_M."""
    h, w = shape
    cells = max(1.0, EDGE_FEATHER_M / res)
    rows = np.minimum(np.arange(h), np.arange(h)[::-1]) + 0.5
    cols = np.minimum(np.arange(w), np.arange(w)[::-1]) + 0.5
    dist = np.minimum.outer(rows, cols) / cells
    t = np.clip(dist, 0, 1)
    return t * t * (3 - 2 * t)


def relief_rgba(dem: Dem) -> tuple[np.ndarray, float]:
    """Translucent overlay of hollows (below their surroundings); returns RGBA and the
    depth (m) at which the tint is fully saturated."""
    z = dem.elevation
    valid = np.isfinite(z)
    relief = np.nan_to_num(local_relief(z, max(3, int(RELIEF_WINDOW_M / dem.resolution) | 1)))
    spread = float(np.nanpercentile(np.abs(relief), 97)) or 0.1
    depth = np.clip(-relief / spread, 0, 1) ** 0.8
    alpha = HOLLOW_MAX_ALPHA * depth * _edge_fade(z.shape, dem.resolution) * valid
    rgb = np.broadcast_to(np.array(HOLLOW_RGB, dtype=float), (*z.shape, 3))
    rgba = np.concatenate([rgb, alpha[..., None]], axis=2).round().astype(np.uint8)
    return rgba, spread


def encode_png(rgba: np.ndarray) -> bytes:
    """Minimal RGBA PNG encoder (no imaging library needed)."""
    h, w, _ = rgba.shape
    rows = np.concatenate([np.zeros((h, 1), np.uint8), rgba.reshape(h, w * 4)], axis=1)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows.tobytes(), 6))
        + chunk(b"IEND", b"")
    )
