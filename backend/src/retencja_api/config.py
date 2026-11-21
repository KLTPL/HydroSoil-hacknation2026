"""Service endpoints, analysis parameters and cache location."""

import os
from pathlib import Path

ULDK_URL = "https://uldk.gugik.gov.pl/"
NMT_WCS_URL = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
)
NMT_COVERAGE_ID = "DTM_PL-KRON86-NH_TIFF"

# Polish national grid (PL-1992); NMT, ULDK and all metric computations use it.
CRS_METRIC = 2180
CRS_WGS84 = 4326

CACHE_DIR = Path(os.environ.get("RETENCJA_CACHE_DIR", Path(__file__).parents[2] / ".cache"))

# DEM tiles are fetched on an aligned grid so neighbouring parcels share the cache.
DEM_TILE_SIZE_M = 500
DEM_FETCH_CONCURRENCY = 4
DEM_FETCH_ATTEMPTS = 4
DEM_FETCH_TIMEOUT_S = 180.0

# Analysis grid: 1 m LIDAR is block-averaged to this resolution (speed, less noise).
ANALYSIS_RESOLUTION_M = 2
# Terrain around the parcel included so upslope runoff and spill paths are visible.
PARCEL_BUFFER_M = 150

# Depressions smaller than this are treated as LIDAR noise or micro-relief.
MIN_DEPRESSION_DEPTH_M = 0.15
MIN_DEPRESSION_AREA_M2 = 300.0
# Depth from which a depression is worth turning into a pond rather than a wet meadow.
POND_MIN_DEPTH_M = 0.5

# Design rain event and runoff coefficient range for arable land (low → high runoff).
DESIGN_RAIN_MM = 30.0
RUNOFF_COEFF_RANGE = (0.05, 0.25)

# Bump when analysis logic changes so cached results are recomputed.
ANALYSIS_VERSION = 2
