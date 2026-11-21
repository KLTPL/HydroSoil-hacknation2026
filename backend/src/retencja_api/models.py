"""API response models (shared contract with the frontend)."""

from datetime import date, datetime
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
    computed_at: datetime  # when the terrain data was downloaded and analysed
    summary: RetentionSummary
    sites: list[RetentionSite]
    assumptions: Assumptions


class Crop(BaseModel):
    id: str
    name: str


class DataSource(BaseModel):
    name: str
    url: str
    license: str
    retrieved: Literal["live", "cached"]
    retrieved_at: datetime


ModuleStatus = Literal["ok", "pending", "unavailable"]


class ModuleResult[T](BaseModel):
    """One analysis step. Missing data is reported, never silently filled in."""

    status: ModuleStatus
    message: str | None = None  # why data is pending or unavailable (shown to the farmer)
    data: T | None = None
    sources: list[DataSource] = []
    duration_ms: int


class AnalysisReport(BaseModel):
    parcel: Parcel
    crop: Crop
    analysis_date: date
    generated_at: datetime
    terrain: ModuleResult[RetentionAnalysis]
