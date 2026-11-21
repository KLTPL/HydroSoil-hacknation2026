"""Pre-download DEM tiles for demo areas so the live demo answers in seconds.

Usage: uv run python -m retencja_api.warm_cache [area ...]
"""

import asyncio
import sys
import time

from retencja_api.geo import lonlat_to_metric
from retencja_api.terrain.nmt import ensure_tiles, tiles_for_bbox

# Drought-prone farmland (lon, lat centre), side length in metres.
DEMO_AREAS: dict[str, tuple[float, float, float]] = {
    "kujawy-kruszwica": (18.36, 52.70, 3000),
    "wielkopolska-wrzesnia": (17.60, 52.30, 3000),
}


async def warm(name: str) -> None:
    lon, lat, side = DEMO_AREAS[name]
    x, y = lonlat_to_metric(lon, lat)
    half = side / 2
    tiles = tiles_for_bbox(x - half, y - half, x + half, y + half)
    start = time.monotonic()
    print(f"{name}: fetching {len(tiles)} tiles…", flush=True)
    await ensure_tiles(tiles)
    print(f"{name}: done in {time.monotonic() - start:.0f} s", flush=True)


async def _main(names: list[str]) -> None:
    for name in names or DEMO_AREAS:
        await warm(name)


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
