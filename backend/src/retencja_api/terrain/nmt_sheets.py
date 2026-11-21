"""NMT from GUGiK's pre-cut 1 m sheets (opendata.geoportal.gov.pl), the fast DEM source.

The WCS computes every request on the fly and slows to minutes under load. The sheets
are static ARC/INFO ASCII files, so their download time depends only on bandwidth; the
server throttles each connection, so a sheet is fetched as parallel byte ranges. The
sheet index (WMS GetFeatureInfo) lists every sheet at a point with survey method and date.
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import rasterio
from affine import Affine
from rasterio.warp import Resampling, reproject

from retencja_api.cache import cache_path
from retencja_api.config import (
    DEM_SHEET_CHUNK_BYTES,
    DEM_SHEET_CONCURRENCY,
    DEM_SHEET_PROBE_STEP_M,
    DEM_SHEET_TIMEOUT_S,
    NMT_SHEET_INDEX_URL,
    NMT_SHEET_LAYERS,
)
from retencja_api.terrain.nmt import Bounds, Dem, get_with_retry, snap_bounds

_CRS = "EPSG:2180"
_ENTRY = re.compile(r"push\(\{(.*?)\}\);", re.S)
_FIELD = re.compile(r'(\w+):"([^"]*)"')
_CONTENT_RANGE = re.compile(r"bytes \d+-\d+/(\d+)")


class NoSheets(RuntimeError):
    """The index lists no usable sheet for the area."""


@dataclass(frozen=True)
class Sheet:
    url: str
    godlo: str
    laser: bool
    date: str  # ISO date of the survey

    @property
    def priority(self) -> tuple[bool, str]:
        # LIDAR (0.15 m height error) beats newer photogrammetry (0.5 m); then newest.
        return (self.laser, self.date)


def parse_index(html: str) -> list[Sheet]:
    """Sheets in a GetFeatureInfo HTML answer: PL-1992 ASCII grids only."""
    sheets = []
    for entry in _ENTRY.findall(html):
        fields = dict(_FIELD.findall(entry))
        if (
            fields.get("ukladWspolrzednychPoziomych") == "PL-1992"
            and fields.get("format") == "ARC/INFO ASCII GRID"
            and fields.get("url", "").endswith(".asc")
        ):
            sheets.append(
                Sheet(
                    url=fields["url"],
                    godlo=fields.get("godlo", fields["url"]),
                    laser=fields.get("zrDanych") == "Skaning laserowy",
                    date=fields.get("aktualnosc", ""),
                )
            )
    return sheets


def pick_sheets(sheets: list[Sheet]) -> list[Sheet]:
    """The best sheet per map section, best first (the mosaic fills gaps in that order)."""
    best: dict[str, Sheet] = {}
    for sheet in sheets:
        if sheet.godlo not in best or sheet.priority > best[sheet.godlo].priority:
            best[sheet.godlo] = sheet
    return sorted(best.values(), key=lambda s: s.priority, reverse=True)


def probe_points(bounds: Bounds) -> list[tuple[float, float]]:
    """Grid over `bounds`, edges included, dense enough to touch every sheet."""
    minx, miny, maxx, maxy = bounds
    nx = max(1, int(np.ceil((maxx - minx) / DEM_SHEET_PROBE_STEP_M)))
    ny = max(1, int(np.ceil((maxy - miny) / DEM_SHEET_PROBE_STEP_M)))
    return [
        (x, y) for x in np.linspace(minx, maxx, nx + 1) for y in np.linspace(miny, maxy, ny + 1)
    ]


async def _sheets_at(client: httpx.AsyncClient, x: float, y: float) -> list[Sheet]:
    layers = ",".join(NMT_SHEET_LAYERS)
    params = [
        ("SERVICE", "WMS"),
        ("VERSION", "1.3.0"),
        ("REQUEST", "GetFeatureInfo"),
        ("LAYERS", layers),
        ("QUERY_LAYERS", layers),
        ("CRS", _CRS),
        # WMS 1.3.0 uses the EPSG axis order of PL-1992: northing first.
        ("BBOX", f"{y - 10},{x - 10},{y + 10},{x + 10}"),
        ("WIDTH", "21"),
        ("HEIGHT", "21"),
        ("I", "10"),
        ("J", "10"),
        ("INFO_FORMAT", "text/html"),
        ("FEATURE_COUNT", "50"),
    ]
    response = await get_with_retry(client, NMT_SHEET_INDEX_URL, params)
    return parse_index(response.text)


async def _chunk(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str, start: int, end: int
) -> httpx.Response:
    async with sem:
        response = await get_with_retry(client, url, headers={"Range": f"bytes={start}-{end}"})
    return response


async def _download(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> bytes:
    first = await _chunk(client, sem, url, 0, DEM_SHEET_CHUNK_BYTES - 1)
    if first.status_code == 200:  # server ignored the range: this is the whole file
        return first.content
    match = _CONTENT_RANGE.fullmatch(first.headers.get("content-range", ""))
    if first.status_code != 206 or match is None:
        raise RuntimeError(f"Unexpected range answer for {url}: {first.status_code}")
    total = int(match.group(1))
    starts = range(DEM_SHEET_CHUNK_BYTES, total, DEM_SHEET_CHUNK_BYTES)
    rest = await asyncio.gather(
        *(_chunk(client, sem, url, s, min(s + DEM_SHEET_CHUNK_BYTES, total) - 1) for s in starts)
    )
    content = first.content + b"".join(r.content for r in rest)
    if len(content) != total:
        raise RuntimeError(f"Incomplete sheet {url}: {len(content)} of {total} bytes")
    return content


def _store(content: bytes, path: Path) -> None:
    """Keep the sheet as a compressed GeoTIFF (~4× smaller than the .asc, faster to read)."""
    with rasterio.MemoryFile(content, ext=".asc") as mem, mem.open() as src:
        data = src.read(1)
        profile = {
            "driver": "GTiff",
            "height": src.height,
            "width": src.width,
            "count": 1,
            "dtype": "float32",
            "crs": _CRS,
            "transform": src.transform,
            "nodata": src.nodata,
            "compress": "deflate",
            "predictor": 3,
            "tiled": True,
        }
    tmp = path.with_suffix(".part")
    with rasterio.open(tmp, "w", **profile) as dst:
        dst.write(data.astype(np.float32), 1)
    tmp.replace(path)


# One download per sheet even when neighbouring parcels need it at the same time.
_in_flight: dict[str, asyncio.Task[Path]] = {}


async def _sheet_file(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> Path:
    path = cache_path("nmt-sheet", url, ".tif")
    if path.exists():
        return path

    async def fetch() -> Path:
        content = await _download(client, sem, url)
        await asyncio.to_thread(_store, content, path)
        return path

    task = _in_flight.get(url)
    if task is None:
        task = asyncio.ensure_future(fetch())
        _in_flight[url] = task
        task.add_done_callback(lambda _: _in_flight.pop(url, None))
    return await task


def mosaic_sheets(paths: list[Path], bounds: tuple[int, int, int, int], resolution: int) -> Dem:
    """Average the 1 m sheets onto the analysis grid; earlier sheets win where they overlap."""
    minx, miny, maxx, maxy = bounds
    shape = ((maxy - miny) // resolution, (maxx - minx) // resolution)
    transform = Affine(resolution, 0, minx, 0, -resolution, maxy)
    out = np.full(shape, np.nan)
    for path in paths:
        layer = np.full(shape, np.nan)
        with rasterio.open(path) as src:
            reproject(
                rasterio.band(src, 1),
                layer,
                dst_transform=transform,
                dst_crs=_CRS,
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
        gaps = np.isnan(out)
        out[gaps] = layer[gaps]
    return Dem(out, transform)


async def load_sheet_dem(bounds: Bounds, resolution: int) -> Dem:
    """DEM covering `bounds` (PL-1992) at `resolution` metres from the NMT sheets."""
    snapped = snap_bounds(bounds, resolution)
    sem = asyncio.Semaphore(DEM_SHEET_CONCURRENCY)
    async with httpx.AsyncClient(timeout=DEM_SHEET_TIMEOUT_S) as client:
        found = await asyncio.gather(*(_sheets_at(client, x, y) for x, y in probe_points(snapped)))
        sheets = pick_sheets([s for at_point in found for s in at_point])
        if not sheets:
            raise NoSheets(f"No NMT sheet listed for {snapped}")
        paths = await asyncio.gather(*(_sheet_file(client, sem, s.url) for s in sheets))
    return await asyncio.to_thread(mosaic_sheets, list(paths), snapped, resolution)
