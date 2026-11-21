"""Drought level of the verdict: the official SMSR criterion first, then the crop's water
stress graded by how many independent sources call the date drier than usual."""

from retencja_api.assessment.crop_params import CropParams
from retencja_api.assessment.signals import NOT_VOTING
from retencja_api.models import DroughtLevel, SourceSignal, WaterBalance


def drought_level(
    water: WaterBalance, crop: CropParams, readings: list[SourceSignal]
) -> DroughtLevel:
    """Absolute crop stress from the soil water balance, graded by how unusual it is.
    Sources saying "wetter than usual" cancel those saying "drier"."""
    stressed = water.available_pct.value < 100 * (1 - crop.depletion_p)
    compared = [r for r in readings if r.key not in NOT_VOTING]
    net = sum(r.verdict == "dry" for r in compared) - sum(r.verdict == "wet" for r in compared)
    smsr = water.smsr
    if smsr is not None and smsr.drought:
        # The official criterion: drought that lowers the yield of this crop on this soil.
        return "severe" if stressed and net >= 2 else "moderate"
    level = _relative_level(water, stressed, net)
    if smsr is not None and smsr.official and level in ("moderate", "severe"):
        return "watch"  # IUNG did not declare drought here: a dry spell, not a yield loss
    return level


def _relative_level(water: WaterBalance, stressed: bool, net: int) -> DroughtLevel:
    if not water.in_season:
        return "watch" if net >= 2 else "none"
    if stressed and net >= 2:
        return "severe"
    if (stressed and net >= 1) or net >= 2:
        return "moderate"
    if stressed or net >= 1:
        return "watch"
    return "none"
