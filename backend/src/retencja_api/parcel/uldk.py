"""Client for ULDK (GUGiK parcel locator): id, region + number, or coordinates → parcel."""

import httpx
from shapely import wkt
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from retencja_api import cache
from retencja_api.config import CRS_METRIC, CRS_WGS84, ULDK_URL
from retencja_api.geo import geometry_to_wgs84
from retencja_api.models import Parcel

_FIELDS = ["id", "voivodeship", "county", "commune", "region", "parcel", "geom_wkt"]
MAX_SEARCH_RESULTS = 10


class ParcelNotFound(Exception):
    pass


class UldkError(Exception):
    pass


def _parse_row(line: str) -> tuple[Parcel, BaseGeometry]:
    values = line.split("|")
    if len(values) != len(_FIELDS):
        raise UldkError(f"Unexpected ULDK row: {line[:200]}")
    row = dict(zip(_FIELDS, values, strict=True))

    srid, _, geom_text = row["geom_wkt"].partition(";")
    if srid != f"SRID={CRS_METRIC}":
        raise UldkError(f"Unexpected geometry SRID: {srid}")
    geom_metric = wkt.loads(geom_text)

    parcel = Parcel(
        id=row["id"],
        voivodeship=row["voivodeship"],
        county=row["county"],
        commune=row["commune"],
        region=row["region"],
        number=row["parcel"],
        area_ha=round(geom_metric.area / 10_000, 4),
        geometry=mapping(geometry_to_wgs84(geom_metric)),
    )
    return parcel, geom_metric


def parse_response(text: str) -> list[tuple[Parcel, BaseGeometry]]:
    """Parse ULDK text output: a status line, then `|`-separated rows in _FIELDS order.

    The status line is "0" (single-result requests) or the match count (search),
    and "-1 <message>" on error.
    """
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        raise UldkError("Empty ULDK response")
    status = lines[0].strip()
    if status.startswith("-1"):
        if "brak" in status.lower():
            raise ParcelNotFound(status)
        raise UldkError(status)
    if not status.isdigit():
        raise UldkError(f"Unexpected ULDK status: {status[:200]}")
    rows = [line for line in lines[1:] if "|" in line]
    if not rows:
        raise ParcelNotFound("ULDK returned no rows")
    return [_parse_row(line) for line in rows]


async def _query(params: dict[str, str]) -> str:
    params = {**params, "result": ",".join(_FIELDS), "srid": str(CRS_METRIC)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(ULDK_URL, params=params)
    response.raise_for_status()
    return response.text


async def get_parcel_by_id(parcel_id: str) -> tuple[Parcel, BaseGeometry]:
    cached = cache.read_json("uldk", parcel_id)
    if cached is None:
        cached = await _query({"request": "GetParcelById", "id": parcel_id})
        parse_response(cached)  # validate before caching
        cache.write_json("uldk", parcel_id, cached)
    return parse_response(cached)[0]


async def get_parcel_by_point(lon: float, lat: float) -> tuple[Parcel, BaseGeometry]:
    text = await _query({"request": "GetParcelByXY", "xy": f"{lon},{lat},{CRS_WGS84}"})
    parcel, geom = parse_response(text)[0]
    return parcel, geom


async def search_parcels(query: str) -> list[Parcel]:
    """Full parcel id (e.g. 040706_5.0016.51/1) or "<region name> <number>" (e.g. Karczyn 51/1)."""
    text = await _query({"request": "GetParcelByIdOrNr", "id": query.strip()})
    return [parcel for parcel, _ in parse_response(text)[:MAX_SEARCH_RESULTS]]
