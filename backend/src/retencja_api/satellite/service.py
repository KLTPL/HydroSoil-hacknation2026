"""Vegetation state on the analysis date against the same season in earlier years."""

import asyncio
from datetime import date

import httpx
import numpy as np

from retencja_api.assessment.water_balance import compare, same_date
from retencja_api.cache import read_json, write_json
from retencja_api.models import VegetationObservation, VegetationState
from retencja_api.satellite.sentinel import (
    READ_CONCURRENCY,
    WINDOW_DAYS,
    SceneIndices,
    best_indices,
    fetch_token,
)

FIRST_YEAR = 2017  # full Sentinel-2 L2A coverage of Poland (2A + 2B)


async def _year_observation(
    client: httpx.AsyncClient,
    geometry: dict,
    day: date,
    token: str,
    semaphore: asyncio.Semaphore,
    cache_key: str,
) -> SceneIndices | None:
    final = day < date.today().replace(day=1)  # older imagery does not change
    cached = read_json("sentinel2", cache_key) if final else None
    if cached is not None:
        return SceneIndices(date.fromisoformat(cached["day"]), *cached["values"]) if cached[
            "found"
        ] else None
    result = await best_indices(client, geometry, day, token, semaphore)
    if final:
        payload = (
            {"found": True, "day": result.day.isoformat(),
             "values": [result.ndvi, result.ndmi, result.clear_pct]}
            if result
            else {"found": False}
        )
        write_json("sentinel2", cache_key, payload)
    return result


async def vegetation_state(
    parcel_id: str, geometry_wgs84: dict, day: date, years: int
) -> VegetationState:
    semaphore = asyncio.Semaphore(READ_CONCURRENCY)
    target_years = [y for y in range(day.year - years, day.year + 1) if y >= FIRST_YEAR]
    async with httpx.AsyncClient(timeout=20) as client:
        token = await fetch_token(client)
        results = await asyncio.gather(
            *(
                _year_observation(
                    client,
                    geometry_wgs84,
                    same_date(day, year),
                    token,
                    semaphore,
                    f"{parcel_id}:{same_date(day, year)}",
                )
                for year in target_years
            )
        )
    observations = {
        year: VegetationObservation(
            year=year,
            date=r.day,
            ndvi=round(r.ndvi, 3),
            ndmi=round(r.ndmi, 3),
            clear_pct=round(r.clear_pct),
        )
        for year, r in zip(target_years, results, strict=True)
        if r is not None and np.isfinite(r.ndvi)
    }
    current = observations.get(day.year)
    ndvi = ndmi = None
    if current is not None and len(observations) > 1:
        ndvi = compare({y: o.ndvi for y, o in observations.items()}, day.year)
        ndmi = compare({y: o.ndmi for y, o in observations.items()}, day.year)
    return VegetationState(
        current=current,
        history=[o for y, o in sorted(observations.items()) if y != day.year],
        ndvi=ndvi,
        ndmi=ndmi,
        window_days=WINDOW_DAYS,
        missing_years=[y for y in target_years if y not in observations],
    )
