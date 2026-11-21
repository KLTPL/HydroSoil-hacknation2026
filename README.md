# Zatrzymaj wodę

HackNation 2026 — KOWR challenge "Zatrzymaj wodę, chroń plony".

Pick a cadastral parcel (map click or GPS) and see where water can be retained on it:
terrain depressions from 1 m LIDAR, how much they hold, how much runoff reaches them
from a design rain, and what to do with each site.

## Run

```sh
docker compose up --build        # http://localhost:8080
```

Local development:

```sh
cd backend && uv run uvicorn retencja_api.api:app --reload   # :8000
cd frontend && pnpm install && pnpm dev                      # :5173, proxies /api
```

Deep link to a parcel: `http://localhost:5173/#52.70,18.36` (lat,lon).

## Demo areas

The NMT WCS takes ~20 s per 500 m tile, so demo areas are pre-downloaded:

```sh
cd backend && uv run python -m retencja_api.warm_cache    # areas in warm_cache.py
```

| Area | Link |
|---|---|
| Kujawy, gm. Kruszwica | `#52.70,18.36` |
| Wielkopolska, near Września | `#52.30,17.60` |

## How it works

| Step | Source / method |
|---|---|
| Parcel lookup | ULDK (GUGiK) `GetParcelByXY` / `GetParcelById` |
| Parcel overlay | KIEG WMS (GUGiK), orthophoto WMS |
| Terrain | NMT GRID1 WCS (GUGiK, 1 m LIDAR), block-averaged to 2 m |
| Depressions | Priority-flood fill (Barnes 2014); depth = filled − terrain |
| Catchment | D8 steepest descent on the filled surface; cells whose path first reaches the depression |
| Retained water | min(storage, catchment × 30 mm × runoff coefficient 0.05–0.25) |

Results are estimates shown as ranges. Not modelled: tile drainage, groundwater, infiltration
during the event. Thresholds live in `backend/src/retencja_api/config.py`.

## Checks

```sh
cd backend && uv run pytest && uv run ruff check .
cd frontend && pnpm build && pnpm lint
```
