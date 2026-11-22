"""Service endpoints, analysis parameters and cache location."""

import os
from pathlib import Path

ULDK_URL = "https://uldk.gugik.gov.pl/"
NMT_WCS_URL = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
)
NMT_COVERAGE_ID = "DTM_PL-KRON86-NH_TIFF"
# Index of the pre-cut NMT sheets (static .asc files on opendata.geoportal.gov.pl).
NMT_SHEET_INDEX_URL = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WMS/SkorowidzeUkladEVRF2007"
)
NMT_SHEET_LAYERS = (
    "SkorowidzeNMT2023iStarsze",
    "SkorowidzeNMT2024",
    "SkorowidzeNMT2025",
    "SkorowidzeNMT2026",
)

# Polish national grid (PL-1992); NMT, ULDK and all metric computations use it.
CRS_METRIC = 2180
CRS_WGS84 = 4326

CACHE_DIR = Path(os.environ.get("RETENCJA_CACHE_DIR", Path(__file__).parents[2] / ".cache"))

# Optional user accounts (saved parcels, report archive). Kept apart from the cache, which
# may be wiped at any time; in Docker this path lives on a named volume.
ACCOUNTS_DB_PATH = Path(
    os.environ.get("RETENCJA_DB_PATH", Path(__file__).parents[2] / ".data" / "accounts.sqlite3")
)
# Session cookies are marked Secure when served over HTTPS (production behind Caddy).
SECURE_COOKIES = os.environ.get("RETENCJA_SECURE_COOKIES", "0") == "1"

# WCS time grows with requested area; larger areas are split into concurrent strips.
DEM_STRIP_MAX_M2 = 250_000
DEM_FETCH_CONCURRENCY = 4
DEM_FETCH_ATTEMPTS = 4
DEM_FETCH_TIMEOUT_S = 180.0
# Sheets (~35 MB each) are throttled per connection (~0.3 MB/s), so they are fetched
# as parallel byte ranges.
DEM_SHEET_CHUNK_BYTES = 2_000_000
DEM_SHEET_CONCURRENCY = 16
DEM_SHEET_TIMEOUT_S = 60.0
# Sheets are ~2.2 × 2.3 km; index points this far apart cannot miss one.
DEM_SHEET_PROBE_STEP_M = 1000

# Analysis grid: 1 m LIDAR is block-averaged to this resolution (speed, less noise).
ANALYSIS_RESOLUTION_M = 2
# Terrain around the parcel included so upslope runoff and spill paths are visible.
PARCEL_BUFFER_M = 60

# Terrain results later than this are reported as pending; the download keeps
# running in the background and fills the cache for the next request.
TERRAIN_TIME_BUDGET_S = 25.0
# Larger parcels would take minutes to download and analyse; terrain is skipped for them.
TERRAIN_MAX_AREA_HA = 250.0

# Analysis dates accepted: today and up to this many years back.
HISTORY_YEARS = 10

# Depressions smaller than this are treated as LIDAR noise or micro-relief.
MIN_DEPRESSION_DEPTH_M = 0.15
MIN_DEPRESSION_AREA_M2 = 300.0
# Depth from which a depression is worth turning into a pond rather than a wet meadow.
POND_MIN_DEPTH_M = 0.5

# Design rain event and runoff coefficient range for arable land (low → high runoff).
DESIGN_RAIN_MM = 30.0
RUNOFF_COEFF_RANGE = (0.05, 0.25)

# Bump when analysis logic changes so cached results are recomputed.
ANALYSIS_VERSION = 10
