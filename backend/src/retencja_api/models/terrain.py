"""LIDAR terrain analysis: retention sites, ditches, runoff lines, relief."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from retencja_api.models.common import GeoJSON, Range

SiteKind = Literal["pond", "wet_depression"]


class RetentionSite(BaseModel):
    id: int
    kind: SiteKind
    area_m2: float
    max_depth_m: float
    storage_m3: float  # volume the depression holds before spilling
    catchment_ha: float  # area draining into the depression
    runoff_m3: Range  # inflow from the design rain event
    retained_m3: Range  # min(storage, runoff)
    parcel_share: float  # fraction of the depression area lying on the parcel
    geometry: GeoJSON  # WGS84


class RetentionSummary(BaseModel):
    site_count: int
    storage_m3: float
    retained_m3: Range


class Assumptions(BaseModel):
    dem_source: str
    resolution_m: float
    design_rain_mm: float
    runoff_coeff: Range
    min_depth_m: float
    min_area_m2: float


class DitchWeirs(BaseModel):
    """Weirs proposed on one ditch on or along the parcel."""

    id: int
    kind: str  # OSM waterway type (ditch, drain, canal, stream) or "lidar" if detected
    length_m: float
    slope_pct: float
    weir_count: int
    weir_head_m: float
    channel_m3: float  # held in the ditch behind the weirs
    soil_m3: Range  # held in the soil of both banks by the raised groundwater table
    geometry: GeoJSON  # WGS84 LineString
    weirs: GeoJSON  # WGS84 MultiPoint


class FlowPath(BaseModel):
    """Surface runoff line (downstream direction); width on the map from `area_m2`."""

    area_m2: float  # upstream area draining through the segment
    end: Literal["pool", "exit", "join"]  # pools in a depression, leaves the area, joins `next`
    next: int | None  # index of the downstream segment after a confluence
    geometry: GeoJSON  # WGS84 LineString


class ReliefImage(BaseModel):
    """Shaded micro-relief image of the analysed area, served by /api/terrain/relief.png."""

    corners: list[list[float]]  # WGS84 [lon, lat]: top-left, top-right, bottom-right, bottom-left
    spread_m: float  # colour scale spans ± this height around the local mean


class TerrainSlope(BaseModel):
    """Slope of the parcel surface from LIDAR."""

    mean_pct: float
    p90_pct: float
    steep_share: float  # share of the parcel steeper than 10 % (strong erosion)
    steep_ha: float
    fall_azimuth_deg: int | None  # mean downhill direction, 0 = north, clockwise; None if flat
    relative_height_m: float  # parcel mean elevation minus its surroundings (< 0: lies lower)
    outflow_edge_m: float  # length of the parcel edge over which runoff leaves it
    outflow_area_ha: float  # area draining off over that edge (incl. run-on from upslope)
    runon_area_ha: float  # area outside the parcel whose runoff flows onto it


class RetentionAnalysis(BaseModel):
    parcel_id: str
    computed_at: datetime  # when the terrain data was downloaded and analysed
    summary: RetentionSummary
    sites: list[RetentionSite]
    assumptions: Assumptions
    ditches: list[DitchWeirs] = []
    ditches_checked: bool = False  # False when the OSM ditch map could not be downloaded
    flow: list[FlowPath] = []
    relief: ReliefImage | None = None
    slope: TerrainSlope | None = None
