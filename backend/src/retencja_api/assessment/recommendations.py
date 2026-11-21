"""Retention and agrotechnical recommendations for the parcel. Each rule fires only when the
parcel data call for it and states the numbers behind it; effects are m³ of water on this
parcel. The rules live in recs_* modules grouped by topic."""

from collections.abc import Callable

from retencja_api.assessment import recs_crop, recs_landscape, recs_retention, recs_soil
from retencja_api.assessment.crop_params import CropParams
from retencja_api.assessment.recs_common import ParcelContext, plural
from retencja_api.landcover.worldcover import is_farmland
from retencja_api.models import (
    HydroStatus,
    LandCover,
    ParcelShape,
    Recommendation,
    RetentionAnalysis,
    SoilProfile,
    WaterBalance,
)

__all__ = ["CATEGORY_ORDER", "plural", "recommend"]

# KOWR sequence ("Podstawy naukowe"): retention → agrotechnics → irrigation as a last resort.
CATEGORY_ORDER = {"retention": 0, "soil": 1, "crop": 2, "irrigation": 3}

RULES: list[Callable[[ParcelContext], Recommendation | None]] = [
    recs_retention.weirs,
    recs_retention.ponds,
    recs_retention.wetland,
    recs_landscape.narrow_strip,
    recs_landscape.steep_grass,
    recs_landscape.slope_buffer,
    recs_landscape.ditch_buffer,
    recs_landscape.shelterbelt,
    recs_soil.organic_matter,
    recs_soil.mulch,
    recs_soil.contour_tillage,
    recs_soil.cover_crops,
    recs_crop.crop_timing,
    recs_crop.grass_management,
    recs_crop.irrigation,
]


def recommend(
    crop: CropParams,
    area_ha: float,
    water: WaterBalance | None,
    soil: SoilProfile | None,
    hydro: HydroStatus | None,
    terrain: RetentionAnalysis | None,
    shape: ParcelShape | None = None,
    land: LandCover | None = None,
) -> list[Recommendation]:
    ctx = ParcelContext(crop, area_ha, water, soil, hydro, terrain, shape, land)
    present = [r for rule in RULES if (r := rule(ctx)) is not None]
    if not is_farmland(land, crop.group):
        # Forest, roads or built-up land: farming advice makes no sense, keeping water does.
        present = [r for r in present if r.category == "retention"]
    # Stable sort: within a category by effect, rules without a number keep their order.
    return sorted(
        present,
        key=lambda r: (CATEGORY_ORDER[r.category], -(r.effect_m3.high if r.effect_m3 else 0)),
    )
