"""Batch analysis of all saved parcels ("Analiza zbiorcza") with the regular report builder.

Parcels run a few at a time (each report already fans out to six upstream services) and
each row is yielded as soon as it is ready, so one slow parcel does not hold up the table.
Slow terrain keeps its usual time budget and is reported as pending."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import date

import httpx

from retencja_api.accounts import archive
from retencja_api.accounts.schemas import BatchRow, SavedParcel
from retencja_api.crops import CROPS_BY_ID
from retencja_api.parcel.uldk import ParcelNotFound, get_parcel_by_id
from retencja_api.report import build_report

log = logging.getLogger(__name__)

BATCH_CONCURRENCY = 2

# Users with a batch in progress; a second one would only double the upstream load.
_running: set[int] = set()


def is_running(user_id: int) -> bool:
    return user_id in _running


def _row(saved: SavedParcel, **fields: object) -> BatchRow:
    return BatchRow(
        saved_id=saved.id,
        parcel_id=saved.parcel_id,
        name=saved.name,
        number=saved.number,
        region=saved.region,
        crop=saved.crop,
        **fields,
    )


async def _analyse(user_id: int, saved: SavedParcel, day: date) -> BatchRow:
    crop = CROPS_BY_ID.get(saved.crop)
    if crop is None:
        return _row(saved, status="error", message="Nieznana uprawa: zmień ją w Moich działkach")
    try:
        parcel, geom = await get_parcel_by_id(saved.parcel_id)
    except ParcelNotFound:
        return _row(saved, status="error", message="Nie znaleziono działki w ULDK")
    except httpx.HTTPError as exc:
        log.warning("Batch: parcel lookup failed for %s: %s", saved.parcel_id, exc)
        return _row(saved, status="error", message="Usługa działek GUGiK nie odpowiada")
    report = await build_report(parcel, geom, crop, day)
    report_id = await asyncio.to_thread(archive.record, user_id, report)
    return _row(
        saved,
        status="ok",
        level=report.diagnosis.level,
        headline=report.diagnosis.headline,
        water_pct=archive.water_pct(report),
        top_recommendation=archive.top_recommendation(report),
        analysed_at=report.generated_at,
        report_id=report_id,
    )


async def run_batch(
    user_id: int, saved: list[SavedParcel], day: date
) -> AsyncIterator[BatchRow]:
    _running.add(user_id)
    limit = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def limited(item: SavedParcel) -> BatchRow:
        async with limit:
            return await _analyse(user_id, item, day)

    tasks = [asyncio.create_task(limited(item)) for item in saved]
    try:
        for next_done in asyncio.as_completed(tasks):
            yield await next_done
    finally:
        # Client went away: stop parcels not started yet (terrain downloads are shared
        # background tasks and keep running).
        for task in tasks:
            task.cancel()
        _running.discard(user_id)
