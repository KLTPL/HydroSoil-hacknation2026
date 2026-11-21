# Zatrzymaj wodę

HackNation 2026 — KOWR challenge "Zatrzymaj wodę, chroń plony".

Find a cadastral parcel (parcel ID, region name + number, map click or GPS), choose the crop
and the analysis date (today or up to 10 years back), and see where water can be retained on it:
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

Deep link that opens a parcel and runs the analysis:
`http://localhost:5173/#p=040706_5.0016.51%2F1&c=zboza_ozime&d=2025-06-15`.

## Terrain data speed

The GUGiK NMT WCS needs ~10 s plus ~20–40 s per km², independent of output resolution.
Only the parcel bounding box (+60 m) is requested. If terrain is not ready within 25 s the
report returns with the terrain section `pending`; the download continues in the background
and the frontend polls `/api/terrain` until it is ready. Results are cached per parcel.

Pre-compute demo parcels before a presentation:

```sh
cd backend && uv run python -m retencja_api.warm_cache [parcel_id ...]   # defaults in warm_cache.py
```

## How it works

| Step | Source / method |
|---|---|
| Parcel lookup | ULDK (GUGiK) `GetParcelByIdOrNr` / `GetParcelByXY` / `GetParcelById` |
| Parcel overlay | KIEG WMS (GUGiK), orthophoto WMS |
| Terrain | NMT GRID1 WCS (GUGiK, 1 m LIDAR), resampled server-side to 2 m |
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
