"""Pre-compute terrain analyses for demo parcels so a live demo answers instantly.

Usage: uv run python -m retencja_api.warm_cache [parcel_id ...]
"""

import asyncio
import sys
import time

from retencja_api.parcel.uldk import get_parcel_by_id
from retencja_api.terrain.service import analyze_parcel, cached_analysis

DEMO_PARCELS = [
    "040706_5.0016.51/1",  # Kujawy, gm. Kruszwica
    "141804_5.0029.14/108",  # Mazowsze, gm. Piaseczno
]


async def warm(parcel_id: str) -> None:
    if cached_analysis(parcel_id) is not None:
        print(f"{parcel_id}: already cached", flush=True)
        return
    start = time.monotonic()
    _, geom = await get_parcel_by_id(parcel_id)
    result = await analyze_parcel(parcel_id, geom)
    took = time.monotonic() - start
    print(f"{parcel_id}: {result.summary.site_count} sites in {took:.0f} s", flush=True)


async def _main(parcel_ids: list[str]) -> None:
    for parcel_id in parcel_ids or DEMO_PARCELS:
        await warm(parcel_id)


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
