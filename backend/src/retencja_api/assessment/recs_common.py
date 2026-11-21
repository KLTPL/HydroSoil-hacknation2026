"""Inputs and helpers shared by the recommendation rules."""

from dataclasses import dataclass

from retencja_api.assessment.crop_params import CropParams
from retencja_api.config import DESIGN_RAIN_MM, RUNOFF_COEFF_RANGE
from retencja_api.models import (
    HydroStatus,
    LandCover,
    ParcelShape,
    Range,
    RetentionAnalysis,
    SoilProfile,
    TerrainSlope,
    WaterBalance,
)

MONTHS = ["", "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
          "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
MONTHS_IN = ["", "styczniu", "lutym", "marcu", "kwietniu", "maju", "czerwcu", "lipcu",
             "sierpniu", "wrześniu", "październiku", "listopadzie", "grudniu"]
_COMPASS = ["północ", "północny wschód", "wschód", "południowy wschód", "południe",
            "południowy zachód", "zachód", "północny zachód"]
_AXES = ["północ–południe", "północny wschód–południowy zachód", "wschód–zachód",
         "południowy wschód–północny zachód"]


@dataclass(frozen=True)
class ParcelContext:
    """Everything known about the parcel; any module may be missing (None)."""

    crop: CropParams
    area_ha: float
    water: WaterBalance | None = None
    soil: SoilProfile | None = None
    hydro: HydroStatus | None = None
    terrain: RetentionAnalysis | None = None
    shape: ParcelShape | None = None
    land: LandCover | None = None

    @property
    def slope(self) -> TerrainSlope | None:
        return self.terrain.slope if self.terrain else None

    @property
    def design_rain_mm(self) -> float:
        return self.terrain.assumptions.design_rain_mm if self.terrain else DESIGN_RAIN_MM

    def runoff_m3(self, area_ha: float, share: tuple[float, float] = (1.0, 1.0)) -> Range:
        """Runoff of the design rain from `area_ha` of arable land, times `share` (the part
        a measure keeps on the field)."""
        lo, hi = RUNOFF_COEFF_RANGE
        return m3(self.design_rain_mm * lo * share[0], self.design_rain_mm * hi * share[1],
                  area_ha)


def plural(n: int, one: str, few: str, many: str) -> str:
    """Polish noun form for a count: 1 zastawka, 2–4 zastawki, 5+ zastawek."""
    if n == 1:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def m3(mm_low: float, mm_high: float, area_ha: float) -> Range:
    """Water depth in mm over `area_ha` as m³ (1 mm on 1 ha = 10 m³)."""
    return Range(low=round(mm_low * area_ha * 10), high=round(mm_high * area_ha * 10))


def compass(azimuth_deg: float) -> str:
    return _COMPASS[round(azimuth_deg / 45) % 8]


def axis_words(azimuth_deg: float) -> str:
    """Undirected line direction in words, e.g. 'wschód–zachód'."""
    return _AXES[round((azimuth_deg % 180) / 45) % 4]


def pl(value: float, digits: int = 1) -> str:
    """Number with a Polish decimal comma."""
    return f"{value:.{digits}f}".replace(".", ",")
