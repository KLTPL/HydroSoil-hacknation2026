"""Crop choice and management, and irrigation as the last resort."""

import math

from retencja_api.assessment.crop_params import CROP_PARAMS
from retencja_api.assessment.recs_common import MONTHS, MONTHS_IN, ParcelContext, m3
from retencja_api.models import IrrigationEstimate, Range, Recommendation, WaterBalance

RISK_SHARE = 0.3  # month with strong stress in ≥ 3 of 10 years
# Water law (Prawo wodne, art. 33 ust. 4 and art. 389): an owner may abstract on average up
# to 5 m³ a day (yearly mean) for the own farm without a water-law permit.
PERMIT_FREE_M3_PER_DAY = 5.0
# Rough running cost of irrigation from an own source (energy or fuel, labour), without
# equipment or water fees, zł per m³. An estimate only, shown as such.
IRRIGATION_COST_PLN_PER_M3 = (0.5, 2.0)


def _risky_months(water: WaterBalance):
    return [m for m in water.risk_calendar
            if m.years and m.years_with_stress / m.years >= RISK_SHARE]


def _risk_why(water: WaterBalance) -> str:
    risky = _risky_months(water)
    worst = max(risky, key=lambda m: m.years_with_stress)
    months = ", ".join(f"{MONTHS[m.month]} ({m.years_with_stress}/{m.years} lat)" for m in risky)
    return (
        f"Kalendarz ryzyka z 10 lat: silny stres wodny w miesiącach: {months}. Okres "
        f"krytyczny uprawy: {water.critical_stage}; najczęściej sucho w "
        f"{MONTHS_IN[worst.month]}."
    )


def crop_timing(ctx: ParcelContext) -> Recommendation | None:
    water = ctx.water
    if water is None or ctx.crop.group != "arable" or not _risky_months(water):
        return None
    return Recommendation(
        key="crop_timing",
        category="crop",
        title="Dopasuj odmianę i termin siewu do suszy",
        action=(
            "Wybieraj odmiany wcześniejsze i bardziej odporne na suszę (patrz listy PDO "
            "COBORU dla województwa), siej w optymalnym terminie, a nawożenie azotem dziel "
            "na dawki, żeby nie stymulować łanu przed suchym okresem."
        ),
        why=_risk_why(water),
        effect_m3=None,
        effect_note=None,
        when="Przy planowaniu siewu i zakupie materiału siewnego.",
        cost="niski",
        formalities=None,
    )


def grass_management(ctx: ParcelContext) -> Recommendation | None:
    """Meadows and pastures: cutting and grazing height decide how fast the sward recovers
    after a dry spell; drought-tolerant species when reseeding."""
    water = ctx.water
    if water is None or ctx.crop.group != "grassland":
        return None
    pasture = ctx.crop is CROP_PARAMS["pastwiska"]
    use = (
        "Wypasaj rotacyjnie w kwaterach i zdejmuj zwierzęta, gdy ruń ma ok. 5–7 cm; "
        "w suszy wydłuż przerwy między wypasami." if pasture else
        "Koś nie niżej niż 5–7 cm i nie koś w samym szczycie suszy: wyższe ściernisko "
        "osłania glebę i szybciej odrasta."
    )
    why = (
        _risk_why(water) if _risky_months(water) else
        f"Okres krytyczny: {water.critical_stage}."
    )
    return Recommendation(
        key="grass_management",
        category="crop",
        title="Użytkuj łąkę tak, by ruń szybko odrastała po suszy" if not pasture else
        "Wypasaj tak, by ruń szybko odrastała po suszy",
        action=(
            f"{use} Przy podsiewie wybieraj gatunki znoszące suszę (kupkówka pospolita, "
            "kostrzewa trzcinowa, stokłosa, lucerna, koniczyna). Nie przeorywuj użytku."
        ),
        why=(
            f"{why} Trawy mają płytkie korzenie: zapas wody dostępnej w strefie korzeni to "
            f"tylko ok. {water.taw_mm:.0f} mm."
        ),
        effect_m3=None,
        effect_note=None,
        when="Przy każdym pokosie lub wypasie; podsiew wiosną lub pod koniec sierpnia.",
        cost="niski",
        formalities=None,
    )


def irrigation_estimate(dose_mm: float, area_ha: float) -> IrrigationEstimate:
    water = dose_mm * area_ha * 10
    lo, hi = IRRIGATION_COST_PLN_PER_M3
    limit = PERMIT_FREE_M3_PER_DAY * 365
    return IrrigationEstimate(
        water_m3=round(water),
        cost_pln=Range(low=round(water * lo, -1), high=round(water * hi, -1)),
        yearly_limit_m3=limit,
        over_limit=water > limit,
    )


IRRIGATION_DOSE_MM = 25.0  # a single overhead dose the topsoil can take in
FULL_PROFILE_DOSE_MM = 60.0


def _doses(dose_mm: float) -> str:
    n = max(1, math.ceil(dose_mm / IRRIGATION_DOSE_MM))
    split = (f" Podaj ją w {n} dawkach po ok. {dose_mm / n:.0f} mm" if n > 1
             else " Podaj ją jednorazowo")
    note = (" To uzupełnienie całej strefy korzeni; w praktyce wystarczy podlewać tak, "
            "żeby zapas nie spadał poniżej progu stresu." if dose_mm > FULL_PROFILE_DOSE_MM
            else "")
    return f"{split}, wieczorem lub w nocy.{note}"


def irrigation(ctx: ParcelContext) -> Recommendation | None:
    water, crop = ctx.water, ctx.crop
    if water is None:
        return None
    threshold = 100 * (1 - crop.depletion_p)
    if not water.in_season or water.available_pct.value >= threshold:
        return None
    dose_mm = water.taw_mm * (1 - water.available_pct.value / 100)
    hydro_note = (
        " IMGW ostrzega przed suszą hydrologiczną w województwie: ogranicz pobór z rowów "
        "i rzek." if ctx.hydro and ctx.hydro.drought_warnings else ""
    )
    method = {
        "orchard": " Najoszczędniej kroplowo, pod rzędami.",
        "grassland": " Na łące nawadnianie zwykle opłaca się tylko po pokosie, na glebie lekkiej.",
    }.get(crop.group, _doses(dose_mm))
    return Recommendation(
        key="irrigation",
        category="irrigation",
        title="Nawodnij, jeśli masz źródło wody",
        action=(
            f"Dawka do pełnego uzupełnienia strefy korzeni: ok. {dose_mm:.0f} mm "
            f"({dose_mm * 10:.0f} m³/ha).{method}{hydro_note}"
        ),
        why=(
            f"W strefie korzeni zostało {water.available_pct.value:.0f} % wody dostępnej, "
            f"poniżej progu stresu {threshold:.0f} % dla tej uprawy."
        ),
        effect_m3=m3(dose_mm, dose_mm, ctx.area_ha),
        effect_note="jednorazowo, na całą działkę",
        when="Teraz.",
        cost="wysoki",
        formalities=(
            "Potrzebne własne źródło wody: studnia, zbiornik albo zgoda na pobór z rowu lub "
            "rzeki. Bez pozwolenia wodnoprawnego można pobierać na potrzeby gospodarstwa "
            "średnio do 5 m³ na dobę w skali roku (Prawo wodne, art. 33); większy pobór "
            "i studnia głębsza niż 30 m wymagają pozwolenia (Wody Polskie). To ogólna "
            "informacja, nie porada prawna."
        ),
        irrigation=irrigation_estimate(dose_mm, ctx.area_ha),
    )
