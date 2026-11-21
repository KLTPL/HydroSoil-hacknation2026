"""Builds the parcel report: runs each analysis module within a time budget and
records which data sources were used, when, and under what licence."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Literal

import httpx
from shapely.geometry.base import BaseGeometry

from retencja_api.config import TERRAIN_TIME_BUDGET_S
from retencja_api.models import (
    AnalysisReport,
    Crop,
    DataSource,
    ModuleResult,
    Parcel,
    RetentionAnalysis,
)
from retencja_api.terrain.service import analyze_parcel, cached_analysis

log = logging.getLogger(__name__)

NMT_SOURCE = (
    "Numeryczny Model Terenu (GUGiK, LIDAR)",
    "https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/",
    "Dane bezpłatne, art. 40a ustawy Prawo geodezyjne i kartograficzne",
)

# One in-flight computation per key, so parallel requests share a slow download
# and a request that timed out keeps computing in the background.
_in_flight: dict[str, asyncio.Task] = {}


def _shared_task[T](key: str, start: Callable[[], Awaitable[T]]) -> asyncio.Task[T]:
    task = _in_flight.get(key)
    if task is None:
        task = asyncio.ensure_future(start())
        _in_flight[key] = task

        def _done(t: asyncio.Task) -> None:
            _in_flight.pop(key, None)
            if not t.cancelled() and t.exception() is not None:
                log.error("Background task %s failed", key, exc_info=t.exception())

        task.add_done_callback(_done)
    return task


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

    task = _shared_task(f"terrain:{parcel_id}", lambda: analyze_parcel(parcel_id, geom))
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


async def build_report(
    parcel: Parcel, geom: BaseGeometry, crop: Crop, analysis_date: date
) -> AnalysisReport:
    terrain = await terrain_module(parcel.id, geom, TERRAIN_TIME_BUDGET_S)
    return AnalysisReport(
        parcel=parcel,
        crop=crop,
        analysis_date=analysis_date,
        generated_at=datetime.now(UTC),
        terrain=terrain,
    )
