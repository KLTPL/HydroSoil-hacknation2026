"""Landscape retention placed by the parcel's shape and LIDAR slope: tree rows, grass buffer
strips, permanent grass on steep ground and measures for narrow strips."""

from retencja_api.assessment.parcel_shape import axis_angle
from retencja_api.assessment.recs_common import (
    ParcelContext,
    axis_words,
    compass,
    m3,
    pl,
    plural,
)
from retencja_api.models import Recommendation

# Shelterbelts: wind speed and field evapotranspiration drop up to ~15 tree heights
# leeward (Ryszkowski & Kędziora, IŚRiL PAN Turew); 10 m trees, 5–15 % less ET.
SHELTER_REACH_M = 150.0
SHELTER_ET_CUT = (0.05, 0.15)
SHELTER_MIN_WIDTH_M = 60.0
SHELTER_MIN_LENGTH_M = 150.0
TREE_COVER_CODE = 10  # ESA WorldCover "Tree cover"
HAS_TREES_SHARE = 0.1
# Prevailing winds in Poland blow from the west (W–SW), IMGW climatology.
PREVAILING_WIND_FROM_DEG = 255

BUFFER_MIN_SLOPE_PCT = 2.0
BUFFER_MIN_EDGE_M = 20.0
BUFFER_WIDTH_M = 6.0
# Share of the runoff that soaks into a grass strip (NWRM, EC 2015: buffer strips;
# conservative range).
BUFFER_INFILTRATION = (0.2, 0.5)
DITCH_BUFFER_M = 5.0

STEEP_MIN_HA = 0.1
STEEP_MIN_SHARE = 0.05
# Runoff coefficient of arable land minus permanent grass on slopes above 10 %.
STEEP_RUNOFF_CUT = (0.10, 0.20)
VERY_STEEP_PCT = 20.0  # IUNG: above this, arable use should give way to grass or trees

# Strip axis closer to the fall line than to the contour: working along it runs downhill.
DOWNHILL_MAX_ANGLE = 45.0
STRIP_MIN_SLOPE_PCT = 2.0
STRIP_RUNOFF_KEPT = (0.2, 0.5)


def _has_trees(ctx: ParcelContext) -> bool:
    if ctx.land is None:
        return False
    return any(c.code == TREE_COVER_CODE and c.share >= HAS_TREES_SHARE for c in ctx.land.classes)


def shelterbelt(ctx: ParcelContext) -> Recommendation | None:
    shape, water, slope = ctx.shape, ctx.water, ctx.slope
    if shape is None or water is None or water.season_etc_mm <= 0:
        return None
    if shape.narrow_strip or shape.width_m < SHELTER_MIN_WIDTH_M:
        return None
    if shape.length_m < SHELTER_MIN_LENGTH_M or _has_trees(ctx):
        return None
    on_slope = slope is not None and slope.fall_azimuth_deg is not None and slope.mean_pct >= 3
    # The belt runs along the contour on a slope, otherwise across the prevailing wind.
    line_az = (slope.fall_azimuth_deg + 90 if on_slope else PREVAILING_WIND_FROM_DEG + 90) % 180
    along_long = axis_angle(shape.axis_azimuth_deg, line_az) <= 45
    belt, across = (shape.length_m, shape.width_m) if along_long else (
        shape.width_m, shape.length_m)
    edge = "dłuższej" if along_long else "krótszej"
    place = (
        f"w poprzek stoku, wzdłuż poziomicy (kierunek {axis_words(line_az)}), w połowie lub "
        "w dolnej części pola" if on_slope else f"wzdłuż {edge} krawędzi od strony zachodniej"
    )
    protected_ha = belt * min(across, SHELTER_REACH_M) / 10_000
    lo, hi = (water.season_etc_mm * c for c in SHELTER_ET_CUT)
    return Recommendation(
        key="shelterbelt",
        category="retention",
        title="Posadź pas drzew i krzewów (zadrzewienie śródpolne)",
        action=(
            f"Posadź pas drzew i krzewów szerokości 5–10 m, ok. {belt:.0f} m długości, {place}. "
            "Wybierz rodzime gatunki (np. dąb, lipa, klon, głóg, tarnina, leszczyna)."
            + (" W sadzie pełni rolę osłony od wiatru." if ctx.crop.group == "orchard" else "")
        ),
        why=(
            f"Uprawa zużywa w sezonie średnio {water.season_etc_mm:.0f} mm wody (model FAO-56, "
            "10 lat). Pas drzew zmniejsza prędkość wiatru i parowanie z pola w odległości "
            f"do ok. 15 wysokości drzew (tu ok. {pl(protected_ha)} ha) o 5–15 % (badania "
            "IŚRiL PAN w Turwi). Działka ma ok. "
            f"{shape.length_m:.0f} × {shape.width_m:.0f} m; w Polsce przeważają wiatry zachodnie."
            + (f" Spadek terenu {pl(slope.mean_pct)} %: pas w poprzek stoku zatrzyma też spływ."
               if on_slope else "")
        ),
        effect_m3=m3(lo, hi, protected_ha),
        effect_note="mniej wody wyparowanej w każdym sezonie, gdy drzewa podrosną",
        when="Sadzenie jesienią (październik–listopad) lub wczesną wiosną.",
        cost="średni",
        formalities=(
            "Pas zajmuje część pola: uzgodnij jego przebieg z sąsiadami i nie sadź na rowie ani "
            "w pasie drogi. Sprawdź w ARiMR i ODR, czy trwa nabór wsparcia na zadrzewienia."
        ),
    )


def ditch_buffer(ctx: ParcelContext) -> Recommendation | None:
    terrain = ctx.terrain
    if terrain is None or not terrain.ditches or ctx.crop.group == "grassland":
        return None
    length = sum(d.length_m for d in terrain.ditches)
    return Recommendation(
        key="ditch_buffer",
        category="retention",
        title="Zostaw pas trawy wzdłuż rowu",
        action=(
            f"Wzdłuż rowów przy działce (ok. {length:.0f} m) zostaw pas trwałej trawy szerokości "
            f"ok. {DITCH_BUFFER_M:.0f} m (ok. {length * DITCH_BUFFER_M:.0f} m²). Nie orz, nie "
            "nawoź i nie pryskaj w tym pasie."
        ),
        why=(
            "Pas trawy spowalnia wodę spływającą do rowu, pozwala jej wsiąknąć i zatrzymuje "
            "glebę oraz nawozy, które inaczej zamulają rów (strefy buforowe, przegląd NWRM "
            f"Komisji Europejskiej 2015). Rowy wykryte z LIDAR i OpenStreetMap: "
            f"{len(terrain.ditches)}."
        ),
        effect_m3=None,
        effect_note=None,
        when="Wysiew trawy wiosną lub po żniwach.",
        cost="niski",
        formalities=(
            "Przy wodach obowiązują pasy bez nawożenia i środków ochrony roślin (m.in. "
            "warunkowość GAEC 4): szerokość sprawdź w ARiMR."
        ),
        ditch_ids=[d.id for d in terrain.ditches],
    )


def slope_buffer(ctx: ParcelContext) -> Recommendation | None:
    slope = ctx.slope
    if slope is None or ctx.crop.group == "grassland":
        return None
    if slope.mean_pct < BUFFER_MIN_SLOPE_PCT or slope.outflow_edge_m < BUFFER_MIN_EDGE_M:
        return None
    if ctx.shape is not None and ctx.shape.narrow_strip:
        return None  # covered by the strip advice
    edge = slope.outflow_edge_m
    side = (
        f" (teren opada w kierunku: {compass(slope.fall_azimuth_deg)})"
        if slope.fall_azimuth_deg is not None else ""
    )
    return Recommendation(
        key="slope_buffer",
        category="retention",
        title="Załóż pas trawy u podnóża stoku",
        action=(
            f"Wzdłuż dolnej krawędzi pola{side}, na ok. {edge:.0f} m, gdzie woda spływa poza "
            f"działkę, zostaw pas trawy szerokości ok. {BUFFER_WIDTH_M:.0f} m "
            f"(ok. {edge * BUFFER_WIDTH_M:.0f} m²)."
        ),
        why=(
            f"Średni spadek działki z LIDAR to {pl(slope.mean_pct)} %. Drogi spływu z modelu "
            f"terenu opuszczają działkę na ok. {edge:.0f} m jej granicy, zbierając wodę "
            f"z ok. {pl(slope.outflow_area_ha)} ha. Pas trawy wchłania 20–50 % takiego spływu "
            "i zatrzymuje spłukiwaną glebę."
        ),
        effect_m3=ctx.runoff_m3(slope.outflow_area_ha, BUFFER_INFILTRATION),
        effect_note=f"z każdego deszczu {ctx.design_rain_mm:.0f} mm",
        when="Wysiew trawy wiosną lub po żniwach.",
        cost="niski",
        formalities=None,
    )


def steep_grass(ctx: ParcelContext) -> Recommendation | None:
    slope = ctx.slope
    if slope is None or ctx.crop.group != "arable":
        return None
    if slope.steep_ha < STEEP_MIN_HA or slope.steep_share < STEEP_MIN_SHARE:
        return None
    lo, hi = (ctx.design_rain_mm * c for c in STEEP_RUNOFF_CUT)
    very = slope.mean_pct >= VERY_STEEP_PCT
    return Recommendation(
        key="steep_grass",
        category="retention",
        title="Zadarń najbardziej strome części pola",
        action=(
            f"Na ok. {pl(slope.steep_ha, 2)} ha o spadku ponad 10 % "
            f"({100 * slope.steep_share:.0f} % działki) załóż trwałą łąkę lub pas krzewów. "
            + ("Przy tak stromym terenie grunt orny lepiej zamienić na trwałą łąkę lub "
               "zadrzewienie w całości." if very else
               "Jeśli uprawiasz tam dalej, unikaj kukurydzy i roślin okopowych (długo goła "
               "gleba).")
        ),
        why=(
            f"Model terenu LIDAR: średni spadek {pl(slope.mean_pct)} %, na 10 % powierzchni "
            f"ponad {pl(slope.p90_pct)} %. Według klasyfikacji erozji IUNG powyżej 10 % grunt "
            "orny podlega silnej erozji wodnej, a ze stromej roli spływa znacznie więcej wody "
            "niż z darni."
            + (" Przy spadku ponad 20 % zaleca się trwałe zadarnienie lub zalesienie."
               if very else "")
        ),
        effect_m3=m3(lo, hi, slope.steep_ha),
        effect_note=f"mniej spływu z każdego deszczu {ctx.design_rain_mm:.0f} mm",
        when="Wysiew trawy wiosną (do połowy maja) lub koniec sierpnia.",
        cost="niski",
        formalities="Zmianę uprawy na trwały użytek zielony zgłoś we wniosku o dopłaty (ARiMR).",
    )


def _strip_spacing(slope_pct: float) -> int:
    """Distance between grass strips across a downhill strip (steeper → closer)."""
    return 50 if slope_pct < 5 else 40 if slope_pct < 10 else 30


def narrow_strip(ctx: ParcelContext) -> Recommendation | None:
    shape, slope = ctx.shape, ctx.slope
    if shape is None or not shape.narrow_strip:
        return None
    downhill = (
        slope is not None and slope.fall_azimuth_deg is not None
        and slope.mean_pct >= STRIP_MIN_SLOPE_PCT
        and axis_angle(shape.axis_azimuth_deg, slope.fall_azimuth_deg) <= DOWNHILL_MAX_ANGLE
    )
    dims = f"ok. {shape.width_m:.0f} m szerokości i {shape.length_m:.0f} m długości"
    why = [f"Działka to wąski pas: {dims}."]
    if downhill:
        spacing = _strip_spacing(slope.mean_pct)
        count = max(1, int(shape.length_m // spacing))
        action = (
            "Pas biega w dół stoku, więc nie da się go uprawiać w poprzek. Zamiast tego co "
            f"ok. {spacing} m zostaw w poprzek pasa trawiastą miedzę szerokości 3–4 m (razem "
            f"ok. {count} {plural(count, 'miedza', 'miedze', 'miedz')}) i pas trawy na dole. "
            "Umów się z sąsiadami z sąsiednich pasów, by miedze ciągnęły się w jednej linii "
            "przez kilka działek: wtedy działają jak tarasy."
        )
        why.append(
            f"Spadek z LIDAR {pl(slope.mean_pct)} % w kierunku: {compass(slope.fall_azimuth_deg)}, "
            "mniej więcej wzdłuż pasa, więc orka i siew idą z góry na dół, a bruzdy prowadzą wodę "
            "w dół stoku."
        )
        effect = ctx.runoff_m3(ctx.area_ha, STRIP_RUNOFF_KEPT)
    else:
        action = (
            "Na tak wąskim pasie nie ma miejsca na oczko wodne ani szeroki pas drzew. "
            "Zachowaj trawiaste miedze na granicach i zatrzymuj wodę wspólnie z sąsiadami: "
            "jedno oczko, zastawka lub pas zadrzewień dla kilku sąsiednich działek."
        )
        effect = None
    if shape.winding:
        action += (
            " Kręte fragmenty i kliny, trudne do obrobienia maszyną, zostaw pod trwałą trawą "
            "lub krzewami."
        )
        why.append(f"Pas jest kręty: obrys ma do {shape.box_width_m:.0f} m szerokości.")
    if slope is not None and slope.runon_area_ha >= 0.1:
        why.append(f"Na działkę spływa woda z ok. {pl(slope.runon_area_ha)} ha powyżej.")
    return Recommendation(
        key="narrow_strip",
        category="retention",
        title="Wąski pas: miedze w poprzek i współpraca z sąsiadami",
        action=action,
        why=" ".join(why),
        effect_m3=effect,
        effect_note=f"z każdego deszczu {ctx.design_rain_mm:.0f} mm" if effect else None,
        when="Miedze zakładaj przy najbliższej uprawie, przed siewem.",
        cost="niski",
        formalities=(
            "Wspólne zatrzymywanie wody łatwiej zorganizować przez spółkę wodną lub sołectwo."
        ),
    )
