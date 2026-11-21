"""Verdict and causes of the water situation, combining every module that delivered data.
Each statement names the numbers it is based on; missing inputs lower the confidence."""

from retencja_api.assessment.crop_params import CropParams
from retencja_api.models import (
    Cause,
    Diagnosis,
    DroughtLevel,
    HydroStatus,
    LandCover,
    RetentionAnalysis,
    SoilProfile,
    VegetationState,
    WaterBalance,
)
from retencja_api.soil.soilgrids import available_water

# Typical plant-available water of a medium (loamy) soil, mm per metre.
REFERENCE_AWC_MM_PER_M = 150.0
LOW_SOC_PCT = 1.2
NDMI_DROP = 0.05  # canopy-moisture drop vs. normal treated as a visible crop response

LIMITATIONS = [
    "Pogoda z reanaliz (ERA5 przez Open-Meteo, ok. 10 km; awaryjnie MERRA-2 przez NASA POWER, "
    "ok. 50 km), a nie ze stacji na polu.",
    "Gleba z modelu SoilGrids (250 m), a nie z odkrywki; mapa glebowo-rolnicza może się różnić.",
    "Bilans wody w glebie nie uwzględnia wód gruntowych, drenowania ani nawadniania.",
    "Fazy rozwojowe uprawy przyjęto dla typowych terminów siewu w Polsce.",
    "Progi suszy są przybliżeniem metody IUNG (KBW), a nie oficjalnym komunikatem SMSR.",
]

LEVEL_TEXT: dict[DroughtLevel, str] = {
    "none": "Brak niedoboru wody",
    "watch": "Zwiększone ryzyko niedoboru wody",
    "moderate": "Umiarkowany niedobór wody dla uprawy",
    "severe": "Silny niedobór wody dla uprawy",
}


DRY_RANK = 3  # among the 3 driest of ~11 years
REANALYSIS_DRY_RATIO = 0.85


def dry_signals(water: WaterBalance, vegetation: VegetationState | None) -> list[str]:
    """Independent signs that this date is drier than usual at the parcel."""
    signals = []
    if water.available_pct.rank <= DRY_RANK:
        signals.append("model wody w glebie")
    if water.window.kbw_mm.rank <= DRY_RANK:
        signals.append("bilans opadów i parowania")
    sm = water.reanalysis_soil_moisture
    if sm and (sm.rank <= DRY_RANK or sm.value < REANALYSIS_DRY_RATIO * sm.normal):
        signals.append(f"wilgotność gleby {water.soil_moisture_source}")
    ndmi = vegetation.ndmi if vegetation else None
    if ndmi and ndmi.value < ndmi.normal - NDMI_DROP:
        signals.append("uwodnienie roślin z satelity")
    return signals


def _level(water: WaterBalance, crop: CropParams, signals: list[str]) -> DroughtLevel:
    """Absolute crop stress from the soil water balance, graded by how unusual it is."""
    stressed = water.available_pct.value < 100 * (1 - crop.depletion_p)
    if not water.in_season:
        return "watch" if len(signals) >= 2 else "none"
    if stressed and len(signals) >= 2:
        return "severe"
    if (stressed and signals) or len(signals) >= 2:
        return "moderate"
    if stressed or signals:
        return "watch"
    return "none"


def _weather_causes(water: WaterBalance) -> list[Cause]:
    w = water.window
    causes = []
    deficit = w.precipitation_mm.normal - w.precipitation_mm.value
    if deficit > 5:
        causes.append(
            Cause(
                key="rain_deficit",
                title="Mniej opadów niż zwykle",
                amount_mm=round(deficit),
                detail=(
                    f"W 60 dniach do daty analizy spadło {w.precipitation_mm.value:.0f} mm, "
                    f"średnio w tym okresie {w.precipitation_mm.normal:.0f} mm."
                ),
            )
        )
    excess = w.et0_mm.value - w.et0_mm.normal
    if excess > 5:
        causes.append(
            Cause(
                key="evaporation",
                title="Większe parowanie niż zwykle",
                amount_mm=round(excess),
                detail=(
                    f"Parowanie wskaźnikowe ET0 wyniosło {w.et0_mm.value:.0f} mm "
                    f"(średnio {w.et0_mm.normal:.0f} mm); "
                    f"dni z upałem ≥30 °C: {w.hot_days.value:.0f} "
                    f"(średnio {w.hot_days.normal:.1f})."
                ),
            )
        )
    return causes


def _soil_causes(soil: SoilProfile, crop: CropParams, taw_mm: float) -> list[Cause]:
    causes = []
    reference = REFERENCE_AWC_MM_PER_M * crop.root_depth_m
    if taw_mm < 0.85 * reference:
        causes.append(
            Cause(
                key="soil_capacity",
                title="Gleba magazynuje mało wody",
                amount_mm=round(reference - taw_mm),
                detail=(
                    f"{soil.texture.capitalize()} (kategoria {soil.category}, "
                    f"{soil.category_label}) mieści ok. {taw_mm:.0f} mm wody dostępnej "
                    f"w strefie korzeni, gleba średnia ok. {reference:.0f} mm."
                ),
            )
        )
    if soil.organic_carbon_pct < LOW_SOC_PCT and soil.layers:
        top = soil.layers[0]
        sand, clay = top.sand_pct / 100, top.clay_pct / 100
        om = soil.organic_carbon_pct * 1.724
        gain = available_water(sand, clay, om + 1) - available_water(sand, clay, om)
        gain_mm = gain * 300  # +1 % organic matter in the 0–30 cm plough layer
        causes.append(
            Cause(
                key="organic_matter",
                title="Mało próchnicy",
                amount_mm=round(gain_mm, 1),
                detail=(
                    f"Węgiel organiczny {soil.organic_carbon_pct:.1f} %. Każdy 1 % próchnicy "
                    f"więcej w warstwie ornej to ok. {gain_mm:.0f} mm wody więcej w glebie."
                ),
            )
        )
    return causes


def _runoff_cause(terrain: RetentionAnalysis, area_ha: float) -> Cause | None:
    retained = terrain.summary.retained_m3
    if terrain.summary.site_count == 0 or retained.high <= 0:
        return None
    mm_low = retained.low / (area_ha * 10)  # m³ per ha → mm
    mm_high = retained.high / (area_ha * 10)
    return Cause(
        key="runoff",
        title="Woda z ulewy spływa z pola",
        amount_mm=round(mm_high, 1),
        detail=(
            f"Po deszczu {terrain.assumptions.design_rain_mm:.0f} mm zagłębienia terenu mogą "
            f"zatrzymać {retained.low:.0f}–{retained.high:.0f} m³ "
            f"({mm_low:.1f}–{mm_high:.1f} mm na całej działce), które dziś odpływają lub "
            "stoją w zastoiskach."
        ),
    )


def _evidence(
    water: WaterBalance | None, vegetation: VegetationState | None, hydro: HydroStatus | None
) -> list[str]:
    out = []
    if water:
        a = water.available_pct
        out.append(
            f"W strefie korzeni zostało {a.value:.0f} % wody dostępnej dla roślin "
            f"(średnio tego dnia {a.normal:.0f} %, {a.rank}. najniższy wynik z {a.years} lat)."
        )
        k = water.window.kbw_mm
        out.append(
            f"Klimatyczny bilans wodny za 60 dni: {k.value:+.0f} mm "
            f"(średnio {k.normal:+.0f} mm, {k.rank}. najniższy z {k.years} lat)."
        )
        if water.reanalysis_soil_moisture:
            e = water.reanalysis_soil_moisture
            pct = 100 * (e.value / e.normal - 1) if e.normal else 0
            out.append(
                f"Niezależnie: wilgotność gleby wg {water.soil_moisture_source} {pct:+.0f} % "
                f"względem średniej ({e.rank}. najniższa z {e.years} lat)."
            )
        if water.stress_days_30:
            out.append(
                f"Dni silnego stresu wodnego uprawy w ostatnich 30 dniach: {water.stress_days_30}."
            )
    if vegetation and vegetation.current and vegetation.ndmi and vegetation.ndvi:
        m, v = vegetation.ndmi, vegetation.ndvi
        out.append(
            f"Satelita ({vegetation.current.date:%d.%m.%Y}): uwodnienie roślin NDMI {m.value:.2f} "
            f"(średnio {m.normal:.2f}), zieleń NDVI {v.value:.2f} (średnio {v.normal:.2f})."
        )
    if hydro and hydro.drought_warnings:
        out.append(
            f"IMGW: ostrzeżenia o suszy hydrologicznej w woj. {hydro.voivodeship}: "
            f"{len(hydro.drought_warnings)}."
        )
    return out


def diagnose(
    crop: CropParams,
    area_ha: float,
    water: WaterBalance | None,
    soil: SoilProfile | None,
    vegetation: VegetationState | None,
    hydro: HydroStatus | None,
    terrain: RetentionAnalysis | None,
    missing: list[str],
) -> Diagnosis:
    if water is None:
        return Diagnosis(
            level="watch",
            headline="Nie udało się ocenić sytuacji wodnej: brak danych pogodowych.",
            evidence=_evidence(None, vegetation, hydro),
            causes=[],
            confidence="low",
            limitations=LIMITATIONS,
            missing_data=missing,
        )
    signals = dry_signals(water, vegetation)
    level = _level(water, crop, signals)
    causes = _weather_causes(water)
    if soil is not None:
        causes += _soil_causes(soil, crop, water.taw_mm)
    if hydro and hydro.drought_warnings:
        causes.append(
            Cause(
                key="hydrological_drought",
                title="Niskie stany wód w zlewni",
                amount_mm=None,
                detail="IMGW ostrzega przed suszą hydrologiczną: rzeki i rowy niosą mniej wody, "
                "co utrudnia nawadnianie i obniża wody gruntowe.",
            )
        )
    if terrain is not None and (cause := _runoff_cause(terrain, area_ha)):
        causes.append(cause)
    causes.sort(key=lambda c: -(c.amount_mm or 0))

    headline = LEVEL_TEXT[level]
    if not water.in_season:
        headline += " (poza sezonem wegetacji uprawy: oceniamy zapas wody w glebie)"
    if signals:
        prefix = "Nieco suszej niż zwykle" if level == "none" else "Sucho na tle 10 lat"
        headline += f". {prefix} wg: {', '.join(signals)}."
    confidence = "high"
    if missing or (soil is not None and soil.assumed):
        confidence = "medium"
    if len(signals) == 1 and level != "none":
        confidence = "medium"  # only one source points to dryness
    return Diagnosis(
        level=level,
        headline=headline,
        evidence=_evidence(water, vegetation, hydro),
        causes=causes,
        confidence=confidence,
        limitations=LIMITATIONS,
        missing_data=missing,
    )


def land_warnings(land: LandCover | None) -> list[str]:
    """Warn when the parcel is mostly not farmland: crop results would be misleading."""
    if land is None or land.is_agricultural:
        return []
    main = ", ".join(f"{c.name} {100 * c.share:.0f} %" for c in land.classes[:3])
    return [
        f"Ta działka nie wygląda na rolniczą (mapa pokrycia terenu ESA WorldCover "
        f"{land.year}: {main}; grunty orne i łąki tylko {100 * land.agricultural_share:.0f} %). "
        "Ocena dla uprawy i zalecenia mają tu ograniczony sens. Sprawdź numer działki."
    ]
