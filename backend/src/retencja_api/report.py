"""Builds the parcel report: runs each analysis module within a time budget and
records which data sources were used, when, and under what licence."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.diagnosis import diagnose, land_warnings
from retencja_api.assessment.parcel_shape import parcel_shape
from retencja_api.assessment.recommendations import recommend
from retencja_api.background import recent_error, shared_task
from retencja_api.config import (
    HISTORY_YEARS,
    PARCEL_BUFFER_M,
    TERRAIN_MAX_AREA_HA,
    TERRAIN_TIME_BUDGET_S,
)
from retencja_api.drought.smsr_gmina import gmina_table, with_official
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
from retencja_api.modules import (
    edo_module,
    hydro_module,
    land_module,
    satellite_module,
    soil_module,
    water_module,
)
from retencja_api.soil.iung import iung_code, with_iung_category
from retencja_api.soil.soilgrids import DEFAULT_PROFILE, humus_water_gain_mm
from retencja_api.terrain.service import analyze_parcel, cached_analysis

log = logging.getLogger(__name__)

IUNG_SOIL_SOURCE = (
    "Mapa kategorii glebowych SMSR (IUNG-PIB)",
    "https://susza.iung.pulawy.pl/kategorie/",
    "Dane publiczne IUNG-PIB",
)

SMSR_SOURCE = (
    "System Monitoringu Suszy Rolniczej, tabele dla gmin (IUNG-PIB)",
    "https://susza.iung.pulawy.pl/wykazy/",
    "Dane publiczne IUNG-PIB (na zlecenie MRiRW)",
)

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
    # The download covers the buffered bounding box, so a long diagonal strip costs as much
    # as a large parcel.
    extent_ha = geom.buffer(PARCEL_BUFFER_M).envelope.area / 10_000
    if extent_ha > TERRAIN_MAX_AREA_HA:
        return ModuleResult(
            status="unavailable",
            message=(
                f"Model terenu dla tej działki obejmuje {extent_ha:.0f} ha; analiza z LIDAR "
                f"działa do {TERRAIN_MAX_AREA_HA:.0f} ha (czas pobierania danych GUGiK)."
            ),
            duration_ms=elapsed(),
        )

    key = f"terrain:{parcel_id}"
    if recent_error(key) is not None:
        return _terrain_failed(elapsed())
    task = shared_task(key, lambda: analyze_parcel(parcel_id, geom))
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
        return _terrain_failed(elapsed())

    return _terrain_ok(data, "live", elapsed())


async def soil_with_category(
    parcel_id: str, geom: BaseGeometry, bounds_wgs84: tuple[float, float, float, float]
) -> ModuleResult[SoilProfile]:
    """SoilGrids texture and water capacity, with the soil category from the IUNG map
    (the one the official drought criterion uses) when that map answers."""
    soil, code = await asyncio.gather(
        soil_module(bounds_wgs84), iung_code(parcel_id, geom), return_exceptions=True
    )
    if isinstance(soil, BaseException):
        raise soil
    if isinstance(code, httpx.HTTPError):
        log.warning("IUNG soil category unavailable for %s: %r", parcel_id, code)
        return soil
    if isinstance(code, BaseException):
        raise code
    if soil.data is None:
        return soil
    profile = with_iung_category(soil.data, code)
    if profile.category_source != "IUNG":
        return soil
    name, url, licence = IUNG_SOIL_SOURCE
    source = DataSource(name=name, url=url, license=licence, retrieved="live",
                        retrieved_at=datetime.now(UTC))
    return soil.model_copy(update={"data": profile, "sources": [*soil.sources, source]})


async def with_official_smsr(
    water: ModuleResult[WaterBalance], parcel_id: str, crop_id: str
) -> ModuleResult[WaterBalance]:
    """Replace the computed SMSR verdict with the official one for the gmina, if published."""
    check = water.data.smsr if water.data else None
    if check is None:
        return water
    try:
        table = await gmina_table(parcel_id, check.period_end.year)
    except httpx.HTTPError as exc:
        log.warning("SMSR gmina table unavailable for %s: %r", parcel_id, exc)
        return water
    official = with_official(check, table, crop_id)
    if not official.official:
        return water
    name, url, licence = SMSR_SOURCE
    source = DataSource(name=name, url=url, license=licence, retrieved="live",
                        retrieved_at=datetime.now(UTC))
    data = water.data.model_copy(update={"smsr": official})
    return water.model_copy(update={"data": data, "sources": [*water.sources, source]})


def _terrain_failed(duration_ms: int) -> ModuleResult[RetentionAnalysis]:
    return ModuleResult(
        status="unavailable",
        message="Nie udało się pobrać modelu terenu z GUGiK. Spróbuj ponownie za kilka minut.",
        duration_ms=duration_ms,
    )


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
        "land": "pokrycie terenu",
        "terrain": "model terenu",
    }
    return [
        f"{labels[name]}: {result.message or 'brak danych'}"
        for name, result in modules.items()
        if result.status != "ok"
    ]


type ModuleListener = Callable[[str, ModuleResult[Any]], None]


async def build_report(
    parcel: Parcel,
    geom: BaseGeometry,
    crop: Crop,
    analysis_date: date,
    budget_s: float | None = None,
    on_module: ModuleListener | None = None,
) -> AnalysisReport:
    """Runs all modules concurrently. `budget_s` limits slow modules (terrain, satellite);
    a short budget is used by polling requests that only collect finished results.
    `on_module` is told about each module as soon as it finishes (live progress)."""
    budget = TERRAIN_TIME_BUDGET_S if budget_s is None else budget_s
    params = CROP_PARAMS[crop.id]
    geom_wgs84 = geometry_to_wgs84(geom)
    centre = geom_wgs84.representative_point()

    async def report[T](name: str, run: Awaitable[ModuleResult[T]]) -> ModuleResult[T]:
        result = await run
        if on_module is not None:
            on_module(name, result)
        return result

    async def soil_and_water() -> tuple[ModuleResult[SoilProfile], ModuleResult[WaterBalance]]:
        soil = await report("soil", soil_with_category(parcel.id, geom, geom_wgs84.bounds))
        profile = soil.data or DEFAULT_PROFILE
        water = await report(
            "water",
            water_module(
                centre.y, centre.x, params, analysis_date, profile.awc_mm_per_m, HISTORY_YEARS,
                humus_water_gain_mm(profile) if soil.data else 0.0,
                (crop.id, profile.category),
            ),
        )
        return soil, await with_official_smsr(water, parcel.id, crop.id)

    (soil, water), satellite, hydro, land, terrain, edo = await asyncio.gather(
        soil_and_water(),
        report(
            "satellite",
            satellite_module(parcel.id, mapping(geom_wgs84), analysis_date, HISTORY_YEARS, budget),
        ),
        report("hydro", hydro_module(parcel.voivodeship, analysis_date)),
        report("land", land_module(parcel.id, mapping(geom_wgs84))),
        report("terrain", terrain_module(parcel.id, geom, budget)),
        report("edo", edo_module(centre.y, centre.x, analysis_date)),
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
             "land": land, "terrain": terrain}
        ),
    )
    if warnings := land_warnings(land.data, params):
        diagnosis = diagnosis.model_copy(update={"warnings": warnings, "confidence": "low"})
    shape = parcel_shape(geom)
    if edo.data is not None:
        agrees = edo.data.drought == (diagnosis.level != "none")
        edo = edo.model_copy(update={"data": edo.data.model_copy(update={"agrees": agrees})})
    return AnalysisReport(
        parcel=parcel,
        crop=crop,
        analysis_date=analysis_date,
        generated_at=datetime.now(UTC),
        diagnosis=diagnosis,
        recommendations=recommend(
            params, parcel.area_ha, water.data, soil.data, hydro.data, terrain.data, shape,
            land.data,
        ),
        water=water,
        soil=soil,
        satellite=satellite,
        hydro=hydro,
        land=land,
        terrain=terrain,
        edo=edo,
        shape=shape,
    )
