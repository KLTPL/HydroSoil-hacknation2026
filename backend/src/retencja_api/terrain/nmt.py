"""Digital terrain model (NMT, 1 m LIDAR) from the GUGiK WCS, cached as aligned tiles."""

import asyncio
import math
from dataclasses import dataclass

import httpx
import numpy as np
import rasterio
from affine import Affine

from retencja_api.cache import cache_path
from retencja_api.config import (
    DEM_FETCH_ATTEMPTS,
    DEM_FETCH_CONCURRENCY,
    DEM_FETCH_TIMEOUT_S,
    DEM_TILE_SIZE_M,
    NMT_COVERAGE_ID,
    NMT_WCS_URL,
)

# Values below this are WCS fill values (outside Poland / missing scans).
_NODATA_BELOW = -1000.0
_NATIVE_RES_M = 1

_Params = list[tuple[str, str]]


@dataclass(frozen=True)
class Dem:
    elevation: np.ndarray  # float64, NaN where missing; row 0 = north
    transform: Affine  # PL-1992 (EPSG:2180)

    @property
    def resolution(self) -> float:
        return self.transform.a


def tiles_for_bbox(minx: float, miny: float, maxx: float, maxy: float) -> list[tuple[int, int]]:
    """Lower-left corners (easting, northing) of grid tiles covering the bbox."""
    t = DEM_TILE_SIZE_M
    xs = range(math.floor(minx / t) * t, math.ceil(maxx / t) * t, t)
    ys = range(math.floor(miny / t) * t, math.ceil(maxy / t) * t, t)
    return [(x, y) for x in xs for y in ys]


def _tile_path(x: int, y: int):
    return cache_path("nmt", f"{x}_{y}_{DEM_TILE_SIZE_M}", ".tif")


async def _get_with_retry(client: httpx.AsyncClient, params: _Params) -> httpx.Response:
    """The WCS drops connections and returns 5xx under load; back off and retry those."""
    for attempt in range(1, DEM_FETCH_ATTEMPTS + 1):
        try:
            response = await client.get(NMT_WCS_URL, params=params)
            if response.status_code < 500:
                response.raise_for_status()
                return response
            error: Exception = httpx.HTTPStatusError(
                f"NMT WCS {response.status_code}", request=response.request, response=response
            )
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            error = exc
        if attempt == DEM_FETCH_ATTEMPTS:
            raise error
        await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")


async def _fetch_tile(client: httpx.AsyncClient, sem: asyncio.Semaphore, x: int, y: int) -> None:
    path = _tile_path(x, y)
    if path.exists():
        return
    t = DEM_TILE_SIZE_M
    params = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", NMT_COVERAGE_ID),
        ("FORMAT", "image/tiff"),
        # Server axis "x" = easting, "y" = northing (verified against known summit).
        ("SUBSET", f"x({x},{x + t})"),
        ("SUBSET", f"y({y},{y + t})"),
    ]
    async with sem:
        response = await _get_with_retry(client, params)
    if not response.content.startswith((b"II*\x00", b"MM\x00*")):
        raise RuntimeError(f"NMT WCS returned non-TIFF for tile {x},{y}: {response.text[:200]}")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(response.content)
    tmp.replace(path)


async def ensure_tiles(tiles: list[tuple[int, int]]) -> None:
    sem = asyncio.Semaphore(DEM_FETCH_CONCURRENCY)
    async with httpx.AsyncClient(timeout=DEM_FETCH_TIMEOUT_S) as client:
        await asyncio.gather(*(_fetch_tile(client, sem, x, y) for x, y in tiles))


def _mosaic(tiles: list[tuple[int, int]]) -> tuple[np.ndarray, float, float]:
    t = DEM_TILE_SIZE_M
    x0 = min(x for x, _ in tiles)
    y1 = max(y for _, y in tiles) + t
    width = max(x for x, _ in tiles) + t - x0
    height = y1 - min(y for _, y in tiles)
    out = np.full((height, width), np.nan)
    for x, y in tiles:
        with rasterio.open(_tile_path(x, y)) as src:
            if src.res != (_NATIVE_RES_M, _NATIVE_RES_M):
                raise RuntimeError(f"Unexpected NMT resolution {src.res}")
            data = src.read(1).astype(np.float64)
            left, top = src.bounds.left, src.bounds.top
        row, col = round(y1 - top), round(left - x0)
        out[row : row + data.shape[0], col : col + data.shape[1]] = data
    out[out < _NODATA_BELOW] = np.nan
    return out, float(x0), float(y1)


def _block_mean(a: np.ndarray, factor: int) -> np.ndarray:
    if factor == 1:
        return a
    h, w = a.shape[0] // factor, a.shape[1] // factor
    blocks = a[: h * factor, : w * factor].reshape(h, factor, w, factor)
    return blocks.mean(axis=(1, 3))  # NaN propagates: partial-coverage cells stay missing


async def load_dem(bounds: tuple[float, float, float, float], resolution_m: int) -> Dem:
    """DEM covering `bounds` (PL-1992), snapped outward to the tile grid."""
    if DEM_TILE_SIZE_M % resolution_m:
        raise ValueError("Tile size must be a multiple of the analysis resolution")
    tiles = tiles_for_bbox(*bounds)
    await ensure_tiles(tiles)
    native, x0, y1 = await asyncio.to_thread(_mosaic, tiles)
    elevation = _block_mean(native, resolution_m // _NATIVE_RES_M)
    return Dem(elevation, Affine(resolution_m, 0, x0, 0, -resolution_m, y1))
