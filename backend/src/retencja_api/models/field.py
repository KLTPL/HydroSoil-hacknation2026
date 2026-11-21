"""Field data modules: soil, weather and soil water, satellite, hydrology, land cover."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from retencja_api.models.common import Comparison


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


class Scenario(BaseModel):
    key: Literal["no_rain", "dry", "typical", "wet", "irrigated", "more_humus"]
    label: str
    analog_year: int | None  # past year whose weather of the same days is replayed
    rain_mm: float
    et0_mm: float
    first_stress_day: date | None  # first in-season day with strong stress (Ks < 0.5)
    stress_days: int
    available_pct_end: float
    refill_mm: float  # irrigation dose that refills the root zone at the end


class Scenarios(BaseModel):
    start: date
    end: date
    humus_gain_mm: float  # extra root-zone water assumed in the "more_humus" scenario
    items: list[Scenario]


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
    season_etc_mm: float = 0.0  # mean crop water use over the growing season (10 years)
    scenarios: Scenarios | None = None  # None outside the growing season
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


class LandCoverShare(BaseModel):
    code: int
    name: str
    share: float  # 0–1 of the parcel area


class LandCover(BaseModel):
    year: int
    classes: list[LandCoverShare]
    agricultural_share: float  # cropland + grassland
    is_agricultural: bool


class EdoDrought(BaseModel):
    dekad: date  # first day of the 10-day period the map describes
    cdi_class: int  # 0 none, 1 watch, 2 warning, 3 alert, 4–6 recovery
    label: str
    drought: bool  # watch, warning or alert
    agrees: bool | None = None  # whether our verdict also says dry / not dry
