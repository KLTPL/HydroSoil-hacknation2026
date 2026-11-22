"""LIDAR elevation of the analysed area as web map terrain tiles, for the 3D view.

Heights are relative to the area's median and fade to zero at its edge, so the field rises
out of a flat map without a cliff where the data ends. Tiles use the Terrarium encoding
(height = R·256 + G + B/256 − 32768 m) that MapLibre reads as a `raster-dem` source."""

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from pyproj import Transformer
from rasterio.transform import Affine
from shapely.geometry import box

from retencja_api import cache
from retencja_api.geo import geometry_to_wgs84
from retencja_api.terrain.flow import _edge_fade, encode_png
from retencja_api.terrain.nmt import Dem

TILE_PX = 256
_TO_METRIC = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


@dataclass(frozen=True)
class Elevation:
    heights: np.ndarray  # float32, metres relative to the median; row 0 = north
    transform: Affine  # PL-1992 (EPSG:2180)

    def wgs84_bounds(self) -> tuple[float, float, float, float]:
        h, w = self.heights.shape
        x0, y0 = self.transform * (0, 0)
        x1, y1 = self.transform * (w, h)
        return geometry_to_wgs84(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))).bounds


def elevation_path(cache_key: str) -> Path:
    return cache.cache_path("elevation", cache_key, ".npz")


def relative_heights(dem: Dem) -> np.ndarray:
    z = dem.elevation
    relative = np.nan_to_num(z - np.nanmedian(z))
    return (relative * _edge_fade(z.shape, dem.resolution)).astype(np.float32)


def save_elevation(cache_key: str, dem: Dem) -> None:
    path = elevation_path(cache_key)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, heights=relative_heights(dem), transform=np.array(dem.transform[:6]))
    tmp.replace(path)


@lru_cache(maxsize=8)
def load_elevation(cache_key: str) -> Elevation | None:
    path = elevation_path(cache_key)
    if not path.exists():
        return None
    with np.load(path) as data:
        return Elevation(heights=data["heights"], transform=Affine(*data["transform"]))


def _tile_lonlat(z: int, x: int, y: int) -> tuple[np.ndarray, np.ndarray]:
    """Longitude and latitude of each pixel centre of a web Mercator tile."""
    n = 2**z * TILE_PX
    px = (x * TILE_PX + np.arange(TILE_PX) + 0.5) / n
    py = (y * TILE_PX + np.arange(TILE_PX) + 0.5) / n
    lon = px * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * py))))
    return np.meshgrid(lon, lat)


def sample(elevation: Elevation, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Bilinear heights at the points; zero outside the grid."""
    xs, ys = _TO_METRIC.transform(lon, lat)
    cols, rows = ~elevation.transform @ (xs, ys)
    cols, rows = cols - 0.5, rows - 0.5  # cell centres
    h, w = elevation.heights.shape
    inside = (cols >= 0) & (rows >= 0) & (cols <= w - 1) & (rows <= h - 1)
    c0 = np.clip(np.floor(cols).astype(int), 0, w - 2)
    r0 = np.clip(np.floor(rows).astype(int), 0, h - 2)
    fc, fr = np.clip(cols - c0, 0, 1), np.clip(rows - r0, 0, 1)
    g = elevation.heights
    top = g[r0, c0] * (1 - fc) + g[r0, c0 + 1] * fc
    bottom = g[r0 + 1, c0] * (1 - fc) + g[r0 + 1, c0 + 1] * fc
    return np.where(inside, top * (1 - fr) + bottom * fr, 0.0)


def terrarium(heights: np.ndarray) -> np.ndarray:
    v = np.clip(heights + 32768.0, 0, 65535.99)
    r = np.floor(v / 256)
    g = np.floor(v) - r * 256
    b = np.floor((v - np.floor(v)) * 256)
    alpha = np.full_like(r, 255)
    return np.stack([r, g, b, alpha], axis=-1).astype(np.uint8)


def render_tile(elevation: Elevation | None, z: int, x: int, y: int) -> bytes:
    if elevation is None:
        return flat_tile()
    lon, lat = _tile_lonlat(z, x, y)
    return encode_png(terrarium(sample(elevation, lon, lat)))


@lru_cache(maxsize=1)
def flat_tile() -> bytes:
    return encode_png(terrarium(np.zeros((TILE_PX, TILE_PX))))
