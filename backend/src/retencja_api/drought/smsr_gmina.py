"""Official drought results of the IUNG Agricultural Drought Monitoring System (SMSR) for a
gmina: for every soil category, crop and six-dekad period, whether the drought criterion of
the regulation was exceeded. Published from 2020 at https://susza.iung.pulawy.pl/wykazy/."""

import html
import re
from datetime import date

import httpx

from retencja_api.assessment.smsr import period_number
from retencja_api.cache import read_json, write_json
from retencja_api.models import SmsrCheck

URL = "https://susza.iung.pulawy.pl/wykazy/{year},{teryt}/"
FIRST_YEAR = 2020
CROP_NAMES = {
    "Zboża ozime": "zboza_ozime",
    "Zboża jare": "zboza_jare",
    "Kukurydza na ziarno": "kukurydza_ziarno",
    "Kukurydza na kiszonkę": "kukurydza_kiszonka",
    "Rzepak i rzepik": "rzepak",
    "Ziemniak": "ziemniak",
    "Burak cukrowy": "burak_cukrowy",
    "Chmiel": "chmiel",
    "Tytoń": "tyton",
    "Warzywa gruntowe": "warzywa",
    "Krzewy owocowe": "krzewy_owocowe",
    "Drzewa owocowe": "drzewa_owocowe",
    "Truskawki": "truskawki",
    "Rośliny strączkowe": "straczkowe",
}
# "+" criterion exceeded, "-" not exceeded, "x" no yield loss in that period,
# "#" crop not suited to the soil, "*" the soil category does not occur in the gmina.
_SYMBOLS = {"+", "-", "x", "#", "*"}
_PERIODS = 14

Table = dict[str, dict[str, list[str]]]  # soil category → crop id → 14 symbols


def gmina_teryt(parcel_id: str) -> str | None:
    """7-digit gmina TERYT from a parcel id (`040706_5.0016.51/1` → `0407063`). Urban and
    rural parts of a mixed gmina (types 4 and 5) are reported together as type 3."""
    match = re.match(r"^(\d{6})_(\d)\.", parcel_id)
    if match is None:
        return None
    kind = match.group(2)
    if kind in ("8", "9"):  # districts and delegations of cities: not in the SMSR tables
        return None
    return match.group(1) + ("3" if kind in ("4", "5") else kind)


def parse(page: str) -> Table:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))
    names = "|".join(re.escape(n) for n in CROP_NAMES)
    table: Table = {}
    for section in re.split(r"Kategoria gleby (?=I|II|III|IV)", text)[1:]:
        category = section.split(" ", 1)[0]
        rows = {}
        for name, cells in re.findall(rf"({names})((?: [+\-x#*]){{{_PERIODS}}})", section):
            symbols = cells.split()
            if set(symbols) <= _SYMBOLS:
                rows[CROP_NAMES[name]] = symbols
        if rows:
            table[category] = rows
    return table


async def gmina_table(parcel_id: str, year: int) -> Table | None:
    """None before 2020 or for parcels outside the SMSR gmina list."""
    teryt = gmina_teryt(parcel_id)
    if teryt is None or year < FIRST_YEAR:
        return None
    # Past seasons are final; the current one changes every dekad.
    key = f"{teryt}:{year}" if year < date.today().year else f"{teryt}:{date.today()}"
    if (cached := read_json("smsr-gmina", key)) is not None:
        return cached or None
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(URL.format(year=year, teryt=teryt))
    response.raise_for_status()
    table = parse(response.text)
    write_json("smsr-gmina", key, table)
    return table or None


def with_official(check: SmsrCheck, table: Table | None, crop_id: str) -> SmsrCheck:
    """`check` with the gmina result for its soil category, crop and period, when listed."""
    symbols = (table or {}).get(check.soil_category, {}).get(crop_id)
    if symbols is None:
        return check
    symbol = symbols[period_number(check.period_start) - 1]
    if symbol == "*":
        return check
    return check.model_copy(update={"drought": symbol == "+", "official": True})
