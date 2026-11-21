"""Client for ULDK (GUGiK parcel locator): coordinates or id → cadastral parcel."""

import httpx
from shapely import wkt
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from retencja_api import cache
from retencja_api.config import CRS_METRIC, CRS_WGS84, ULDK_URL
from retencja_api.geo import geometry_to_wgs84
from retencja_api.models import Parcel

_FIELDS = ["id", "voivodeship", "county", "commune", "region", "parcel", "geom_wkt"]


class ParcelNotFound(Exception):
    pass


class UldkError(Exception):
    pass


def parse_response(text: str) -> tuple[Parcel, BaseGeometry]:
    """Parse ULDK text output: status line, then `|`-separated rows in _FIELDS order."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        raise UldkError("Empty ULDK response")
    status = lines[0].strip()
    if status != "0":
        if "brak" in status.lower():
            raise ParcelNotFound(status)
        raise UldkError(status)
    if len(lines) < 2:
        raise ParcelNotFound("ULDK returned no rows")

    values = lines[1].split("|")
    if len(values) != len(_FIELDS):
        raise UldkError(f"Unexpected ULDK row: {lines[1][:200]}")
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
    return parse_response(cached)


async def get_parcel_by_point(lon: float, lat: float) -> tuple[Parcel, BaseGeometry]:
    text = await _query({"request": "GetParcelByXY", "xy": f"{lon},{lat},{CRS_WGS84}"})
    parcel, geom = parse_response(text)
    cache.write_json("uldk", parcel.id, text)
    return parcel, geom
