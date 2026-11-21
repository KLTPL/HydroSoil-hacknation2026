"""Retention and agrotechnical recommendations for the parcel, each tied to the numbers
in the report that justify it. Effects are ranges in m³ of water on this parcel."""

from retencja_api.assessment.crop_params import KC_OFF_SEASON, CropParams
from retencja_api.models import (
    HydroStatus,
    Range,
    Recommendation,
    RetentionAnalysis,
    SoilProfile,
    WaterBalance,
)
from retencja_api.soil.soilgrids import available_water

PLOUGH_LAYER_M = 0.3
OM_GAIN_PCT = 1.0  # realistic organic-matter gain from years of manure, straw, cover crops
TARGET_SOC_PCT = 2.0  # below this, building organic matter is worth recommending
MULCH_EVAPORATION_CUT = (0.25, 0.5)  # share of bare-soil evaporation saved by mulch / no-till
RISK_SHARE = 0.3  # month with strong stress in ≥ 3 of 10 years
MONTHS = ["", "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
          "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
MONTHS_IN = ["", "styczniu", "lutym", "marcu", "kwietniu", "maju", "czerwcu", "lipcu",
             "sierpniu", "wrześniu", "październiku", "listopadzie", "grudniu"]


def _m3(mm_low: float, mm_high: float, area_ha: float) -> Range:
    return Range(low=round(mm_low * area_ha * 10), high=round(mm_high * area_ha * 10))


def _ponds(terrain: RetentionAnalysis) -> Recommendation | None:
    sites = sorted(terrain.sites, key=lambda s: -s.retained_m3.high)[:3]
    if not sites:
        return None
    total = terrain.summary.retained_m3
    listing = "; ".join(
        f"nr {s.id}: {'oczko wodne' if s.kind == 'pond' else 'podmokła łąka'}, "
        f"{s.area_m2:.0f} m², do {s.max_depth_m:.1f} m głębokości"
        for s in sites
    )
    return Recommendation(
        key="ponds",
        category="retention",
        title="Zatrzymaj wodę w naturalnych zagłębieniach",
        action=(
            f"Nie zasypuj i nie zaorywuj zagłębień, w których zbiera się woda ({listing}). "
            "Najgłębsze przekształć w oczko wodne, płytkie zostaw jako trwale zieloną, "
            "podmokłą łąkę (pas trawy wokół zatrzyma glebę spłukiwaną z pola)."
        ),
        why=(
            f"Model terenu z LIDAR pokazuje {terrain.summary.site_count} zagłębień "
            f"o łącznej pojemności {terrain.summary.storage_m3:.0f} m³; po deszczu "
            f"{terrain.assumptions.design_rain_mm:.0f} mm spływa do nich "
            f"{total.low:.0f}–{total.high:.0f} m³ wody."
        ),
        effect_m3=total,
        effect_note=f"z każdego deszczu {terrain.assumptions.design_rain_mm:.0f} mm",
        when="Prace ziemne po żniwach lub wczesną wiosną, przy suchym gruncie.",
        cost="średni",
        formalities=(
            "Przed kopaniem oczka zapytaj w starostwie i w Wodach Polskich, czy potrzebne jest "
            "zgłoszenie (zależy od powierzchni, głębokości i połączenia z wodami)."
        ),
        site_ids=[s.id for s in sites],
    )


def _weirs(terrain: RetentionAnalysis) -> Recommendation | None:
    if not terrain.ditches:
        return None
    weirs = sum(d.weir_count for d in terrain.ditches)
    length = sum(d.length_m for d in terrain.ditches)
    soil = Range(
        low=sum(d.soil_m3.low + d.channel_m3 for d in terrain.ditches),
        high=sum(d.soil_m3.high + d.channel_m3 for d in terrain.ditches),
    )
    slopes = ", ".join(f"{d.slope_pct:.2f} %" for d in terrain.ditches[:3])
    return Recommendation(
        key="weirs",
        category="retention",
        title="Postaw zastawki na rowach",
        action=(
            f"Na {length:.0f} m rowów przy działce postaw {weirs} "
            f"{'zastawkę' if weirs == 1 else 'zastawek'} (piętrzenie ok. "
            f"{terrain.ditches[0].weir_head_m:.1f} m), w miejscach zaznaczonych na mapie. "
            "Zamykaj je po roztopach i po ulewach, otwieraj przy podtopieniu pola."
        ),
        why=(
            f"Spadek rowów z modelu terenu: {slopes}; zastawki rozmieszczono tak, by cofka "
            "wody sięgała do następnej. Podniesiony poziom wody w rowie podnosi wody gruntowe "
            "w pasie ok. 50 m po obu stronach."
        ),
        effect_m3=soil,
        effect_note="w rowach i w glebie przy rowach, na cały sezon",
        when="Zamknięcie zastawek: koniec marca, po spłynięciu wód roztopowych.",
        cost="niski",
        formalities=(
            "Rów zwykle należy do spółki wodnej lub Wód Polskich: zastawkę uzgodnij "
            "z zarządcą rowu; wymaga zgłoszenia wodnoprawnego."
        ),
        ditch_ids=[d.id for d in terrain.ditches],
    )


def _organic_matter(soil: SoilProfile, area_ha: float) -> Recommendation | None:
    if soil.organic_carbon_pct >= TARGET_SOC_PCT and soil.category in ("III", "IV"):
        return None
    if not soil.layers:
        return None
    top = soil.layers[0]
    sand, clay = top.sand_pct / 100, top.clay_pct / 100
    om = soil.organic_carbon_pct * 1.724
    gain = available_water(sand, clay, om + OM_GAIN_PCT) - available_water(sand, clay, om)
    mm = gain * PLOUGH_LAYER_M * 1000
    return Recommendation(
        key="organic_matter",
        category="soil",
        title="Zwiększ ilość próchnicy w glebie",
        action=(
            "Przyorywuj słomę zamiast ją sprzedawać, stosuj obornik lub kompost i siej "
            "międzyplony po żniwach. Nie zostawiaj gleby bez okrywy na zimę."
        ),
        why=(
            f"{soil.texture.capitalize()} (kategoria {soil.category}, {soil.category_label}), "
            f"węgiel organiczny {soil.organic_carbon_pct:.1f} %. Każdy 1 % próchnicy więcej "
            f"w warstwie ornej to ok. {mm:.0f} mm wody więcej dostępnej dla roślin "
            "(Saxton i Rawls 2006)."
        ),
        effect_m3=_m3(mm * 0.5, mm, area_ha),
        effect_note="więcej wody w glebie po kilku latach (+0,5–1 % próchnicy)",
        when="Po żniwach (słoma, międzyplon) i przed siewem (obornik).",
        cost="niski",
        formalities=(
            "Międzyplony i szybkie wymieszanie obornika to praktyki ekoschematu "
            "„Rolnictwo węglowe” (dopłata ARiMR)."
        ),
    )


def _mulch(water: WaterBalance, area_ha: float) -> Recommendation:
    # Until the canopy closes, evaporation from the soil surface runs at about the
    # bare-soil coefficient.
    soil_evaporation = water.open_canopy_et0_mm * KC_OFF_SEASON
    low, high = (soil_evaporation * cut for cut in MULCH_EVAPORATION_CUT)
    return Recommendation(
        key="mulch",
        category="soil",
        title="Ogranicz parowanie z gołej gleby",
        action=(
            "Zamiast orki stosuj uprawę uproszczoną lub siew bezpośredni w mulcz ze słomy "
            "albo międzyplonu. Wiosną uprawiaj płytko i od razu wałuj, żeby nie przesuszyć "
            "wierzchniej warstwy."
        ),
        why=(
            f"Od siewu do zwarcia łanu parowanie wskaźnikowe wynosi tu średnio "
            f"{water.open_canopy_et0_mm:.0f} mm; z odkrytej gleby ucieka z tego ok. "
            f"{soil_evaporation:.0f} mm. Mulcz ogranicza to o 25–50 % (FAO-56)."
        ),
        effect_m3=_m3(low, high, area_ha),
        effect_note="mniej wody straconej w każdym sezonie",
        when="Przy uprawie przedsiewnej i siewie.",
        cost="niski",
        formalities="Uproszczone systemy uprawy to praktyka ekoschematu „Rolnictwo węglowe”.",
    )


def _crop_timing(water: WaterBalance) -> Recommendation | None:
    risky = [m for m in water.risk_calendar if m.years and m.years_with_stress / m.years
             >= RISK_SHARE]
    if not risky:
        return None
    worst = max(risky, key=lambda m: m.years_with_stress)
    months = ", ".join(f"{MONTHS[m.month]} ({m.years_with_stress}/{m.years} lat)" for m in risky)
    return Recommendation(
        key="crop_timing",
        category="crop",
        title="Dopasuj odmianę i termin siewu do suszy",
        action=(
            "Wybieraj odmiany wcześniejsze i bardziej odporne na suszę (patrz listy PDO "
            "COBORU dla województwa), siej w optymalnym terminie, a nawożenie azotem dziel "
            "na dawki, żeby nie stymulować łanu przed suchym okresem."
        ),
        why=(
            f"Kalendarz ryzyka z 10 lat: silny stres wodny w miesiącach: {months}. Okres "
            f"krytyczny uprawy: {water.critical_stage}; najczęściej sucho w "
            f"{MONTHS_IN[worst.month]}."
        ),
        effect_m3=None,
        effect_note=None,
        when="Przy planowaniu siewu i zakupie materiału siewnego.",
        cost="niski",
        formalities=None,
    )


def _irrigation(
    water: WaterBalance, crop: CropParams, area_ha: float, hydro: HydroStatus | None
) -> Recommendation | None:
    threshold = 100 * (1 - crop.depletion_p)
    if not water.in_season or water.available_pct.value >= threshold:
        return None
    dose_mm = water.taw_mm * (1 - water.available_pct.value / 100)
    hydro_note = (
        " IMGW ostrzega przed suszą hydrologiczną w województwie: ogranicz pobór z rowów "
        "i rzek." if hydro and hydro.drought_warnings else ""
    )
    return Recommendation(
        key="irrigation",
        category="irrigation",
        title="Nawodnij, jeśli masz źródło wody",
        action=(
            f"Dawka do pełnego uzupełnienia strefy korzeni: ok. {dose_mm:.0f} mm "
            f"({dose_mm * 10:.0f} m³/ha). Podaj ją w 2–3 dawkach po 20–30 mm, wieczorem "
            f"lub w nocy.{hydro_note}"
        ),
        why=(
            f"W strefie korzeni zostało {water.available_pct.value:.0f} % wody dostępnej, "
            f"poniżej progu stresu {threshold:.0f} % dla tej uprawy."
        ),
        effect_m3=_m3(dose_mm, dose_mm, area_ha),
        effect_note="jednorazowo, na całą działkę",
        when="Teraz.",
        cost="wysoki",
        formalities=(
            "Pobór wody powyżej 5 m³ na dobę zwykle wymaga pozwolenia wodnoprawnego "
            "(Wody Polskie)."
        ),
    )


def recommend(
    crop: CropParams,
    area_ha: float,
    water: WaterBalance | None,
    soil: SoilProfile | None,
    hydro: HydroStatus | None,
    terrain: RetentionAnalysis | None,
) -> list[Recommendation]:
    recs: list[Recommendation | None] = []
    if water is not None:
        recs.append(_irrigation(water, crop, area_ha, hydro))
    if terrain is not None:
        recs += [_weirs(terrain), _ponds(terrain)]
    if soil is not None:
        recs.append(_organic_matter(soil, area_ha))
    if water is not None:
        recs += [_mulch(water, area_ha), _crop_timing(water)]
    present = [r for r in recs if r is not None]
    urgent = [r for r in present if r.category == "irrigation"]
    rest = sorted(
        (r for r in present if r.category != "irrigation"),
        key=lambda r: -(r.effect_m3.high if r.effect_m3 else 0),
    )
    return urgent + rest
