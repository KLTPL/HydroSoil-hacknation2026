"""Soil retention and agrotechnics: organic matter, mulch, cover crops, contour tillage."""

from retencja_api.assessment.crop_params import KC_OFF_SEASON
from retencja_api.assessment.parcel_shape import axis_angle
from retencja_api.assessment.recs_common import MONTHS_IN, ParcelContext, axis_words, m3, pl
from retencja_api.models import Recommendation
from retencja_api.soil.soilgrids import humus_water_gain_mm

TARGET_SOC_PCT = 2.0  # below this, building organic matter is worth recommending
MULCH_EVAPORATION_CUT = (0.25, 0.5)  # share of bare-soil evaporation saved by mulch / no-till
ORCHARD_ROW_SHARE = 0.3  # mulched strip under the rows, share of the orchard area
EARLY_HARVEST = (8, 31)  # harvested by then: time for a summer catch crop
CONTOUR_MIN_SLOPE_PCT = 3.0
# Contour tillage keeps part of the runoff on the field (USLE support factor P 0.5–0.9).
CONTOUR_RUNOFF_KEPT = (0.1, 0.5)

_OM_ACTION = {
    "arable": "Przyorywuj słomę zamiast ją sprzedawać i stosuj obornik lub kompost.",
    "grassland": (
        "Nawoź obornikiem lub kompostem (gnojowicę stosuj z umiarem) i nie zaorywuj darni: "
        "przy każdym przeoraniu łąki próchnica szybko się rozkłada."
    ),
    "orchard": (
        "Stosuj kompost lub obornik w pasie pod drzewami lub krzewami, a skoszoną trawę "
        "z międzyrzędzi zostawiaj na miejscu."
    ),
}


ORGANIC_SOIL_SOC_PCT = 3.5
MIN_HUMUS_GAIN_MM = 1.0


def organic_matter(ctx: ParcelContext) -> Recommendation | None:
    soil = ctx.soil
    if soil is None or not soil.layers:
        return None
    if soil.organic_carbon_pct >= TARGET_SOC_PCT and soil.category in ("III", "IV"):
        return None
    if soil.organic_carbon_pct >= ORGANIC_SOIL_SOC_PCT:
        return None  # already humus-rich or organic: more humus barely adds water
    mm = humus_water_gain_mm(soil)
    if mm < MIN_HUMUS_GAIN_MM:
        return None
    return Recommendation(
        key="organic_matter",
        category="soil",
        title="Zwiększ ilość próchnicy w glebie",
        action=_OM_ACTION[ctx.crop.group],
        why=(
            f"{soil.texture.capitalize()} (kategoria {soil.category}, {soil.category_label}), "
            f"węgiel organiczny {soil.organic_carbon_pct:.1f} %. Każdy 1 % próchnicy więcej "
            f"w warstwie ornej to ok. {mm:.0f} mm wody więcej dostępnej dla roślin "
            "(Saxton i Rawls 2006)."
        ),
        effect_m3=m3(mm * 0.5, mm, ctx.area_ha),
        effect_note="więcej wody w glebie po kilku latach (+0,5–1 % próchnicy)",
        when="Po zbiorze lub po pokosie (obornik, kompost) i przed siewem.",
        cost="niski",
        formalities=(
            "Szybkie wymieszanie obornika i międzyplony to praktyki ekoschematu "
            "„Rolnictwo węglowe” (dopłata ARiMR)." if ctx.crop.group == "arable" else None
        ),
    )


def mulch(ctx: ParcelContext) -> Recommendation | None:
    water, group = ctx.water, ctx.crop.group
    if water is None or group == "grassland":
        return None  # a permanent sward already covers the soil
    # Until the canopy closes, evaporation from the soil surface runs at about the
    # bare-soil coefficient.
    soil_evaporation = water.open_canopy_et0_mm * KC_OFF_SEASON
    share = ORCHARD_ROW_SHARE if group == "orchard" else 1.0
    low, high = (soil_evaporation * cut * share for cut in MULCH_EVAPORATION_CUT)
    if group == "orchard":
        action = (
            "Ściółkuj pas pod drzewami lub krzewami (szerokość ok. 1 m) korą, zrębkami, słomą "
            "lub kompostem zamiast trzymać go odchwaszczonym na gołą ziemię. Murawę "
            "w międzyrzędziach koś nisko w czasie suszy, żeby nie konkurowała o wodę."
        )
    else:
        action = (
            "Zamiast orki stosuj uprawę uproszczoną lub siew bezpośredni w mulcz ze słomy "
            "albo międzyplonu. Wiosną uprawiaj płytko i od razu wałuj, żeby nie przesuszyć "
            "wierzchniej warstwy."
        )
    return Recommendation(
        key="mulch",
        category="soil",
        title="Ogranicz parowanie z gołej gleby",
        action=action,
        why=(
            f"Od początku wegetacji do pełnego ulistnienia parowanie wskaźnikowe wynosi tu "
            f"średnio {water.open_canopy_et0_mm:.0f} mm; z odkrytej gleby ucieka z tego ok. "
            f"{soil_evaporation:.0f} mm. Mulcz ogranicza to o 25–50 % (FAO-56)."
            + (" Ściółka obejmuje ok. 30 % powierzchni sadu." if group == "orchard" else "")
        ),
        effect_m3=m3(low, high, ctx.area_ha),
        effect_note="mniej wody straconej w każdym sezonie",
        when="Wiosną, przed ruszeniem wegetacji." if group == "orchard" else (
            "Przy uprawie przedsiewnej i siewie."),
        cost="niski",
        formalities=None if group == "orchard" else (
            "Uproszczone systemy uprawy to praktyka ekoschematu „Rolnictwo węglowe”."),
    )


def cover_crops(ctx: ParcelContext) -> Recommendation | None:
    """Catch crops and crop residue (the examples of soil retention in the KOWR brief)."""
    crop = ctx.crop
    if crop.group != "arable":
        return None
    month, day = crop.end
    early = (month, day) <= EARLY_HARVEST
    slope, soil = ctx.slope, ctx.soil
    if early:
        action = (
            "Zaraz po zbiorze wysiej międzyplon ścierniskowy (np. gorczyca, facelia, "
            "mieszanka z bobowatymi), jeśli następna uprawa jest jara; resztki pożniwne "
            "zostaw na powierzchni jako mulcz."
        )
    else:
        action = (
            "Po późnym zbiorze nie zostawiaj gołej, zaoranej roli na zimę: rozdrobnij resztki "
            "pożniwne i zostaw je na powierzchni lub wysiej żyto ozime jako okrywę na zimę."
        )
    why = [
        f"Typowy zbiór tej uprawy: w {MONTHS_IN[month]}. Do wiosny gleba bez okrywy traci "
        "wodę z deszczy jesiennych i roztopów przez spływ i parowanie."
    ]
    if slope is not None and slope.mean_pct >= CONTOUR_MIN_SLOPE_PCT:
        why.append(f"Spadek {pl(slope.mean_pct)} %: okrywa chroni też przed zmywaniem gleby.")
    if soil is not None and soil.category in ("I", "II") and early:
        why.append(
            f"Gleba kategorii {soil.category}: w suchej jesieni międzyplon zużywa wodę, więc "
            "wybierz gatunki o krótkim okresie wzrostu i zakończ go wcześnie."
        )
    return Recommendation(
        key="cover_crops",
        category="soil",
        title="Międzyplon i resztki pożniwne zamiast gołej roli",
        action=action,
        why=" ".join(why),
        effect_m3=None,
        effect_note=None,
        when="Zaraz po zbiorze." if early else "Po zbiorze, przed zimą.",
        cost="niski",
        formalities=(
            "Międzyplony i wymieszanie słomy z glebą to praktyki ekoschematu "
            "„Rolnictwo węglowe” (dopłata ARiMR)."
        ),
    )


def contour_tillage(ctx: ParcelContext) -> Recommendation | None:
    slope, shape = ctx.slope, ctx.shape
    if ctx.crop.group != "arable" or slope is None or slope.fall_azimuth_deg is None:
        return None
    if slope.mean_pct < CONTOUR_MIN_SLOPE_PCT or (shape is not None and shape.narrow_strip):
        return None  # narrow strips get their own advice
    contour = (slope.fall_azimuth_deg + 90) % 180
    along = shape is not None and axis_angle(shape.axis_azimuth_deg, contour) <= 45
    return Recommendation(
        key="contour_tillage",
        category="soil",
        title="Orz i siej w poprzek stoku",
        action=(
            f"Prowadź orkę, siew i rzędy w poprzek spadku, w kierunku {axis_words(contour)}"
            + (" (wzdłuż dłuższego boku działki)." if along else ".")
            + " Na końcach pola zostaw trawiaste uwrocia."
        ),
        why=(
            f"Średni spadek z LIDAR {pl(slope.mean_pct)} %. Bruzdy wzdłuż poziomic działają "
            "jak małe progi: woda wsiąka, zamiast spływać (czynnik P w równaniu erozji "
            "USLE 0,5–0,9)."
        ),
        effect_m3=ctx.runoff_m3(ctx.area_ha, CONTOUR_RUNOFF_KEPT),
        effect_note=f"mniej spływu z każdego deszczu {ctx.design_rain_mm:.0f} mm",
        when="Przy każdej uprawie roli.",
        cost="niski",
        formalities=None,
    )
