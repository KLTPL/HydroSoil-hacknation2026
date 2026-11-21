"""What each independent data source says about the analysis date against the same date
in earlier years ("vote of sources"), interpreted for the crop that grows on the parcel."""

from retencja_api.assessment.crop_params import CropParams
from retencja_api.models import (
    Comparison,
    HydroStatus,
    SignalVerdict,
    SmsrCheck,
    SourceSignal,
    VegetationState,
    WaterBalance,
)

NDMI_DROP = 0.05  # canopy-moisture drop vs. normal treated as a visible crop response
DRY_RANK = 3  # among the 3 driest (or wettest) of ~11 years
REANALYSIS_DRY_RATIO = 0.85
# Differences smaller than these are within the noise of the method: never dry or wet.
SOIL_WATER_TOLERANCE_PCT = 5.0
KBW_TOLERANCE_MM = 10.0
# The satellite reading compares canopies only with enough years and a closed canopy.
MIN_SATELLITE_YEARS = 3
MIN_CANOPY_NDVI = 0.4


def _ranked(c: Comparison, tolerance: float = 0.0) -> SignalVerdict:
    if abs(c.value - c.normal) < tolerance:
        return "normal"
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


# How the canopy seen by the satellite differs from a closed field crop.
SATELLITE_LIMITATIONS = {
    "grassland": (
        "Na łące i pastwisku zieleń i uwodnienie z satelity spadają po każdym pokosie "
        "i wypasie, niezależnie od suszy; spadek bez potwierdzenia w bilansie wody nie jest "
        "liczony jako sygnał suszy."
    ),
    "orchard": (
        "W sadzie piksel satelity (20 m) łączy korony drzew lub krzewów z murawą "
        "w międzyrzędziach; NDMI opisuje głównie murawę i reaguje na jej koszenie."
    ),
}


def _satellite_verdict(
    verdict: SignalVerdict, soil_model: SignalVerdict, crop: CropParams | None
) -> tuple[SignalVerdict, str]:
    """Mowing or grazing drops NDMI on grassland: trust it only with a dry soil model."""
    if crop is not None and crop.group == "grassland" and verdict == "dry" and (
        soil_model != "dry"
    ):
        return "normal", "spadek zapewne po pokosie lub wypasie"
    return verdict, ""


def _satellite_skip(vegetation: VegetationState, crop: CropParams | None) -> str | None:
    """Why NDMI cannot be compared with earlier years on this date, or None."""
    ndmi, ndvi, current = vegetation.ndmi, vegetation.ndvi, vegetation.current
    if ndmi is None or current is None:
        return "brak bezchmurnego zdjęcia"
    if ndmi.years < MIN_SATELLITE_YEARS:
        return f"za mało lat do porównania ({ndmi.years})"
    if ndvi is None or min(ndvi.value, ndvi.normal) < MIN_CANOPY_NDVI:
        return "brak zwartego łanu (goła gleba, wschody lub po zbiorze)"
    if crop is not None and crop.group == "arable":
        late = crop.stages(current.date.year)[3]
        if not crop.in_season(current.date) or current.date >= late:
            return "dojrzewanie lub poza sezonem: łan zasycha naturalnie"
    return None


def source_signals(
    water: WaterBalance,
    vegetation: VegetationState | None,
    hydro: HydroStatus | None,
    crop: CropParams | None = None,
) -> list[SourceSignal]:
    """Independent readings of this date against the same date in earlier years."""
    a = water.available_pct
    k = water.window.kbw_mm
    out = [
        SourceSignal(
            key="soil_model",
            source="Model wody w glebie",
            verdict=_ranked(a, SOIL_WATER_TOLERANCE_PCT),
            value=f"{a.value:.0f} % (średnio {a.normal:.0f} %)",
            note=_rank_note(a),
        ),
        SourceSignal(
            key="kbw",
            source="Opady minus parowanie (60 dni)",
            verdict=_ranked(k, KBW_TOLERANCE_MM),
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
    skip = _satellite_skip(vegetation, crop) if vegetation else "brak bezchmurnego zdjęcia"
    ndmi = vegetation.ndmi if vegetation else None
    if skip is None and ndmi and vegetation and vegetation.current:
        verdict = "normal"
        if ndmi.value < ndmi.normal - NDMI_DROP:
            verdict = "dry"
        elif ndmi.value > ndmi.normal + NDMI_DROP:
            verdict = "wet"
        verdict, reason = _satellite_verdict(verdict, out[0].verdict, crop)
        out.append(
            SourceSignal(
                key="satellite",
                source="Uwodnienie roślin z satelity",
                verdict=verdict,
                value=f"NDMI {_pl(ndmi.value)} (średnio {_pl(ndmi.normal)})",
                note=f"Sentinel-2, {vegetation.current.date:%d.%m.%Y}"
                + (f"; {reason}" if reason else ""),
            )
        )
    else:
        out.append(SourceSignal(key="satellite", source="Uwodnienie roślin z satelity",
                                verdict="missing", value="nie porównano", note=skip or ""))
    if water.smsr is not None:
        out.append(smsr_signal(water.smsr))
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


# Not a comparison with earlier years: IMGW warnings are current-only, and the SMSR criterion
# is an absolute threshold on the same water balance the KBW comparison already counts.
NOT_VOTING = ("hydro", "smsr")


def smsr_signal(check: SmsrCheck) -> SourceSignal:
    period = f"{check.period_start:%d.%m}–{check.period_end:%d.%m}"
    if check.threshold_mm is None:
        value = f"KBW {check.kbw_mm:+.0f} mm; w tym okresie susza nie obniża plonu"
    else:
        value = f"KBW {check.kbw_mm:+.0f} mm, próg suszy {check.threshold_mm:.0f} mm"
    return SourceSignal(
        key="smsr",
        source="Kryterium suszy rolniczej IUNG (SMSR)",
        verdict="dry" if check.drought else "normal",
        value=value,
        note=f"okres {period}, kategoria gleby {check.soil_category}; "
        + ("wynik IUNG dla gminy" if check.official else "obliczone z reanalizy pogody"),
    )


def dry_signals(signals: list[SourceSignal]) -> list[str]:
    """Names of the 10-year comparisons pointing to a drier than usual date."""
    return [s.source.lower() for s in signals if s.verdict == "dry" and s.key not in NOT_VOTING]
