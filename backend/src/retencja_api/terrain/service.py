"""Parcel retention analysis: DEM loading, site detection, response assembly, caching."""

import asyncio

from shapely.geometry import mapping
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
    Range,
    RetentionAnalysis,
    RetentionSite,
    RetentionSummary,
)
from retencja_api.terrain.nmt import load_dem
from retencja_api.terrain.retention import Site, find_sites


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


async def analyze_parcel(parcel_id: str, parcel_geom: BaseGeometry) -> RetentionAnalysis:
    key = f"{parcel_id}@v{ANALYSIS_VERSION}"
    cached = cache.read_json("retention", key)
    if cached is not None:
        return RetentionAnalysis.model_validate(cached)

    bounds = parcel_geom.buffer(PARCEL_BUFFER_M).bounds
    dem = await load_dem(bounds, ANALYSIS_RESOLUTION_M)
    sites = await asyncio.to_thread(find_sites, dem, parcel_geom)
    models = [_to_model(i, s) for i, s in enumerate(sites, start=1)]

    result = RetentionAnalysis(
        parcel_id=parcel_id,
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
    )
    cache.write_json("retention", key, result.model_dump())
    return result
