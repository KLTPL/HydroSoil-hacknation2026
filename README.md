# Zatrzymaj wodę

HackNation 2026 — KOWR challenge "Zatrzymaj wodę, chroń plony".
Team: _TODO team name_

**Live:** https://woda.kodlab.pl · example report:
https://woda.kodlab.pl/#p=040706_5.0016.51%2F1&c=zboza_ozime&d=2025-06-15

A farmer enters a cadastral parcel number (or clicks the map / uses GPS), picks the crop and
the analysis date (today or up to 10 years back) and gets, in about 30 seconds, a report that
answers three questions:

1. **Is there a water shortage on my parcel now, and how unusual is it?** Climatic water
   balance and a root-zone soil water model for the crop, compared with the same date in the
   previous 10 years, cross-checked with satellite canopy moisture and reanalysis soil moisture.
2. **Why?** Causes quantified in millimetres of water: rain deficit, extra evaporation, low soil
   water capacity, little organic matter, runoff leaving the field, hydrological drought.
3. **What can I do on this parcel?** Recommendations with the amount of water they keep
   (m³), why (the numbers behind them), when, cost and formalities. The differentiator is the
   **retention map from 1 m LIDAR**: terrain depressions where water can be held, and
   **ditches detected in the terrain model with a weir (zastawka) plan** spaced by the ditch
   gradient.

The report can be printed or saved as PDF, and lists every data source with its licence and
download time, plus limitations and missing data.

---

## 1. How to run

**No installation:** open https://woda.kodlab.pl in any current browser (Chrome, Firefox, Edge,
Safari, Opera; desktop or phone).

Run locally with Docker:

```sh
docker compose up --build        # http://localhost:8080
```

Local development:

```sh
cd backend && uv run uvicorn retencja_api.api:app --reload   # API on :8000
cd frontend && pnpm install && pnpm dev                      # UI on :5173, proxies /api
```

Production (HTTPS via Caddy; set the domain in `deploy/Caddyfile`):

```sh
docker compose -f docker-compose.yml -f deploy/compose.prod.yml up -d --build
```

Deep link format (opens a parcel and runs the analysis):
`/#p=<parcel id>&c=<crop id>&d=<YYYY-MM-DD>`. Crop ids: `GET /api/crops`.

Optional: pre-compute terrain for demo parcels so a live demo answers instantly:

```sh
cd backend && uv run python -m retencja_api.warm_cache [parcel_id ...]
```

## 2. Features

| Step | What the farmer gets |
|---|---|
| Parcel | Search by full id (`040706_5.0016.51/1`) or region + number (`Karczyn 51/1`); map click; GPS. Parcel outline on orthophoto with cadastral overlay. |
| Inputs | Crop (14 crop groups of the IUNG drought monitoring) and analysis date (today … 10 years back). |
| Assessment | 4-level verdict (none / watch / moderate / severe) with the evidence: plant-available water in the root zone, 60-day climatic water balance (KBW), hot days, satellite NDMI/NDVI, reanalysis soil moisture, IMGW hydrological drought warnings, each ranked against 10 earlier years. Confidence level. |
| Causes | Ranked, in mm: rain deficit, extra evaporation, low soil capacity, organic matter, runoff, hydrological drought. |
| Recommendations | Irrigation dose (only when the crop is stressed), weirs on ditches, ponds / wet meadows in depressions, organic matter, mulch / reduced tillage, variety and sowing date. Each with m³ effect, data justification, timing, cost and formalities. |
| Retention map | Depressions (pond / wet meadow) with storage, catchment and retained volume per design rain; ditches (LIDAR + OpenStreetMap) with proposed weir points. |
| Risk calendar | In how many of the last 10 years the crop had ≥ 15 days of strong water stress, per month April–September. |
| Report | Print / save as PDF (A4, map snapshot, sources with URLs); shareable link. |
| Honesty | Every source with licence and download time; missing data stated explicitly; warning if the parcel is not farmland (ESA WorldCover). |

## 3. Architecture

```
Browser (React + MapLibre)  ──HTTPS──>  Caddy  ──>  nginx (static UI, /api proxy)
                                                     │
                                                     └─>  FastAPI backend (Python)
                                                           ├─ parcel: ULDK GUGiK
                                                           ├─ modules run concurrently, each within a time budget:
                                                           │   water   Open-Meteo / NASA POWER → KBW + FAO-56 soil water balance
                                                           │   soil    SoilGrids WCS → texture, IUNG category, water capacity
                                                           │   satellite  Sentinel-2 L2A (Planetary Computer STAC + COG) → NDVI/NDMI
                                                           │   hydro   IMGW warnings API
                                                           │   land    ESA WorldCover → farmland check
                                                           │   terrain NMT WCS (LIDAR) → depressions, catchments, ditches, weirs
                                                           ├─ diagnosis + recommendations (pure functions over module results)
                                                           └─ file cache (responses and analyses)
```

- Every module returns `ok | pending | unavailable` with a plain-language reason, its sources
  and duration. A failing source never breaks the report; it is listed under missing data.
- Slow modules (terrain, satellite) get 25 s. If they are not ready, the report is returned
  anyway with the section "pending", the computation continues in the background and the
  browser polls until the result appears.
- No database and no user accounts; results are cached as files.

Code: `backend/src/retencja_api/` (`api.py`, `report.py`, `modules.py`, `assessment/`,
`meteo/`, `soil/`, `satellite/`, `hydro/`, `landcover/`, `terrain/`), `frontend/src/`.

### Methods

| Topic | Method |
|---|---|
| Climatic water balance (KBW) | Precipitation − FAO-56 reference evapotranspiration ET0 over 60 days (six 10-day periods, as in the IUNG agricultural drought monitoring). |
| Soil water | Daily root-zone bucket, FAO-56 single crop coefficient (Allen et al.): Kc curve per crop with typical Polish stage dates, root depth, depletion fraction p; total available water = available water capacity × root depth; stress coefficient Ks. Spin-up from November of the year before the oldest compared year. |
| Available water capacity | Saxton & Rawls (2006) pedotransfer from SoilGrids sand, clay and organic carbon, 0–100 cm. |
| IUNG soil category | Texture-based approximation: I (loose/slightly loamy sand) … IV (medium/heavy loam, clay). |
| Verdict | Absolute crop stress (available water below (1 − p)) graded by independent dryness signals: soil water model, KBW, reanalysis soil moisture (ERA5-Land or MERRA-2), satellite NDMI. "Dry" = among the 3 driest of ~11 years or ≥ 15 % below normal. |
| Strong stress / risk calendar | Ks < 0.5; month counts as dry with ≥ 15 such days. Calibrated so that the known drought summers 2015, 2018, 2019 stand out. |
| Satellite | Sentinel-2 L2A, most recent scene with ≥ 60 % of the parcel cloud-free (SCL mask) in the 20 days before the date; same window in each earlier year since 2017. NDVI = (B08−B04)/(B08+B04), NDMI = (B08−B11)/(B08+B11), 20 m grid, BOA offset handled. |
| Depressions | Priority-flood fill (Barnes et al. 2014) on the 1 m LIDAR DTM resampled to 2 m; D8 flow; depressions ≥ 0.15 m deep and ≥ 300 m², ≥ 30 % on the parcel. Retained water = min(storage, catchment × 30 mm × runoff coefficient 0.05–0.25). |
| Ditches | Cells ≥ 0.25 m below the 20 m neighbourhood mean that drain ≥ 0.2 ha, traced downstream along D8 into lines; OSM waterways added when available. |
| Weirs | Head 0.5 m; spacing = head / ditch gradient (≥ 50 m), so each backwater reaches the next weir. Water held in the ditch plus groundwater rise in a 2 × 50 m bank strip (mean rise 0.25 m × specific yield 0.05–0.15). |
| Recommendation effects | Irrigation: refill of the root-zone deficit. Mulch: 25–50 % of bare-soil evaporation (Kc 0.3 × ET0 from sowing to canopy closure, 10-year mean). Organic matter: +0.5–1 % in the 0.3 m plough layer via Saxton & Rawls. |

## 4. Data sources and coverage

| Data | Source | Resolution / period | Access |
|---|---|---|---|
| Parcels (id, geometry, admin units) | ULDK, GUGiK | cadastral, current | API, no key |
| Cadastral overlay, orthophoto | KIEG WMS, Geoportal ORTO WMS (GUGiK) | — | WMS, no key |
| Terrain | NMT GRID1, GUGiK (LIDAR) | 1 m, resampled to 2 m; parcel bbox + 60 m | WCS, no key |
| Weather (primary) | Open-Meteo Historical Weather API (ERA5, ERA5-Land, ECMWF IFS) | ~10 km (0.1° cell); daily; analysis date − 11 years … date | API, no key |
| Weather (fallback) | NASA POWER (MERRA-2) | ~50 km; daily; same period | API, no key |
| Soil | SoilGrids 2.0, ISRIC | 250 m; 0–100 cm in 5 layers | WCS, no key |
| Satellite | Copernicus Sentinel-2 L2A via Microsoft Planetary Computer | 10–20 m; 2017 … date | STAC + COG, anonymous SAS token |
| Land cover | ESA WorldCover 2021 via Planetary Computer | 10 m; 2021 | STAC + COG |
| Hydrological drought | IMGW-PIB public data API, `warningshydro` | per voivodeship / catchment; current only | API, no key |
| Ditches (supplementary) | OpenStreetMap via Overpass API | — | API, no key |

## 5. Live vs. pre-downloaded data

**All results are computed by the application at request time** from the data above. There are
no pre-computed recommendations and no bundled datasets.

Downloaded data is cached on the server so repeated requests are fast and free quotas are not
exhausted. Each report lists, per source, whether it was **"pobrane teraz"** (downloaded for
this request) or **"z pamięci podręcznej"** (cached), with the original download time.

| Data | Cache policy |
|---|---|
| Parcel (ULDK) | Cached per parcel id. |
| Terrain analysis (NMT) | Cached per parcel and analysis version; terrain does not change between dates. |
| Weather history | Cached per 0.1° cell up to the end of the last settled month; days since then are always downloaded live. |
| Soil, land cover | Cached per parcel bounding box / parcel id (static datasets). |
| Sentinel-2 indices | Earlier years cached per parcel and date (archive does not change); the current month is always downloaded live. |
| IMGW warnings | Always live. |

Demo parcels were pre-warmed on 21.11.2026 with `warm_cache` (terrain only).

## 6. Libraries, components, services and AI tools

| Component | Version | Licence | Use |
|---|---|---|---|
| Python | 3.12 | PSF | backend runtime |
| FastAPI | 0.165 | MIT | HTTP API |
| Pydantic | 2.14 | MIT | data models |
| Uvicorn | 0.54 | BSD-3-Clause | ASGI server |
| HTTPX | 0.28 | BSD-3-Clause | HTTP client |
| NumPy | 2.5 | BSD-3-Clause | grid computations |
| Rasterio (+ bundled GDAL) | 1.5 | BSD-3-Clause (GDAL: MIT) | GeoTIFF / COG reading, rasterising |
| Shapely | 2.2 | BSD-3-Clause | geometry |
| pyproj (+ PROJ) | 3.8 | MIT | coordinate transformations |
| affine | 3.0 | BSD-3-Clause | raster transforms |
| pytest, pytest-asyncio, Ruff | 9.2, 1.5, 0.17 | MIT | tests, lint (dev only) |
| React, React DOM | 19.3 | MIT | UI |
| MapLibre GL JS | 6.19 | BSD-3-Clause | map |
| Vite, TypeScript, oxlint | 8.3, 7.0, 1.90 | MIT, Apache-2.0, MIT | build, lint (dev only) |
| nginx | 1.29 | BSD-2-Clause | static files, API proxy |
| Caddy | 2.10 | Apache-2.0 | HTTPS (Let's Encrypt) |
| Docker / Docker Compose | — | Apache-2.0 | packaging |
| Oracle Cloud Always Free (Ampere A1, 4 OCPU / 24 GB) | — | free tier | hosting |

External services: see section 4 (all free, no API keys).

**AI tools.** The code, tests and documentation were written with **Claude Code (Anthropic,
model Claude Opus)** as a coding assistant, under the team's direction and review. The running
application uses **no AI or machine-learning model**: every number in the report comes from
deterministic, documented calculations (section 3) on the source data, so results are
reproducible and explainable.

## 7. Licences and terms of use

| Data / service | Terms |
|---|---|
| GUGiK (ULDK, NMT, ortofotomapa, KIEG) | Free of charge, Art. 40a of the Polish Geodetic and Cartographic Law. |
| Open-Meteo | Data CC BY 4.0; the free API is for non-commercial use. Commercial use: paid API plan or the NASA POWER fallback. |
| NASA POWER | Public NASA data, no restrictions; attribution requested. |
| SoilGrids (ISRIC) | CC BY 4.0. |
| Copernicus Sentinel-2 | Free, full and open (Regulation (EU) 1159/2013); "Contains modified Copernicus Sentinel data". |
| Microsoft Planetary Computer | Free access; data under the licences of the datasets. |
| ESA WorldCover | CC BY 4.0, © ESA WorldCover project. |
| IMGW-PIB public data | Free; source must be credited ("Źródłem danych jest IMGW-PIB"). |
| OpenStreetMap | ODbL, © OpenStreetMap contributors. |
| Code | Written during the event; all dependencies are permissive open-source licences (section 6), compatible with KOWR's use of the solution. |

## 8. Known limitations

- **Weather is gridded reanalysis** (~10 km Open-Meteo, ~50 km NASA POWER), not a station on
  the field. Local convective rain can be missed.
- **Open-Meteo free quota is per IP and per day.** When exceeded, the app switches to NASA
  POWER automatically. Its ET0 (own FAO-56 calculation) is ~10 % lower than Open-Meteo's,
  but comparisons with earlier years stay consistent because both sides use the same source.
- **Soil is modelled** (SoilGrids, 250 m), not sampled; the IUNG category is an approximation
  from texture, not the official IUNG soil susceptibility map.
- **The soil water model** has no groundwater, tile drainage or irrigation, and uses typical
  stage dates, not the farmer's sowing date.
- **Drought thresholds approximate the IUNG method**; they are not the official IUNG SMSR
  verdict. Calibrated on known drought years, verified on a small set of parcels.
- **Terrain:** the GUGiK WCS takes ~10 s plus ~20–40 s per km², so terrain for parcels above a
  few hectares may arrive after the report (the page updates itself). Parcels over 250 ha skip
  terrain. The LIDAR model is from the national scanning campaign, not today's surface.
- **Ditch detection** can also mark natural flow furrows or road ditches; weir spacing and
  groundwater effect use typical values (0.5 m head, 50 m influence, specific yield 0.05–0.15).
- **Sentinel-2** needs a mostly cloud-free scene in the 20 days before the date; otherwise that
  year is listed as missing.
- **IMGW hydrological warnings** exist only for the current day (no archive), matched by
  voivodeship.
- **Land cover** (farmland check) is from 2021.
- **Formalities** in recommendations (water-law notification, ditch owners) are general
  guidance, not legal advice.

## 9. How results are verified

- **Independent cross-checks in every report:** the soil water model is compared with
  reanalysis soil moisture (ERA5-Land or MERRA-2) and Sentinel-2 NDMI for the same date and
  history. Agreement raises, disagreement lowers the stated confidence.
- **Ranking against 10 earlier years** instead of absolute thresholds only: model biases cancel
  out, and the farmer can check the years they remember (e.g. 2018, 2019) in the charts.
- **Calibration:** the strong-stress threshold was set so that known Polish drought summers
  (2015, 2018, 2019) stand out and wet 2017 does not (checked on a Kujawy parcel).
- **Spot checks:** detected ditches and depressions compared with the orthophoto; NASA POWER
  ET0 vs Open-Meteo (correlation 0.98); Sentinel-2 dry spring 2025 (NDMI lowest in 8 years) vs
  the known 2025 drought.
- **Automated tests** (`cd backend && uv run pytest`, 51 tests): FAO-56 radiation against
  the FAO worked example, Penman-Monteith plausibility, soil water balance behaviour,
  ranking, pedotransfer, soil categories, depression filling, retention volumes, ditch
  detection and weir spacing on synthetic terrain, recommendations, report degradation when
  sources fail.
- **Traceability:** every source is linked in the report with its licence and download time, so
  each input can be re-checked by hand.

Checks:

```sh
cd backend && uv run pytest && uv run ruff check .
cd frontend && pnpm build && pnpm lint
```

## Scalability and cost

- **Quotas and availability:** all upstream responses are cached (static data per parcel,
  weather per 0.1° cell, archive imagery per parcel and date); weather falls back to NASA
  POWER, ditches fall back to LIDAR-only detection; slow modules are time-boxed and finish in
  the background. One in-flight computation per parcel is shared by parallel requests.
- **At national scale:** pre-compute the terrain analysis for all arable parcels (the slowest
  part, independent of the date) from the national LIDAR DTM tiles instead of the WCS; run the
  weather and soil water balance on a national grid daily (a few thousand cells); store results
  in PostGIS/object storage; run several stateless backend instances behind a load balancer.
- **Costs:** the prototype runs on Oracle Cloud Always Free (0 PLN). A national service would
  need a commercial weather licence (Open-Meteo API from ~€30/month, or own ERA5-Land
  processing via Copernicus CDS, free) and ~2–4 cloud VMs plus storage for the pre-computed
  terrain (on the order of hundreds of PLN per month). All other data sources are free.

## Security and privacy

- No accounts, no personal data collected; the parcel number is public cadastral data.
- HTTPS only (HTTP redirects to HTTPS); input validated (parcel id length, date range, known
  crop ids); external calls are read-only.
- The browser asks for location only when the user taps the GPS button; the position is sent
  only to look up the parcel. The application does not store it (it appears only in the
  server's rotating access log).
