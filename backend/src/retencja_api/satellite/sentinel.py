"""Vegetation and canopy-moisture state of the parcel from Sentinel-2 L2A
(Microsoft Planetary Computer: STAC search + Cloud-Optimized GeoTIFF window reads).

NDVI = (B08 − B04) / (B08 + B04) — vegetation vigour.
NDMI = (B08 − B11) / (B08 + B11) — water content of the canopy.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a"
COLLECTION = "sentinel-2-l2a"
WINDOW_DAYS = 20  # look this far back from the analysis date for a clear scene
MAX_SCENE_CLOUD_PCT = 70
MIN_CLEAR_PCT = 60  # share of the parcel that must be cloud-free
CANDIDATES_PER_YEAR = 3
_CLEAR_SCL = (4, 5, 6)  # vegetation, bare soil, water
READ_CONCURRENCY = 6
_GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MAX_RETRY": "2",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "GDAL_HTTP_TIMEOUT": "10",
    "GDAL_HTTP_CONNECTTIMEOUT": "5",
}


@dataclass(frozen=True)
class Scene:
    id: str
    day: date
    cloud_pct: float
    hrefs: dict[str, str]
    offset: float  # processing baseline ≥ 04.00 adds +1000 to reflectances
    epsg: int


@dataclass(frozen=True)
class SceneIndices:
    day: date
    ndvi: float
    ndmi: float
    clear_pct: float


async def search_scenes(
    client: httpx.AsyncClient, geometry_wgs84: dict, start: date, end: date
) -> list[Scene]:
    body = {
        "collections": [COLLECTION],
        "intersects": geometry_wgs84,
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": MAX_SCENE_CLOUD_PCT}},
        "limit": 50,
    }
    response = await client.post(STAC_URL, json=body)
    response.raise_for_status()
    parcel = shape(geometry_wgs84)
    scenes = []
    for item in response.json()["features"]:
        if not shape(item["geometry"]).contains(parcel):
            continue  # parcel on a tile edge: the other tile has it whole
        props = item["properties"]
        baseline = float(props.get("s2:processing_baseline", "0") or 0)
        scenes.append(
            Scene(
                id=item["id"],
                day=datetime.fromisoformat(props["datetime"].replace("Z", "+00:00")).date(),
                cloud_pct=float(props["eo:cloud_cover"]),
                hrefs={band: item["assets"][band]["href"] for band in ("B04", "B08", "B11", "SCL")},
                offset=1000.0 if baseline >= 4.0 else 0.0,
                epsg=int(props["proj:epsg"]),
            )
        )
    # Most recent first, so the scene closest to the analysis date wins when clear;
    # one scene per day (the same overpass is published for overlapping tiles).
    by_day: dict[date, Scene] = {}
    for scene in sorted(scenes, key=lambda s: s.cloud_pct):
        by_day.setdefault(scene.day, scene)
    return sorted(by_day.values(), key=lambda s: s.day, reverse=True)


def _read_band(href: str, bounds: tuple, shape: tuple[int, int] | None) -> tuple:
    with rasterio.open(href) as ds:
        window = from_bounds(*bounds, ds.transform)
        if shape is None:  # SCL defines the 20 m analysis grid
            window = window.round_offsets().round_lengths()
            data = ds.read(1, window=window)
            return data, ds.window_transform(window)
        data = ds.read(1, window=window, out_shape=shape, resampling=Resampling.average)
        return data.astype(float), None


def read_indices(scene: Scene, geometry_wgs84: dict, token: str) -> SceneIndices | None:
    """Parcel-mean NDVI/NDMI on a 20 m grid; NaN values if the parcel is mostly cloudy."""
    geom = transform_geom("EPSG:4326", f"EPSG:{scene.epsg}", geometry_wgs84)
    # Snap to the 20 m grid so the resampled 10 m bands line up with SCL.
    minx, miny, maxx, maxy = shape(geom).bounds
    bounds = (minx // 20 * 20, miny // 20 * 20, -(-maxx // 20) * 20, -(-maxy // 20) * 20)
    hrefs = {band: f"/vsicurl/{href}?{token}" for band, href in scene.hrefs.items()}
    with rasterio.Env(**_GDAL_ENV):
        scl, transform = _read_band(hrefs["SCL"], bounds, None)
        if scl.size == 0:
            return None
        with ThreadPoolExecutor(3) as pool:
            futures = {
                b: pool.submit(_read_band, hrefs[b], bounds, scl.shape)
                for b in ("B04", "B08", "B11")
            }
            bands = {b: (f.result()[0] - scene.offset) / 10000 for b, f in futures.items()}
    inside = ~geometry_mask([geom], scl.shape, transform)
    if not inside.any():
        inside = ~geometry_mask([geom], scl.shape, transform, all_touched=True)
    clear = inside & np.isin(scl, _CLEAR_SCL)
    clear_pct = float(100 * clear.sum() / max(inside.sum(), 1))
    if clear_pct < MIN_CLEAR_PCT:
        return SceneIndices(scene.day, np.nan, np.nan, clear_pct)
    red, nir, swir = (bands[b][clear] for b in ("B04", "B08", "B11"))
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.nanmean((nir - red) / (nir + red))
        ndmi = np.nanmean((nir - swir) / (nir + swir))
    return SceneIndices(scene.day, float(ndvi), float(ndmi), clear_pct)


async def best_indices(
    client: httpx.AsyncClient,
    geometry_wgs84: dict,
    end: date,
    token: str,
    semaphore: asyncio.Semaphore,
) -> SceneIndices | None:
    """Most recent mostly-clear observation in the WINDOW_DAYS before `end`."""
    scenes = await search_scenes(client, geometry_wgs84, end - timedelta(days=WINDOW_DAYS), end)
    for scene in scenes[:CANDIDATES_PER_YEAR]:
        async with semaphore:
            result = await asyncio.to_thread(read_indices, scene, geometry_wgs84, token)
        if result is not None and np.isfinite(result.ndvi):
            return result
    return None


async def fetch_token(client: httpx.AsyncClient) -> str:
    response = await client.get(TOKEN_URL)
    response.raise_for_status()
    return response.json()["token"]


def to_geojson(geom: BaseGeometry) -> dict:
    return mapping(geom)
