"""HTTP API."""

import asyncio
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from shapely.geometry.base import BaseGeometry

from retencja_api.config import HISTORY_YEARS
from retencja_api.crops import CROPS, CROPS_BY_ID
from retencja_api.models import AnalysisReport, Crop, ModuleResult, Parcel, RetentionAnalysis
from retencja_api.parcel.uldk import (
    ParcelNotFound,
    get_parcel_by_id,
    get_parcel_by_point,
    search_parcels,
)
from retencja_api.progress import ModuleProgress, module_progress
from retencja_api.report import build_report, terrain_module
from retencja_api.terrain.service import relief_path

app = FastAPI(title="Retencja API")

# Polling requests (poll=true) only collect results that finished in the background.
POLL_BUDGET_S = 2.0


def earliest_analysis_date(today: date) -> date:
    try:
        return today.replace(year=today.year - HISTORY_YEARS)
    except ValueError:  # 29 February → 28 February
        return today.replace(year=today.year - HISTORY_YEARS, day=28)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/crops")
async def crops() -> list[Crop]:
    return CROPS


@app.get("/api/parcels/search")
async def parcel_search(q: str = Query(min_length=2, max_length=80)) -> list[Parcel]:
    try:
        return await search_parcels(q)
    except ParcelNotFound:
        return []


@app.get("/api/parcels/at")
async def parcel_at(
    lat: float = Query(ge=48.5, le=55.0), lon: float = Query(ge=13.5, le=24.5)
) -> Parcel:
    try:
        parcel, _ = await get_parcel_by_point(lon, lat)
    except ParcelNotFound:
        raise HTTPException(404, "Brak działki ewidencyjnej w tym miejscu") from None
    return parcel


AnalysisInputs = tuple[Parcel, BaseGeometry, Crop, date]


async def analysis_inputs(
    parcel_id: str = Query(min_length=5, max_length=64),
    crop: str = Query(),
    analysis_date: date | None = Query(default=None, alias="date"),
) -> AnalysisInputs:
    """Validated request parameters. A dependency, so errors are returned before a stream
    starts (a streamed response has already sent its 200 status)."""
    today = date.today()
    analysis_date = analysis_date or today
    earliest = earliest_analysis_date(today)
    if not earliest <= analysis_date <= today:
        raise HTTPException(422, f"Data analizy musi mieścić się między {earliest:%d.%m.%Y} a dziś")
    if crop not in CROPS_BY_ID:
        raise HTTPException(422, "Nieznana uprawa")
    try:
        parcel, geom = await get_parcel_by_id(parcel_id)
    except ParcelNotFound:
        raise HTTPException(404, "Nie znaleziono działki") from None
    return parcel, geom, CROPS_BY_ID[crop], analysis_date


@app.get("/api/analysis")
async def analysis(
    inputs: Annotated[AnalysisInputs, Depends(analysis_inputs)],
    poll: bool = Query(default=False),
) -> AnalysisReport:
    parcel, geom, crop_model, day = inputs
    budget = POLL_BUDGET_S if poll else None
    return await build_report(parcel, geom, crop_model, day, budget)


@app.get("/api/analysis/stream", response_class=EventSourceResponse)
async def analysis_stream(
    inputs: Annotated[AnalysisInputs, Depends(analysis_inputs)],
) -> AsyncIterator[ServerSentEvent]:
    """Same report as /api/analysis, preceded by a `module` event as each data source
    finishes, so the farmer sees the analysis progress instead of a spinner."""
    parcel, geom, crop_model, day = inputs
    queue: asyncio.Queue[ModuleProgress | None] = asyncio.Queue()
    task = asyncio.create_task(
        build_report(
            parcel, geom, crop_model, day,
            on_module=lambda name, result: queue.put_nowait(module_progress(name, result)),
        )
    )
    task.add_done_callback(lambda _: queue.put_nowait(None))
    while (progress := await queue.get()) is not None:
        yield ServerSentEvent(event="module", data=progress)
    yield ServerSentEvent(event="report", data=task.result())


@app.get("/api/terrain")
async def terrain(
    parcel_id: str = Query(min_length=5, max_length=64),
) -> ModuleResult[RetentionAnalysis]:
    try:
        _, geom = await get_parcel_by_id(parcel_id)
    except ParcelNotFound:
        raise HTTPException(404, "Nie znaleziono działki") from None
    return await terrain_module(parcel_id, geom, POLL_BUDGET_S)


@app.get("/api/terrain/relief.png", response_class=FileResponse)
async def terrain_relief(parcel_id: str = Query(min_length=5, max_length=64)) -> FileResponse:
    """Shaded micro-relief image produced by the terrain analysis (see `relief` in it)."""
    path = relief_path(parcel_id)
    if not path.exists():
        raise HTTPException(404, "Brak obrazu rzeźby terenu: analiza terenu jeszcze trwa")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=86400"})
