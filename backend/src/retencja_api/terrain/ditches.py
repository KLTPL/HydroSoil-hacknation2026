"""Ditches on and along the parcel (OpenStreetMap and LIDAR-detected channels) and a weir
plan for each one.

A weir (zastawka) raises the water in a drainage ditch by WEIR_HEAD_M. Water is held
twice: in the ditch behind the weir (backwater), and in the soil on both banks, where
the raised ditch level lifts the groundwater table. Ditch gradient comes from the DEM.
"""

import math
from dataclasses import dataclass

import httpx
import numpy as np
from shapely.geometry import LineString, MultiLineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, unary_union

from retencja_api.cache import read_json, write_json
from retencja_api.geo import lonlat_to_metric
from retencja_api.terrain.nmt import Dem

# Public Overpass instances, tried in order (the main one throttles or drops clients).
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "zatrzymaj-wode/0.1 (hackathon prototype)"
WATERWAYS = "ditch|drain|canal|stream"
LIDAR_KIND = "lidar"  # channel detected in the terrain model, not on any map
OVERLAP_BUFFER_M = 8.0  # a LIDAR channel this close to an OSM ditch is the same ditch
DITCH_NEAR_PARCEL_M = 25.0  # ditches on the boundary also drain the parcel
MIN_DITCH_LENGTH_M = 50.0

WEIR_HEAD_M = 0.5  # typical raise of a wooden or concrete weir
DITCH_WET_WIDTH_M = 1.5
BANK_INFLUENCE_M = 50.0  # groundwater rise reaches this far on each bank
SPECIFIC_YIELD = (0.05, 0.15)  # drainable porosity: loam … sand
MIN_SLOPE = 0.0005  # flatter ditches: one weir holds the whole stretch
MIN_SPACING_M = 50.0


@dataclass(frozen=True)
class DitchPlan:
    line: BaseGeometry  # PL-1992, part within reach of the parcel
    kind: str
    length_m: float
    slope: float
    weirs: list[Point]
    channel_m3: float
    soil_m3: tuple[float, float]


async def fetch_waterways(bounds_wgs84: tuple[float, float, float, float]) -> list[dict]:
    west, south, east, north = bounds_wgs84
    key = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    cached = read_json("overpass", key)
    if cached is not None:
        return cached
    query = f'[out:json][timeout:20];way["waterway"~"^({WATERWAYS})$"]({key});out geom tags;'
    timeout = httpx.Timeout(12, connect=5)  # LIDAR channels cover for a slow Overpass
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        for i, url in enumerate(OVERPASS_URLS):
            try:
                response = await client.post(url, data={"data": query})
                response.raise_for_status()
                break
            except httpx.HTTPError:
                if i == len(OVERPASS_URLS) - 1:
                    raise
        ways = [
            {"kind": e["tags"]["waterway"], "coords": [(p["lon"], p["lat"]) for p in e["geometry"]]}
            for e in response.json()["elements"]
            if len(e.get("geometry", [])) >= 2
        ]
    write_json("overpass", key, ways)
    return ways


def _elevation(dem: Dem, x: float, y: float) -> float:
    col, row = ~dem.transform @ (x, y)
    r, c = int(row), int(col)
    if 0 <= r < dem.elevation.shape[0] and 0 <= c < dem.elevation.shape[1]:
        return float(dem.elevation[r, c])
    return math.nan


def plan_ditch(line: LineString, kind: str, dem: Dem) -> DitchPlan | None:
    length = line.length
    if length < MIN_DITCH_LENGTH_M:
        return None
    step = max(dem.resolution, 2.0)
    distances = np.arange(0, length, step)
    points = [line.interpolate(d) for d in distances]
    z = np.array([_elevation(dem, p.x, p.y) for p in points])
    ok = np.isfinite(z)
    if ok.sum() < 5:
        return None
    gradient = np.polyfit(distances[ok], z[ok], 1)[0]  # m per m along the line
    slope = max(abs(gradient), MIN_SLOPE)
    spacing = min(max(WEIR_HEAD_M / slope, MIN_SPACING_M), length)
    # Weirs from the downstream end up, one wherever the previous backwater ends.
    downstream_first = gradient > 0  # elevation rises along the line → start is downstream
    offsets = np.arange(min(5.0, length / 10), length, spacing)
    weirs = [line.interpolate(d if downstream_first else length - d) for d in offsets]
    backwater = min(WEIR_HEAD_M / slope, spacing)
    channel = len(weirs) * 0.5 * backwater * WEIR_HEAD_M * DITCH_WET_WIDTH_M
    raised = min(length, len(weirs) * backwater)
    band_m2 = raised * 2 * BANK_INFLUENCE_M
    mean_rise = WEIR_HEAD_M / 2
    soil = tuple(band_m2 * mean_rise * sy for sy in SPECIFIC_YIELD)
    return DitchPlan(line, kind, length, slope, weirs, channel, soil)  # type: ignore[arg-type]


Line = tuple[LineString, str]  # PL-1992 geometry, kind


def osm_lines(ways: list[dict]) -> list[Line]:
    return [
        (LineString([lonlat_to_metric(lon, lat) for lon, lat in way["coords"]]), way["kind"])
        for way in ways
    ]


def merge_sources(lidar: list[LineString], osm: list[Line]) -> list[Line]:
    """OSM ditches plus LIDAR channels that OSM does not already map."""
    if not osm:
        return [(line, LIDAR_KIND) for line in lidar]
    mapped = unary_union([line.buffer(OVERLAP_BUFFER_M) for line, _ in osm])
    extra = [
        (line, LIDAR_KIND)
        for line in lidar
        if line.intersection(mapped).length < 0.5 * line.length
    ]
    return osm + extra


def plan_ditches(lines: list[Line], parcel: BaseGeometry, dem: Dem) -> list[DitchPlan]:
    reach = parcel.buffer(DITCH_NEAR_PARCEL_M)
    plans = []
    for line, kind in lines:
        part = line.intersection(reach)
        if part.is_empty:
            continue
        if isinstance(part, MultiLineString):
            part = linemerge(part)
        parts = part.geoms if isinstance(part, MultiLineString) else [part]
        for segment in parts:
            if isinstance(segment, LineString) and (plan := plan_ditch(segment, kind, dem)):
                plans.append(plan)
    return sorted(plans, key=lambda p: -p.soil_m3[1])
