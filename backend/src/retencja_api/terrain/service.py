"""Parcel retention analysis: DEM loading, site detection, response assembly, caching."""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from rasterio.errors import RasterioIOError
from shapely.geometry import MultiPoint, Polygon, mapping
from shapely.geometry.base import BaseGeometry

from retencja_api import cache
from retencja_api.config import (
    ANALYSIS_RESOLUTION_M,
    ANALYSIS_VERSION,
    DESIGN_RAIN_MM,
    MIN_DEPRESSION_AREA_M2,
    MIN_DEPRESSION_DEPTH_M,
    PARCEL_BUFFER_M,
    RUNOFF_COEFF_RANGE,
)
from retencja_api.geo import geometry_to_wgs84
from retencja_api.models import (
    Assumptions,
    DitchWeirs,
    FlowPath,
    Range,
    ReliefImage,
    RetentionAnalysis,
    RetentionSite,
    RetentionSummary,
)
from retencja_api.terrain.channels import detect_channels
from retencja_api.terrain.ditches import (
    WEIR_HEAD_M,
    DitchPlan,
    fetch_waterways,
    merge_sources,
    osm_lines,
    plan_ditches,
)
from retencja_api.terrain.flow import encode_png, flow_lines, relief_rgba
from retencja_api.terrain.nmt import Dem, load_dem
from retencja_api.terrain.nmt_sheets import load_sheet_dem
from retencja_api.terrain.retention import Site, find_sites
from retencja_api.terrain.slope import slope_stats


def _to_model(index: int, site: Site) -> RetentionSite:
    return RetentionSite(
        id=index,
        kind=site.kind,
        area_m2=round(site.area_m2),
        max_depth_m=round(site.max_depth_m, 2),
        storage_m3=round(site.storage_m3),
        catchment_ha=round(site.catchment_ha, 2),
        runoff_m3=Range(low=round(site.runoff_m3[0]), high=round(site.runoff_m3[1])),
        retained_m3=Range(low=round(site.retained_m3[0]), high=round(site.retained_m3[1])),
        parcel_share=round(site.parcel_share, 2),
        geometry=mapping(geometry_to_wgs84(site.geometry)),
    )


log = logging.getLogger(__name__)


def _ditch_model(index: int, plan: DitchPlan) -> DitchWeirs:
    return DitchWeirs(
        id=index,
        kind=plan.kind,
        length_m=round(plan.length_m),
        slope_pct=round(plan.slope * 100, 2),
        weir_count=len(plan.weirs),
        weir_head_m=WEIR_HEAD_M,
        channel_m3=round(plan.channel_m3),
        soil_m3=Range(low=round(plan.soil_m3[0]), high=round(plan.soil_m3[1])),
        geometry=mapping(geometry_to_wgs84(plan.line)),
        weirs=mapping(geometry_to_wgs84(MultiPoint(plan.weirs))),
    )


def _rounded(geojson: dict) -> dict:
    """~0.1 m precision is plenty for map lines and keeps the response small."""
    coords = [[round(x, 6), round(y, 6)] for x, y in geojson["coordinates"]]
    return {"type": geojson["type"], "coordinates": coords}


def relief_path(parcel_id: str) -> Path:
    return cache.cache_path("relief", _cache_key(parcel_id), ".png")


def _save_relief(parcel_id: str, dem: Dem) -> ReliefImage:
    rgba, spread = relief_rgba(dem)
    path = relief_path(parcel_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(encode_png(rgba))
    tmp.replace(path)
    h, w = dem.elevation.shape
    corners = Polygon([dem.transform * (c, r) for c, r in ((0, 0), (w, 0), (w, h), (0, h))])
    lonlat = geometry_to_wgs84(corners).exterior.coords[:4]
    return ReliefImage(
        corners=[[round(x, 7), round(y, 7)] for x, y in lonlat], spread_m=round(spread, 2)
    )


async def _load_dem(bounds: tuple[float, float, float, float]) -> Dem:
    """Static NMT sheets first; the (slower, load-sensitive) WCS if they fail."""
    try:
        return await load_sheet_dem(bounds, ANALYSIS_RESOLUTION_M)
    except (httpx.HTTPError, RuntimeError, RasterioIOError) as exc:  # NoSheets too
        log.warning("NMT sheets unavailable, falling back to WCS: %r", exc)
    return await load_dem(bounds, ANALYSIS_RESOLUTION_M)


def _cache_key(parcel_id: str) -> str:
    return f"{parcel_id}@v{ANALYSIS_VERSION}"


def cached_analysis(parcel_id: str) -> RetentionAnalysis | None:
    cached = cache.read_json("retention", _cache_key(parcel_id))
    return None if cached is None else RetentionAnalysis.model_validate(cached)


async def analyze_parcel(parcel_id: str, parcel_geom: BaseGeometry) -> RetentionAnalysis:
    """Download terrain, find retention sites and cache the result."""
    bounds = parcel_geom.buffer(PARCEL_BUFFER_M).bounds
    dem_task = asyncio.ensure_future(_load_dem(bounds))
    try:
        ways = await fetch_waterways(geometry_to_wgs84(parcel_geom.buffer(PARCEL_BUFFER_M)).bounds)
    except httpx.HTTPError as exc:
        log.warning("Ditch map unavailable: %r", exc)
        ways = None
    dem = await dem_task
    sites = await asyncio.to_thread(find_sites, dem, parcel_geom)
    models = [_to_model(i, s) for i, s in enumerate(sites, start=1)]
    channels = await asyncio.to_thread(detect_channels, dem)
    lines = merge_sources(channels, osm_lines(ways or []))
    plans = await asyncio.to_thread(plan_ditches, lines, parcel_geom, dem)
    flows = await asyncio.to_thread(flow_lines, dem)
    relief = await asyncio.to_thread(_save_relief, parcel_id, dem)
    slope = await asyncio.to_thread(slope_stats, dem, parcel_geom)

    result = RetentionAnalysis(
        parcel_id=parcel_id,
        computed_at=datetime.now(UTC),
        summary=RetentionSummary(
            site_count=len(models),
            storage_m3=sum(m.storage_m3 for m in models),
            retained_m3=Range(
                low=sum(m.retained_m3.low for m in models),
                high=sum(m.retained_m3.high for m in models),
            ),
        ),
        sites=models,
        assumptions=Assumptions(
            dem_source="NMT GUGiK (LIDAR, 1 m)",
            resolution_m=ANALYSIS_RESOLUTION_M,
            design_rain_mm=DESIGN_RAIN_MM,
            runoff_coeff=Range(low=RUNOFF_COEFF_RANGE[0], high=RUNOFF_COEFF_RANGE[1]),
            min_depth_m=MIN_DEPRESSION_DEPTH_M,
            min_area_m2=MIN_DEPRESSION_AREA_M2,
        ),
        ditches=[_ditch_model(i, p) for i, p in enumerate(plans, start=1)],
        ditches_checked=ways is not None,
        flow=[
            FlowPath(
                area_m2=round(f.area_m2), end=f.end, next=f.next_index,
                geometry=_rounded(mapping(geometry_to_wgs84(f.line))),
            )
            for f in flows
        ],
        relief=relief,
        slope=slope,
    )
    cache.write_json("retention", _cache_key(parcel_id), result.model_dump(mode="json"))
    return result
