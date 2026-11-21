"""HTTP API."""

from datetime import date

from fastapi import FastAPI, HTTPException, Query

from retencja_api.config import HISTORY_YEARS
from retencja_api.crops import CROPS, CROPS_BY_ID
from retencja_api.models import AnalysisReport, Crop, ModuleResult, Parcel, RetentionAnalysis
from retencja_api.parcel.uldk import (
    ParcelNotFound,
    get_parcel_by_id,
    get_parcel_by_point,
    search_parcels,
)
from retencja_api.report import build_report, terrain_module

app = FastAPI(title="Retencja API")


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


@app.get("/api/analysis")
async def analysis(
    parcel_id: str = Query(min_length=5, max_length=64),
    crop: str = Query(),
    analysis_date: date | None = Query(default=None, alias="date"),
) -> AnalysisReport:
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
    return await build_report(parcel, geom, CROPS_BY_ID[crop], analysis_date)


# Polling endpoint for a terrain result that was still pending in the report.
TERRAIN_POLL_BUDGET_S = 2.0


@app.get("/api/terrain")
async def terrain(
    parcel_id: str = Query(min_length=5, max_length=64),
) -> ModuleResult[RetentionAnalysis]:
    try:
        _, geom = await get_parcel_by_id(parcel_id)
    except ParcelNotFound:
        raise HTTPException(404, "Nie znaleziono działki") from None
    return await terrain_module(parcel_id, geom, TERRAIN_POLL_BUDGET_S)
