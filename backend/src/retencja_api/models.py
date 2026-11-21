"""API response models (shared contract with the frontend)."""

from typing import Any, Literal

from pydantic import BaseModel

GeoJSON = dict[str, Any]


class Parcel(BaseModel):
    id: str
    voivodeship: str
    county: str
    commune: str
    region: str
    number: str
    area_ha: float
    geometry: GeoJSON  # WGS84


class Range(BaseModel):
    low: float
    high: float


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


class RetentionAnalysis(BaseModel):
    parcel_id: str
    summary: RetentionSummary
    sites: list[RetentionSite]
    assumptions: Assumptions
