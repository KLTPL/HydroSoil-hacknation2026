"""Digital terrain model (NMT, LIDAR) from the GUGiK WCS, fetched per area and cached.

The WCS reads full 1 m data server-side, so response time grows with the requested
area (~20–40 s per km²) regardless of output resolution. We therefore request only
the parcel's bounding box (plus a small buffer), resampled server-side to the
analysis resolution, split into strips fetched concurrently.
"""

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
    DEM_STRIP_MAX_M2,
    NMT_COVERAGE_ID,
    NMT_WCS_URL,
)

# Values below this are WCS fill values (outside Poland / missing scans).
_NODATA_BELOW = -1000.0
_NATIVE_RES_M = 1

_Params = list[tuple[str, str]]
Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class Dem:
    elevation: np.ndarray  # float64, NaN where missing; row 0 = north
    transform: Affine  # PL-1992 (EPSG:2180)

    @property
    def resolution(self) -> float:
        return self.transform.a


def snap_bounds(bounds: Bounds, resolution: int) -> tuple[int, int, int, int]:
    minx, miny, maxx, maxy = bounds
    r = resolution
    return (
        math.floor(minx / r) * r,
        math.floor(miny / r) * r,
        math.ceil(maxx / r) * r,
        math.ceil(maxy / r) * r,
    )


def split_strips(bounds: tuple[int, int, int, int], resolution: int) -> list[tuple[int, ...]]:
    """Horizontal strips (north → south) no larger than DEM_STRIP_MAX_M2 each."""
    minx, miny, maxx, maxy = bounds
    width, height = maxx - minx, maxy - miny
    count = max(1, math.ceil(width * height / DEM_STRIP_MAX_M2))
    step = math.ceil(height / count / resolution) * resolution
    strips = []
    top = maxy
    while top > miny:
        bottom = max(miny, top - step)
        strips.append((minx, bottom, maxx, top))
        top = bottom
    return strips


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: _Params | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """GUGiK drops connections and returns 5xx under load; back off and retry those."""
    for attempt in range(1, DEM_FETCH_ATTEMPTS + 1):
        try:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code < 500:
                response.raise_for_status()
                return response
            error: Exception = httpx.HTTPStatusError(
                f"GUGiK {response.status_code} for {url}",
                request=response.request,
                response=response,
            )
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            error = exc
        if attempt == DEM_FETCH_ATTEMPTS:
            raise error
        await asyncio.sleep(2**attempt)
    raise AssertionError("unreachable")


async def _fetch_strip(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, strip: tuple[int, ...], resolution: int
) -> bytes:
    minx, miny, maxx, maxy = strip
    path = cache_path("nmt-strip", f"{minx}_{miny}_{maxx}_{maxy}@{resolution}", ".tif")
    if path.exists():
        return path.read_bytes()
    params = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", NMT_COVERAGE_ID),
        ("FORMAT", "image/tiff"),
        # Server axis "x" = easting, "y" = northing (verified against a known summit).
        ("SUBSET", f"x({minx},{maxx})"),
        ("SUBSET", f"y({miny},{maxy})"),
        ("SCALEFACTOR", str(_NATIVE_RES_M / resolution)),
    ]
    async with sem:
        response = await get_with_retry(client, NMT_WCS_URL, params)
    if not response.content.startswith((b"II*\x00", b"MM\x00*")):
        raise RuntimeError(f"NMT WCS returned non-TIFF for {strip}: {response.text[:200]}")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(response.content)
    tmp.replace(path)
    return response.content


def _mosaic(strips: list[bytes], bounds: tuple[int, int, int, int], resolution: int) -> Dem:
    minx, miny, maxx, maxy = bounds
    shape = ((maxy - miny) // resolution, (maxx - minx) // resolution)
    out = np.full(shape, np.nan)
    for content in strips:
        with rasterio.MemoryFile(content) as memfile, memfile.open() as src:
            data = src.read(1).astype(np.float64)
            # Place by the strip's own georeference; the server may round edges by a cell.
            row = round((maxy - src.bounds.top) / resolution)
            col = round((src.bounds.left - minx) / resolution)
        rows = slice(max(row, 0), min(row + data.shape[0], shape[0]))
        cols = slice(max(col, 0), min(col + data.shape[1], shape[1]))
        out[rows, cols] = data[
            rows.start - row : rows.stop - row, cols.start - col : cols.stop - col
        ]
    out[out < _NODATA_BELOW] = np.nan
    return Dem(out, Affine(resolution, 0, minx, 0, -resolution, maxy))


async def load_dem(bounds: Bounds, resolution: int) -> Dem:
    """DEM covering `bounds` (PL-1992) at `resolution` metres."""
    snapped = snap_bounds(bounds, resolution)
    strips = split_strips(snapped, resolution)
    sem = asyncio.Semaphore(DEM_FETCH_CONCURRENCY)
    async with httpx.AsyncClient(timeout=DEM_FETCH_TIMEOUT_S) as client:
        contents = await asyncio.gather(*(_fetch_strip(client, sem, s, resolution) for s in strips))
    return await asyncio.to_thread(_mosaic, list(contents), snapped, resolution)
