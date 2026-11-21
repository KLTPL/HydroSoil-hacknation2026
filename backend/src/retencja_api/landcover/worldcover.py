"""Land cover of the parcel from ESA WorldCover 2021 (10 m, Sentinel-1/2 based), read as a
Cloud-Optimized GeoTIFF window from Microsoft Planetary Computer. Used to warn when the
parcel is not farmland (built-up, forest, water), where crop results make little sense."""

import asyncio

import httpx
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

from retencja_api.cache import read_json, write_json
from retencja_api.models import LandCover, LandCoverShare

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/esa-worldcover"
YEAR = 2021
CLASSES = {
    10: "las i zadrzewienia",
    20: "zarośla",
    30: "łąki i pastwiska",
    40: "grunty orne",
    50: "zabudowa",
    60: "teren bez roślinności",
    70: "śnieg i lód",
    80: "wody",
    90: "mokradła",
    95: "namorzyny",
    100: "mchy i porosty",
}
AGRICULTURAL = (30, 40)
MIN_AGRICULTURAL_SHARE = 0.5
_GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "GDAL_HTTP_TIMEOUT": "10"}


async def _asset_href(geometry_wgs84: dict) -> str:
    body = {
        "collections": ["esa-worldcover"],
        "intersects": geometry_wgs84,
        "datetime": f"{YEAR}-01-01T00:00:00Z/{YEAR}-12-31T23:59:59Z",
        "limit": 4,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        search, token = await asyncio.gather(
            client.post(STAC_URL, json=body), client.get(TOKEN_URL)
        )
        search.raise_for_status()
        token.raise_for_status()
    parcel = shape(geometry_wgs84)
    items = search.json()["features"]
    item = next((i for i in items if shape(i["geometry"]).contains(parcel)), items[0])
    return f"{item['assets']['map']['href']}?{token.json()['token']}"


def class_counts(href: str, geometry_wgs84: dict) -> dict[int, int]:
    with rasterio.Env(**_GDAL_ENV), rasterio.open(f"/vsicurl/{href}") as ds:
        window = from_bounds(*shape(geometry_wgs84).bounds, ds.transform)
        window = window.round_offsets().round_lengths()
        data = ds.read(1, window=window, boundless=True, fill_value=0)
        transform = ds.window_transform(window)
    inside = ~geometry_mask([geometry_wgs84], data.shape, transform, all_touched=True)
    values, counts = np.unique(data[inside & (data > 0)], return_counts=True)
    return {int(v): int(c) for v, c in zip(values, counts, strict=True)}


def summarize(counts: dict[int, int]) -> LandCover:
    total = sum(counts.values()) or 1
    shares = sorted(
        (
            LandCoverShare(code=code, name=CLASSES.get(code, str(code)), share=round(n / total, 3))
            for code, n in counts.items()
        ),
        key=lambda s: -s.share,
    )
    agricultural = sum(s.share for s in shares if s.code in AGRICULTURAL)
    return LandCover(
        year=YEAR,
        classes=shares,
        agricultural_share=round(agricultural, 3),
        is_agricultural=agricultural >= MIN_AGRICULTURAL_SHARE,
    )


async def land_cover(parcel_id: str, geometry_wgs84: dict) -> LandCover:
    cached = read_json("worldcover", parcel_id)
    if cached is None:
        href = await _asset_href(geometry_wgs84)
        counts = await asyncio.to_thread(class_counts, href, geometry_wgs84)
        cached = {str(k): v for k, v in counts.items()}
        write_json("worldcover", parcel_id, cached)
    return summarize({int(k): v for k, v in cached.items()})
