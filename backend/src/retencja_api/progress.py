"""Live analysis progress: one short, factual line per finished data module."""

from typing import Any

from pydantic import BaseModel

from retencja_api.assessment.recommendations import plural
from retencja_api.models import (
    HydroStatus,
    LandCover,
    ModuleResult,
    ModuleStatus,
    RetentionAnalysis,
    SoilProfile,
    VegetationState,
    WaterBalance,
)


class ModuleProgress(BaseModel):
    module: str
    status: ModuleStatus
    fact: str  # what the module found, or why it has no data
    duration_ms: int
    live: bool  # downloaded now (False: served from the cache)


def _fact(data: Any) -> str:
    match data:
        case WaterBalance():
            years = data.window.kbw_mm.years
            return f"{years} lat pogody · bilans 60 dni {data.window.kbw_mm.value:+.0f} mm"
        case SoilProfile():
            return f"{data.texture}, kategoria {data.category}"
        case VegetationState():
            scenes = len(data.history) + (1 if data.current else 0)
            photos = plural(
                scenes, "bezchmurne zdjęcie", "bezchmurne zdjęcia", "bezchmurnych zdjęć"
            )
            return f"{scenes} {photos} z tej pory roku"
        case HydroStatus():
            n = len(data.drought_warnings)
            warnings = plural(n, "ostrzeżenie", "ostrzeżenia", "ostrzeżeń")
            return f"{n} {warnings} o suszy" if n else f"brak ostrzeżeń, woj. {data.voivodeship}"
        case LandCover():
            return f"grunty rolne {100 * data.agricultural_share:.0f} % działki"
        case RetentionAnalysis():
            sites, ditches = data.summary.site_count, len(data.ditches)
            return (
                f"{sites} {plural(sites, 'miejsce', 'miejsca', 'miejsc')} na wodę · "
                f"{ditches} {plural(ditches, 'rów', 'rowy', 'rowów')}"
            )
    raise TypeError(f"No progress fact for {type(data).__name__}")


def module_progress(name: str, result: ModuleResult[Any]) -> ModuleProgress:
    if result.status == "ok" and result.data is not None:
        fact = _fact(result.data)
    else:
        fact = result.message or "brak danych"
    return ModuleProgress(
        module=name,
        status=result.status,
        fact=fact,
        duration_ms=result.duration_ms,
        live=any(s.retrieved == "live" for s in result.sources),
    )
