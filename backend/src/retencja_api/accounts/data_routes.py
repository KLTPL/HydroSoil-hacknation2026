"""Endpoints for a logged-in user's data: saved parcels, report archive, batch analysis.
Every query is scoped to the session's user; another user's ids answer 404."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent

from retencja_api.accounts import archive, batch, parcels
from retencja_api.accounts.deps import current_user, same_origin
from retencja_api.accounts.schemas import (
    ArchivedReport,
    ReportSummary,
    SavedParcel,
    SaveParcel,
    UpdateParcel,
    User,
)
from retencja_api.config import HISTORY_YEARS
from retencja_api.crops import CROPS_BY_ID
from retencja_api.models import GeoJSON
from retencja_api.parcel.uldk import ParcelNotFound, UldkError, get_parcel_by_id

router = APIRouter(prefix="/api/account", tags=["account"])

CurrentUser = Annotated[User, Depends(current_user)]
NOT_FOUND = "Nie znaleziono działki na Twojej liście"
BACKFILL_CONCURRENCY = 4

log = logging.getLogger(__name__)


def _check_crop(crop: str) -> None:
    if crop not in CROPS_BY_ID:
        raise HTTPException(422, "Nieznana uprawa")


async def _fill_missing_outlines(user_id: int, saved: list[SavedParcel]) -> list[SavedParcel]:
    """Parcels saved before the list kept outlines get theirs from ULDK once.
    A failed lookup leaves the thumbnail out; the next listing tries again."""
    missing = [s for s in saved if s.geometry is None]
    if not missing:
        return saved
    limit = asyncio.Semaphore(BACKFILL_CONCURRENCY)

    async def outline(s: SavedParcel) -> tuple[int, GeoJSON | None]:
        async with limit:
            try:
                parcel, _ = await get_parcel_by_id(s.parcel_id)
            except (ParcelNotFound, UldkError, httpx.HTTPError) as err:
                log.warning("No outline for saved parcel %s: %s", s.parcel_id, err)
                return s.id, None
        return s.id, parcel.geometry

    found = {i: g for i, g in await asyncio.gather(*map(outline, missing)) if g is not None}
    if found:
        parcels.set_geometries(user_id, found)
    return [s.model_copy(update={"geometry": found[s.id]}) if s.id in found else s for s in saved]


@router.get("/parcels")
async def list_parcels(user: CurrentUser) -> list[SavedParcel]:
    return await _fill_missing_outlines(user.id, parcels.list_parcels(user.id))


@router.post("/parcels", status_code=201, dependencies=[Depends(same_origin)])
async def save_parcel(body: SaveParcel, user: CurrentUser) -> SavedParcel:
    _check_crop(body.crop)
    try:
        parcel, _ = await get_parcel_by_id(body.parcel_id)
    except ParcelNotFound:
        raise HTTPException(404, "Nie znaleziono działki") from None
    try:
        return parcels.save_parcel(user.id, parcel, body.crop, (body.name or "").strip() or None)
    except parcels.AlreadySaved:
        raise HTTPException(409, "Ta działka jest już na Twojej liście") from None
    except parcels.TooManyParcels:
        limit = parcels.MAX_SAVED_PARCELS
        raise HTTPException(409, f"Możesz zapisać najwyżej {limit} działek") from None


@router.patch("/parcels/{saved_id}", dependencies=[Depends(same_origin)])
def update_parcel(saved_id: int, body: UpdateParcel, user: CurrentUser) -> SavedParcel:
    if body.crop is not None:
        _check_crop(body.crop)
    name = (body.name or "").strip() or None
    updated = parcels.update_parcel(
        user.id, saved_id, body.crop, name, set_name="name" in body.model_fields_set
    )
    if updated is None:
        raise HTTPException(404, NOT_FOUND)
    return updated


@router.delete("/parcels/{saved_id}", status_code=204, dependencies=[Depends(same_origin)])
def delete_parcel(saved_id: int, user: CurrentUser) -> None:
    if not parcels.delete_parcel(user.id, saved_id):
        raise HTTPException(404, NOT_FOUND)


@router.get("/reports")
def list_reports(
    user: CurrentUser, parcel_id: str | None = Query(default=None, max_length=64)
) -> list[ReportSummary]:
    return archive.list_reports(user.id, parcel_id)


@router.get("/reports/{report_id}")
def get_report(report_id: int, user: CurrentUser) -> ArchivedReport:
    found = archive.get_report(user.id, report_id)
    if found is None:
        raise HTTPException(404, "Nie znaleziono raportu w Twoim archiwum")
    return found


def batch_inputs(
    user: CurrentUser, day: date | None = Query(default=None, alias="date")
) -> tuple[User, date]:
    """Validated before the stream starts (a streamed response has already sent 200)."""
    today = date.today()
    day = day or today
    try:
        earliest = today.replace(year=today.year - HISTORY_YEARS)
    except ValueError:  # 29 February → 28 February
        earliest = today.replace(year=today.year - HISTORY_YEARS, day=28)
    if not earliest <= day <= today:
        raise HTTPException(422, f"Data analizy musi mieścić się między {earliest:%d.%m.%Y} a dziś")
    if batch.is_running(user.id):
        raise HTTPException(409, "Analiza zbiorcza już trwa. Poczekaj na jej wynik.")
    return user, day


@router.get("/batch/stream", response_class=EventSourceResponse)
async def batch_stream(
    inputs: Annotated[tuple[User, date], Depends(batch_inputs)],
) -> AsyncIterator[ServerSentEvent]:
    """A `row` event per saved parcel as soon as its analysis is ready, then `done`."""
    user, analysis_date = inputs
    saved = parcels.list_parcels(user.id)
    async for row in batch.run_batch(user.id, saved, analysis_date):
        yield ServerSentEvent(event="row", data=row)
    yield ServerSentEvent(event="done", data={"count": len(saved)})
