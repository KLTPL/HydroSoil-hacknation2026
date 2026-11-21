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


class DitchWeirs(BaseModel):
    """Weirs proposed on one ditch on or along the parcel."""

    id: int
    kind: str  # OSM waterway type: ditch, drain, canal, stream
    length_m: float
    slope_pct: float
    weir_count: int
    weir_head_m: float
    channel_m3: float  # held in the ditch behind the weirs
    soil_m3: Range  # held in the soil of both banks by the raised groundwater table
    geometry: GeoJSON  # WGS84 LineString
    weirs: GeoJSON  # WGS84 MultiPoint


class RetentionAnalysis(BaseModel):
    parcel_id: str
    computed_at: datetime  # when the terrain data was downloaded and analysed
    summary: RetentionSummary
    sites: list[RetentionSite]
    assumptions: Assumptions
    ditches: list[DitchWeirs] = []
    ditches_checked: bool = False  # False when the ditch map could not be downloaded


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


class SoilLayer(BaseModel):
    depth: str
    clay_pct: float
    sand_pct: float
    silt_pct: float
    organic_carbon_pct: float


class SoilProfile(BaseModel):
    texture: str
    category: Literal["I", "II", "III", "IV"]  # IUNG soil category, I = most drought-prone
    category_label: str
    awc_mm_per_m: float  # plant-available water per metre of soil
    organic_carbon_pct: float  # topsoil 0–30 cm
    layers: list[SoilLayer]
    resolution_m: float
    assumed: bool = False  # True when soil data was missing and a default was used


class WeatherWindow(BaseModel):
    start: date
    end: date
    precipitation_mm: Comparison
    et0_mm: Comparison
    kbw_mm: Comparison  # climatic water balance = precipitation − ET0
    hot_days: Comparison  # days with Tmax ≥ 30 °C


class RiskMonth(BaseModel):
    month: int
    years_with_stress: int
    years: int
    mean_stress_days: float


class WaterBalance(BaseModel):
    window: WeatherWindow
    in_season: bool
    kc: float
    taw_mm: float  # total available water in the root zone
    raw_mm: float  # readily available water (no stress until it is used up)
    available_pct: Comparison  # modelled plant-available water left in the root zone
    stress_days_30: int  # days with strong crop water stress in the last 30 days
    reanalysis_soil_moisture: Comparison | None  # independent check from a reanalysis model
    soil_moisture_source: str  # e.g. ERA5-Land 0–100 cm (m³/m³) or MERRA-2 root-zone wetness
    risk_calendar: list[RiskMonth]
    critical_stage: str
    open_canopy_et0_mm: float  # mean ET0 from sowing until the canopy closes
    grid_lat: float
    grid_lon: float


class VegetationObservation(BaseModel):
    year: int
    date: date
    ndvi: float
    ndmi: float
    clear_pct: float  # share of the parcel free of clouds and shadows


class VegetationState(BaseModel):
    current: VegetationObservation | None
    history: list[VegetationObservation]
    ndvi: Comparison | None
    ndmi: Comparison | None
    window_days: int
    missing_years: list[int]


class HydroWarning(BaseModel):
    number: str
    event: str
    probability_pct: int
    valid_from: str
    valid_to: str | None
    office: str
    area: str
    description: str


class HydroStatus(BaseModel):
    voivodeship: str
    drought_warnings: list[HydroWarning]
    other_warnings: int


DroughtLevel = Literal["none", "watch", "moderate", "severe"]


class Cause(BaseModel):
    key: str
    title: str
    amount_mm: float | None  # contribution to the water shortage, where quantifiable
    detail: str


class Diagnosis(BaseModel):
    level: DroughtLevel
    headline: str
    evidence: list[str]  # observations supporting the verdict
    causes: list[Cause]
    confidence: Literal["high", "medium", "low"]
    limitations: list[str]
    missing_data: list[str]


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
    terrain: ModuleResult[RetentionAnalysis]
