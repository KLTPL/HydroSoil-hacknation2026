"""Water retention in the terrain: depressions, ditch weirs and wet (organic) soils."""

from retencja_api.assessment.recs_common import ParcelContext, m3, pl, plural
from retencja_api.models import Range, Recommendation

SHARED_SITE = 0.7  # a depression lying less than this much on the parcel is shared
# Organic carbon from which the topsoil is muck or peat (mursz, torf): hydrogenic soil.
ORGANIC_SOIL_SOC_PCT = 6.0
VALLEY_MAX_SLOPE_PCT = 2.0
VALLEY_RELATIVE_HEIGHT_M = -0.5  # parcel lies this much lower than its surroundings
# Raising the summer groundwater table by about 0.2 m stores water in the soil pores it
# fills; specific yield of muck and peat soils about 0.1–0.2.
WETLAND_RAISE_M = 0.2
WETLAND_SPECIFIC_YIELD = (0.1, 0.2)


def ponds(ctx: ParcelContext) -> Recommendation | None:
    terrain = ctx.terrain
    if terrain is None or not terrain.sites:
        return None
    sites = sorted(terrain.sites, key=lambda s: -s.retained_m3.high)[:3]
    total = terrain.summary.retained_m3
    narrow = ctx.shape is not None and ctx.shape.narrow_strip
    shared = [s for s in sites if s.parcel_share < SHARED_SITE]
    listing = "; ".join(
        f"nr {s.id}: {'oczko wodne' if s.kind == 'pond' and not narrow else 'podmokłe obniżenie'}"
        f", {s.area_m2:.0f} m², do {s.max_depth_m:.1f} m głębokości"
        + (f", na Twojej działce {100 * s.parcel_share:.0f} %" if s.parcel_share < SHARED_SITE
           else "")
        for s in sites
    )
    if narrow:
        action = (
            f"Nie zasypuj i nie zaorywuj zagłębień, w których zbiera się woda ({listing}). "
            f"Działka ma tylko ok. {ctx.shape.width_m:.0f} m szerokości, więc nie kop na niej "
            "oczka: zostaw zagłębienia pod trawą jako podmokłe miejsca. Większe oczko ma sens "
            "tylko wspólnie z sąsiadami, na kilku działkach naraz."
        )
    else:
        action = (
            f"Nie zasypuj i nie zaorywuj zagłębień, w których zbiera się woda ({listing}). "
            "Najgłębsze przekształć w oczko wodne, płytkie zostaw jako trwale zieloną, "
            "podmokłą łąkę (pas trawy wokół zatrzyma glebę spłukiwaną z pola)."
        )
        if shared:
            action += " Zagłębienia sięgające działek sąsiadów zagospodaruj razem z nimi."
    return Recommendation(
        key="ponds",
        category="retention",
        title="Zatrzymaj wodę w naturalnych zagłębieniach",
        action=action,
        why=(
            f"Model terenu z LIDAR pokazuje {terrain.summary.site_count} zagłębień "
            f"o łącznej pojemności {terrain.summary.storage_m3:.0f} m³; po deszczu "
            f"{terrain.assumptions.design_rain_mm:.0f} mm spływa do nich "
            f"{total.low:.0f}–{total.high:.0f} m³ wody."
        ),
        effect_m3=total,
        effect_note=f"z każdego deszczu {terrain.assumptions.design_rain_mm:.0f} mm",
        when="Prace ziemne po żniwach lub wczesną wiosną, przy suchym gruncie.",
        cost="niski" if narrow else "średni",
        formalities=None if narrow else (
            "Przed kopaniem oczka zapytaj w starostwie i w Wodach Polskich, czy potrzebne jest "
            "zgłoszenie (zależy od powierzchni, głębokości i połączenia z wodami)."
        ),
        site_ids=[s.id for s in sites],
    )


def weirs(ctx: ParcelContext) -> Recommendation | None:
    terrain = ctx.terrain
    if terrain is None or not terrain.ditches:
        return None
    count = sum(d.weir_count for d in terrain.ditches)
    length = sum(d.length_m for d in terrain.ditches)
    soil = Range(
        low=sum(d.soil_m3.low + d.channel_m3 for d in terrain.ditches),
        high=sum(d.soil_m3.high + d.channel_m3 for d in terrain.ditches),
    )
    slopes = ", ".join(f"{d.slope_pct:.2f} %" for d in terrain.ditches[:3])
    lidar = sum(d.kind == "lidar" for d in terrain.ditches)
    osm = len(terrain.ditches) - lidar
    found = f"Rowy wykryte w modelu terenu LIDAR: {lidar}" + (
        f", z OpenStreetMap: {osm}. " if osm else ". "
    )
    return Recommendation(
        key="weirs",
        category="retention",
        title="Postaw zastawki na rowach",
        action=(
            f"Na {length:.0f} m rowów przy działce postaw {count} "
            f"{plural(count, 'zastawkę', 'zastawki', 'zastawek')} (piętrzenie ok. "
            f"{terrain.ditches[0].weir_head_m:.1f} m), w miejscach zaznaczonych na mapie. "
            "Zamykaj je po roztopach i po ulewach, otwieraj przy podtopieniu pola."
        ),
        why=(
            f"{found}Spadek rowów z modelu terenu: {slopes}; zastawki rozmieszczono tak, by cofka "
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


def wetland(ctx: ParcelContext) -> Recommendation | None:
    """Organic (muck, peat) soil or a flat valley floor with ditches: drainage dries and
    destroys the soil; keeping the water table high is the retention measure."""
    soil, slope, terrain = ctx.soil, ctx.slope, ctx.terrain
    organic = soil is not None and not soil.assumed and (
        soil.organic_soil or soil.organic_carbon_pct >= ORGANIC_SOIL_SOC_PCT
    )
    valley = (
        slope is not None and terrain is not None and bool(terrain.ditches)
        and slope.mean_pct < VALLEY_MAX_SLOPE_PCT
        and slope.relative_height_m <= VALLEY_RELATIVE_HEIGHT_M
    )
    if not organic and not valley:
        return None
    reasons = []
    if organic:
        reasons.append(
            f"W wierzchniej warstwie gleby jest {pl(soil.organic_carbon_pct)} % węgla "
            "organicznego (SoilGrids): to gleba organiczna (murszowa lub torfowa). "
            "Odwodniona traci co roku 0,5–2 cm wysokości, bo materia organiczna się rozkłada."
        )
    if valley:
        reasons.append(
            f"Działka jest płaska (średni spadek {pl(slope.mean_pct)} %) i leży "
            f"{pl(-slope.relative_height_m)} m niżej niż jej otoczenie, przy rowach: "
            "to dno doliny, do którego spływa woda z okolicy."
        )
    grass = ctx.crop.group == "grassland"
    return Recommendation(
        key="wetland",
        category="retention",
        title="Trzymaj wysoko wodę na mokrym, niskim terenie",
        action=(
            "Nie pogłębiaj rowów i nie zakładaj nowego drenowania. Latem utrzymuj wodę "
            "w rowach tak, by wody gruntowe były ok. 40–60 cm pod powierzchnią (zastawki). "
            + ("Użytkuj teren jako łąkę i nie zaorywuj jej." if grass else
               "Najlepszym użytkowaniem takiego terenu jest trwała łąka, nie grunt orny.")
        ),
        why=" ".join(reasons),
        effect_m3=m3(1000 * WETLAND_RAISE_M * WETLAND_SPECIFIC_YIELD[0],
                     1000 * WETLAND_RAISE_M * WETLAND_SPECIFIC_YIELD[1], ctx.area_ha),
        effect_note="w glebie, gdy wody gruntowe będą wyżej o ok. 20 cm",
        when="Cały rok; zastawki zamykaj po roztopach.",
        cost="niski",
        formalities=(
            "Poziom wody w rowach melioracyjnych uzgodnij ze spółką wodną lub Wodami "
            "Polskimi. Zmianę gruntu ornego na łąkę zgłoś we wniosku o dopłaty (ARiMR)."
        ),
    )
