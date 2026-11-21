"""Shared building blocks: parcel, ranges, module results and year comparisons."""

from datetime import datetime
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


class YearValue(BaseModel):
    year: int
    value: float


class Comparison(BaseModel):
    """A value at the analysis date against the same calendar date in earlier years."""

    value: float
    normal: float  # mean of earlier years
    rank: int  # 1 = lowest of all years incl. the analysed one
    years: int  # number of years ranked
    history: list[YearValue]  # earlier years, oldest first
