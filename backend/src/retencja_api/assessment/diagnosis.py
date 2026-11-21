"""Verdict and causes of the water situation, combining every module that delivered data.
Each statement names the numbers it is based on; missing inputs lower the confidence."""

from retencja_api.assessment.crop_params import CropParams
from retencja_api.models import (
    Cause,
    Comparison,
    Diagnosis,
    DroughtLevel,
    HydroStatus,
    LandCover,
    RetentionAnalysis,
    SignalVerdict,
    SoilProfile,
    SourceSignal,
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

DRY_RANK = 3  # among the 3 driest (or wettest) of ~11 years
REANALYSIS_DRY_RATIO = 0.85


def _ranked(c: Comparison) -> SignalVerdict:
    if c.rank <= DRY_RANK:
        return "dry"
    if c.rank > c.years - DRY_RANK:
        return "wet"
    return "normal"


def _rank_note(c: Comparison) -> str:
    if c.rank > c.years / 2:
        return f"{c.years - c.rank + 1}. najwyższy wynik z {c.years} lat"
    return f"{c.rank}. najniższy wynik z {c.years} lat"


def _pl(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def source_signals(
    water: WaterBalance, vegetation: VegetationState | None, hydro: HydroStatus | None
) -> list[SourceSignal]:
    """Independent readings of this date against the same date in earlier years."""
    a = water.available_pct
    k = water.window.kbw_mm
    out = [
        SourceSignal(
            key="soil_model",
            source="Model wody w glebie",
            verdict=_ranked(a),
            value=f"{a.value:.0f} % (średnio {a.normal:.0f} %)",
            note=_rank_note(a),
        ),
        SourceSignal(
            key="kbw",
            source="Opady minus parowanie (60 dni)",
            verdict=_ranked(k),
            value=f"{k.value:+.0f} mm (średnio {k.normal:+.0f} mm)",
            note=_rank_note(k),
        ),
    ]
    sm = water.reanalysis_soil_moisture
    if sm:
        pct = 100 * (sm.value / sm.normal - 1) if sm.normal else 0
        verdict = _ranked(sm)
        if sm.value < REANALYSIS_DRY_RATIO * sm.normal:
            verdict = "dry"
        out.append(
            SourceSignal(
                key="reanalysis",
                source=f"Wilgotność gleby {water.soil_moisture_source.split(' ')[0]}",
                verdict=verdict,
                value=f"{pct:+.0f} % względem średniej",
                note=_rank_note(sm),
            )
        )
    else:
        out.append(SourceSignal(key="reanalysis", source="Wilgotność gleby (reanaliza)",
                                verdict="missing", value="brak danych", note=""))
    ndmi = vegetation.ndmi if vegetation else None
    if ndmi and vegetation and vegetation.current:
        verdict = "normal"
        if ndmi.value < ndmi.normal - NDMI_DROP:
            verdict = "dry"
        elif ndmi.value > ndmi.normal + NDMI_DROP:
            verdict = "wet"
        out.append(
            SourceSignal(
                key="satellite",
                source="Uwodnienie roślin z satelity",
                verdict=verdict,
                value=f"NDMI {_pl(ndmi.value)} (średnio {_pl(ndmi.normal)})",
                note=f"Sentinel-2, {vegetation.current.date:%d.%m.%Y}",
            )
        )
    else:
        out.append(SourceSignal(key="satellite", source="Uwodnienie roślin z satelity",
                                verdict="missing", value="brak bezchmurnego zdjęcia", note=""))
    if hydro is not None:
        n = len(hydro.drought_warnings)
        out.append(
            SourceSignal(
                key="hydro",
                source="Susza hydrologiczna IMGW",
                verdict="dry" if n else "normal",
                value=f"{n} ostrzeżeń" if n else "brak ostrzeżeń",
                note=f"woj. {hydro.voivodeship}, stan bieżący",
            )
        )
    return out


def dry_signals(signals: list[SourceSignal]) -> list[str]:
    """Names of the 10-year comparisons pointing to a drier than usual date.
    IMGW warnings are current-only, so they do not count for historical dates."""
    return [s.source.lower() for s in signals if s.verdict == "dry" and s.key != "hydro"]


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


def _headline(water: WaterBalance, crop: CropParams, signals: list[SourceSignal]) -> str:
    """Two separate statements: does the crop have water now, and is that unusual."""
    threshold = 100 * (1 - crop.depletion_p)
    left = water.available_pct.value
    if not water.in_season:
        state = (
            f"Uprawa jest poza sezonem wegetacji. W glebie jest {left:.0f} % "
            "wody dostępnej (zapas na wiosnę)."
        )
    elif left < threshold:
        state = (
            f"Uprawa cierpi z braku wody: w strefie korzeni zostało {left:.0f} % wody "
            f"dostępnej, a stres zaczyna się poniżej {threshold:.0f} %."
        )
    else:
        state = (
            f"Uprawa ma wodę: w strefie korzeni jest {left:.0f} % wody dostępnej "
            f"(stres poniżej {threshold:.0f} %)."
        )
    compared = [s for s in signals if s.verdict != "missing" and s.key != "hydro"]
    dry = [s.source.lower() for s in compared if s.verdict == "dry"]
    wet = [s.source.lower() for s in compared if s.verdict == "wet"]
    if dry and wet:
        context = (
            f"Na tle 10 lat źródła nie są zgodne: suszej niż zwykle wg {', '.join(dry)}, "
            f"wilgotniej wg {', '.join(wet)}."
        )
    elif dry:
        context = (
            f"Na tle 10 lat jest suszej niż zwykle ({len(dry)} z {len(compared)} źródeł: "
            f"{', '.join(dry)})."
        )
    elif wet:
        context = f"Na tle 10 lat jest wilgotniej niż zwykle wg: {', '.join(wet)}."
    else:
        context = "Na tle 10 lat to typowa sytuacja dla tej pory roku."
    return f"{state} {context}"


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
    readings = source_signals(water, vegetation, hydro)
    signals = dry_signals(readings)
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

    confidence = "high"
    if missing or (soil is not None and soil.assumed):
        confidence = "medium"
    if len(signals) == 1 and level != "none":
        confidence = "medium"  # only one source points to dryness
    if signals and any(r.verdict == "wet" for r in readings):
        confidence = "medium"  # sources disagree
    return Diagnosis(
        level=level,
        headline=_headline(water, crop, readings),
        signals=readings,
        stress_threshold_pct=round(100 * (1 - crop.depletion_p)),
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
