"""HTTP API."""

from fastapi import FastAPI, HTTPException, Query

from retencja_api.models import Parcel, RetentionAnalysis
from retencja_api.parcel.uldk import ParcelNotFound, get_parcel_by_id, get_parcel_by_point
from retencja_api.terrain.service import analyze_parcel

app = FastAPI(title="Retencja API")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/parcels/at")
async def parcel_at(
    lat: float = Query(ge=48.5, le=55.0), lon: float = Query(ge=13.5, le=24.5)
) -> Parcel:
    try:
        parcel, _ = await get_parcel_by_point(lon, lat)
    except ParcelNotFound:
        raise HTTPException(404, "Brak działki ewidencyjnej w tym miejscu") from None
    return parcel


@app.get("/api/retention")
async def retention(parcel_id: str = Query(min_length=5, max_length=64)) -> RetentionAnalysis:
    try:
        _, geom = await get_parcel_by_id(parcel_id)
    except ParcelNotFound:
        raise HTTPException(404, "Nie znaleziono działki") from None
    return await analyze_parcel(parcel_id, geom)
