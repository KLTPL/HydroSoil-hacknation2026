"""Builds the parcel report: runs each analysis module within a time budget and
records which data sources were used, when, and under what licence."""

import asyncio
import logging
import time
from datetime import UTC, date, datetime
from typing import Literal

import httpx
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.diagnosis import diagnose
from retencja_api.assessment.recommendations import recommend
from retencja_api.background import shared_task
from retencja_api.config import HISTORY_YEARS, TERRAIN_TIME_BUDGET_S
from retencja_api.geo import geometry_to_wgs84
from retencja_api.models import (
    AnalysisReport,
    Crop,
    DataSource,
    ModuleResult,
    Parcel,
    RetentionAnalysis,
    SoilProfile,
    WaterBalance,
)
from retencja_api.modules import hydro_module, satellite_module, soil_module, water_module
from retencja_api.soil.soilgrids import DEFAULT_PROFILE
from retencja_api.terrain.service import analyze_parcel, cached_analysis

log = logging.getLogger(__name__)

NMT_SOURCE = (
    "Numeryczny Model Terenu (GUGiK, LIDAR)",
    "https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/",
    "Dane bezpłatne, art. 40a ustawy Prawo geodezyjne i kartograficzne",
)

async def terrain_module(
    parcel_id: str, geom: BaseGeometry, budget_s: float
) -> ModuleResult[RetentionAnalysis]:
    """Terrain result, or `pending` if not ready within `budget_s` (computation continues)."""
    started = time.monotonic()

    def elapsed() -> int:
        return round((time.monotonic() - started) * 1000)

    cached = cached_analysis(parcel_id)
    if cached is not None:
        return _terrain_ok(cached, "cached", elapsed())

    task = shared_task(f"terrain:{parcel_id}", lambda: analyze_parcel(parcel_id, geom))
    try:
        data = await asyncio.wait_for(asyncio.shield(task), budget_s)
    except TimeoutError:
        return ModuleResult(
            status="pending",
            message=(
                "Pobieram model terenu z GUGiK (serwer odpowiada wolno). "
                "Mapa miejsc retencji pojawi się automatycznie."
            ),
            duration_ms=elapsed(),
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        log.warning("Terrain unavailable for %s: %s", parcel_id, exc)
        return ModuleResult(
            status="unavailable",
            message="Nie udało się pobrać modelu terenu z GUGiK. Spróbuj ponownie później.",
            duration_ms=elapsed(),
        )

    return _terrain_ok(data, "live", elapsed())


def _terrain_ok(
    data: RetentionAnalysis, retrieved: Literal["live", "cached"], duration_ms: int
) -> ModuleResult[RetentionAnalysis]:
    name, url, licence = NMT_SOURCE
    source = DataSource(
        name=name, url=url, license=licence, retrieved=retrieved, retrieved_at=data.computed_at
    )
    return ModuleResult(status="ok", data=data, sources=[source], duration_ms=duration_ms)


def _missing(modules: dict[str, ModuleResult]) -> list[str]:
    labels = {
        "water": "pogoda i bilans wodny",
        "soil": "gleba",
        "satellite": "zdjęcia satelitarne",
        "hydro": "ostrzeżenia hydrologiczne IMGW",
        "terrain": "model terenu",
    }
    return [
        f"{labels[name]}: {result.message or 'brak danych'}"
        for name, result in modules.items()
        if result.status != "ok"
    ]


async def build_report(
    parcel: Parcel,
    geom: BaseGeometry,
    crop: Crop,
    analysis_date: date,
    budget_s: float | None = None,
) -> AnalysisReport:
    """Runs all modules concurrently. `budget_s` limits slow modules (terrain, satellite);
    a short budget is used by polling requests that only collect finished results."""
    budget = TERRAIN_TIME_BUDGET_S if budget_s is None else budget_s
    params = CROP_PARAMS[crop.id]
    geom_wgs84 = geometry_to_wgs84(geom)
    centre = geom_wgs84.representative_point()

    async def soil_and_water() -> tuple[ModuleResult[SoilProfile], ModuleResult[WaterBalance]]:
        soil = await soil_module(geom_wgs84.bounds)
        awc = (soil.data or DEFAULT_PROFILE).awc_mm_per_m
        water = await water_module(centre.y, centre.x, params, analysis_date, awc, HISTORY_YEARS)
        return soil, water

    (soil, water), satellite, hydro, terrain = await asyncio.gather(
        soil_and_water(),
        satellite_module(parcel.id, mapping(geom_wgs84), analysis_date, HISTORY_YEARS, budget),
        hydro_module(parcel.voivodeship, analysis_date),
        terrain_module(parcel.id, geom, budget),
    )
    diagnosis = diagnose(
        params,
        parcel.area_ha,
        water.data,
        soil.data or DEFAULT_PROFILE,
        satellite.data,
        hydro.data,
        terrain.data,
        _missing(
            {"water": water, "soil": soil, "satellite": satellite, "hydro": hydro,
             "terrain": terrain}
        ),
    )
    return AnalysisReport(
        parcel=parcel,
        crop=crop,
        analysis_date=analysis_date,
        generated_at=datetime.now(UTC),
        diagnosis=diagnosis,
        recommendations=recommend(
            params, parcel.area_ha, water.data, soil.data, hydro.data, terrain.data
        ),
        water=water,
        soil=soil,
        satellite=satellite,
        hydro=hydro,
        terrain=terrain,
    )
