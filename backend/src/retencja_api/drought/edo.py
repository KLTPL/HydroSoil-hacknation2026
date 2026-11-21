"""Combined Drought Indicator (CDI v4) of the European Drought Observatory (Copernicus EMS),
read at the parcel through the observatory's WCS. Used as an independent cross-check."""

from datetime import date, datetime, timedelta

import httpx
import numpy as np
from rasterio.io import MemoryFile

from retencja_api.cache import cached_at, read_json, write_json

WCS_URL = "https://drought.emergency.copernicus.eu/api/wcs"
COVERAGE_ID = "cdiad"
_HALF_WINDOW_DEG = 0.05  # the grid is 1/24° (~4.6 km); a small window around the point
# The latest dekads are published with a delay; step back this many to find the newest.
_MAX_STEPS_BACK = 3
# Recent maps may still be recomputed; older ones are cached for good.
_FINAL_AFTER = timedelta(days=60)
_OUT_OF_RANGE = "outside the available coverage range"

# Class value → (label in the report, whether it means drought)
CDI_CLASSES: dict[int, tuple[str, bool]] = {
    0: ("brak suszy", False),
    1: ("Watch: niedobór opadów", True),
    2: ("Warning: niedobór opadów i wilgoci w glebie", True),
    3: ("Alert: niedobór opadów, wilgoci w glebie i stres roślinności", True),
    4: ("pełna odbudowa po suszy", False),
    5: ("częściowa odbudowa (wilgotność gleby)", False),
    6: ("częściowa odbudowa (roślinność)", False),
}


class CdiNotPublishedError(Exception):
    """No CDI map for the requested date or the few dekads before it."""


def dekad_start(day: date) -> date:
    """CDI maps are dekadal, labelled with the 1st, 11th and 21st day of the month."""
    return day.replace(day=1 if day.day <= 10 else 11 if day.day <= 20 else 21)


def previous_dekad(dekad: date) -> date:
    if dekad.day > 1:
        return dekad.replace(day=dekad.day - 10)
    return (dekad - timedelta(days=1)).replace(day=21)


def sample(tiff: bytes, lat: float, lon: float) -> int:
    with MemoryFile(tiff) as memfile, memfile.open() as dataset:
        value = next(dataset.sample([(lon, lat)]))[0]
    return int(np.asarray(value).item())


async def _request(client: httpx.AsyncClient, lat: float, lon: float, dekad: date) -> bytes | None:
    """GeoTIFF around the point, or None when the dekad is not published (yet)."""
    params = [
        ("map", "DO_WCS"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.0"),
        ("REQUEST", "GetCoverage"),
        ("coverageID", COVERAGE_ID),
        ("CRS", "EPSG:4326"),
        ("format", "GEOTIFF"),
        ("TIME", dekad.isoformat()),
        ("SUBSET", f"lat({lat - _HALF_WINDOW_DEG:.3f},{lat + _HALF_WINDOW_DEG:.3f})"),
        ("SUBSET", f"long({lon - _HALF_WINDOW_DEG:.3f},{lon + _HALF_WINDOW_DEG:.3f})"),
    ]
    response = await client.get(WCS_URL, params=params)
    if response.status_code == httpx.codes.BAD_REQUEST and _OUT_OF_RANGE in response.text:
        return None
    response.raise_for_status()
    return response.content


async def fetch_cdi(lat: float, lon: float, day: date) -> tuple[date, int, datetime | None]:
    """CDI class at the point for the dekad containing `day` (or the newest one before it).
    Returns the dekad, the class value and when it was downloaded if it came from cache."""
    lat, lon = round(lat, 2), round(lon, 2)
    dekad = dekad_start(day)
    async with httpx.AsyncClient(timeout=20) as client:
        for _ in range(_MAX_STEPS_BACK + 1):
            key = f"{lat:.2f},{lon:.2f}:{dekad}"
            if (cached := read_json("edo-cdi", key)) is not None:
                return dekad, cached, cached_at("edo-cdi", key)
            tiff = await _request(client, lat, lon, dekad)
            if tiff is None:
                dekad = previous_dekad(dekad)
                continue
            value = sample(tiff, lat, lon)
            if date.today() - dekad > _FINAL_AFTER:
                write_json("edo-cdi", key, value)
            return dekad, value, None
    raise CdiNotPublishedError(f"No CDI map published up to {dekad_start(day)}")

