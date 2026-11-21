"""Diagnosis, recommendations and the full parcel report."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from retencja_api.models.common import Crop, ModuleResult, Parcel, Range
from retencja_api.models.field import (
    EdoDrought,
    HydroStatus,
    LandCover,
    SoilProfile,
    VegetationState,
    WaterBalance,
)
from retencja_api.models.terrain import RetentionAnalysis

DroughtLevel = Literal["none", "watch", "moderate", "severe"]


class Cause(BaseModel):
    key: str
    title: str
    amount_mm: float | None  # contribution to the water shortage, where quantifiable
    detail: str


SignalVerdict = Literal["dry", "normal", "wet", "missing"]


class SourceSignal(BaseModel):
    """What one independent data source says about this date against the last 10 years."""

    key: str
    source: str  # short name shown to the farmer
    verdict: SignalVerdict
    value: str  # the reading, e.g. "22 % (średnio 23 %)"
    note: str  # rank or reason, e.g. "5. najniższy z 11 lat"


class Diagnosis(BaseModel):
    level: DroughtLevel
    headline: str
    signals: list[SourceSignal] = []
    stress_threshold_pct: float | None = None  # plant-available water below which the crop suffers
    warnings: list[str] = []  # shown before everything else (e.g. parcel is not farmland)
    evidence: list[str]  # observations supporting the verdict
    causes: list[Cause]
    confidence: Literal["high", "medium", "low"]
    limitations: list[str]
    missing_data: list[str]


class IrrigationEstimate(BaseModel):
    """Water and rough running cost of one irrigation dose on the whole parcel."""

    water_m3: float
    cost_pln: Range  # estimate: energy and labour with an own water source, no equipment
    yearly_limit_m3: float  # abstraction allowed without a water-law permit (5 m³/day average)
    over_limit: bool


class Recommendation(BaseModel):
    key: str
    category: Literal["retention", "soil", "crop", "irrigation"]
    title: str
    action: str  # what to do, concretely
    why: str  # the data behind it
    effect_m3: Range | None  # water kept or supplied on the parcel
    effect_note: str | None  # what the effect refers to (per rain, per season, …)
    when: str
    cost: Literal["niski", "średni", "wysoki"]
    formalities: str | None
    site_ids: list[int] = []  # retention sites on the map
    ditch_ids: list[int] = []
    irrigation: IrrigationEstimate | None = None


class ParcelShape(BaseModel):
    """Plan shape of the parcel (PL-1992 metres)."""

    length_m: float  # long side of the rectangle with the same area and perimeter
    width_m: float  # its short side: typical working width, also for winding strips
    box_width_m: float  # short side of the minimum rotated bounding rectangle
    elongation: float  # length / width
    compactness: float  # 4πA / P² (1 = circle, < 0.3 = long or ragged)
    axis_azimuth_deg: int  # direction of the long axis, 0–179, 0 = north–south
    narrow_strip: bool
    winding: bool  # strip bends: bounding box much wider than the strip itself


class AnalysisReport(BaseModel):
    parcel: Parcel
    crop: Crop
    analysis_date: date
    generated_at: datetime
    diagnosis: Diagnosis
    recommendations: list[Recommendation]
    water: ModuleResult[WaterBalance]
    soil: ModuleResult[SoilProfile]
    satellite: ModuleResult[VegetationState]
    hydro: ModuleResult[HydroStatus]
    land: ModuleResult[LandCover]
    terrain: ModuleResult[RetentionAnalysis]
    edo: ModuleResult[EdoDrought]
    shape: ParcelShape | None = None
