"""Soil category of the IUNG Agricultural Drought Monitoring System, read from the IUNG map
of soil categories (raster `Susza:katgl_landuse2024`, the one SMSR itself uses).

Codes: 1–4 are the drought-susceptibility categories I–IV, 5 organic soils, 11 forest,
12 water, 13 built-up land, 14 roads and wasteland."""

import asyncio
from collections import Counter

import httpx
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from retencja_api.cache import read_json, write_json
from retencja_api.models import SoilProfile

WMS_URL = "https://sgeo.iung.pl/geoserver/Susza/wms"
LAYER = "Susza:katgl_landuse2024"
ORGANIC = 5
CATEGORIES = {1: "I", 2: "II", 3: "III", 4: "IV"}
LABELS = {
    "I": "bardzo podatna na suszę",
    "II": "podatna na suszę",
    "III": "średnio podatna na suszę",
    "IV": "mało podatna na suszę",
}
_GRID = 3  # up to 3 × 3 sample points spread over the parcel
_HALF_PIXEL_M = 5.0


def sample_points(geom: BaseGeometry) -> list[Point]:
    """Points inside the parcel (EPSG:2180) on a regular grid, at least one."""
    minx, miny, maxx, maxy = geom.bounds
    points = [
        Point(minx + (maxx - minx) * (i + 0.5) / _GRID, miny + (maxy - miny) * (j + 0.5) / _GRID)
        for i in range(_GRID)
        for j in range(_GRID)
    ]
    inside = [p for p in points if geom.contains(p)]
    return inside or [geom.representative_point()]


async def _code_at(client: httpx.AsyncClient, point: Point) -> int | None:
    x, y = point.x, point.y
    response = await client.get(WMS_URL, params={
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetFeatureInfo",
        "LAYERS": LAYER, "QUERY_LAYERS": LAYER, "INFO_FORMAT": "application/json",
        "SRS": "EPSG:2180", "WIDTH": 1, "HEIGHT": 1, "X": 0, "Y": 0,
        "BBOX": f"{x - _HALF_PIXEL_M},{y - _HALF_PIXEL_M},{x + _HALF_PIXEL_M},{y + _HALF_PIXEL_M}",
    })
    response.raise_for_status()
    features = response.json().get("features", [])
    return int(features[0]["properties"]["GRAY_INDEX"]) if features else None


async def iung_code(parcel_id: str, geom: BaseGeometry) -> int | None:
    """Most frequent map code within the parcel, or None outside the map."""
    if (cached := read_json("iung-soil", parcel_id)) is not None:
        return cached["code"]
    async with httpx.AsyncClient(timeout=10) as client:
        codes = await asyncio.gather(*(_code_at(client, p) for p in sample_points(geom)))
    found = [c for c in codes if c]
    code = Counter(found).most_common(1)[0][0] if found else None
    write_json("iung-soil", parcel_id, {"code": code})
    return code


def with_iung_category(profile: SoilProfile, code: int | None) -> SoilProfile:
    """The profile with the official category (1–4) or the organic-soil flag (5)."""
    if code in CATEGORIES:
        category = CATEGORIES[code]
        return profile.model_copy(update={
            "category": category, "category_label": LABELS[category], "category_source": "IUNG",
        })
    if code == ORGANIC:
        return profile.model_copy(update={"organic_soil": True, "category_source": "IUNG"})
    return profile
