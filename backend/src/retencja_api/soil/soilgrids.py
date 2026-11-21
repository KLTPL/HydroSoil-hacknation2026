"""Soil texture and organic carbon from SoilGrids 2.0 (ISRIC, 250 m) via WCS, turned into
plant-available water capacity (Saxton & Rawls 2006) and the IUNG soil category."""

import asyncio
from io import BytesIO

import httpx
import numpy as np
import rasterio

from retencja_api.cache import read_json, write_json
from retencja_api.models import SoilLayer, SoilProfile

WCS_URL = "https://maps.isric.org/mapserv"
PROPERTIES = ("clay", "sand", "soc")
# (label, thickness cm); the root zone analysed is 0–100 cm.
DEPTHS = (("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15), ("30-60cm", 30), ("60-100cm", 40))
RESOLUTION_M = 250.0
_BUFFER_DEG = 0.003  # at least one full 250 m cell around small parcels
_CONCURRENCY = 8

Bounds = tuple[float, float, float, float]  # lon/lat


class SoilDataMissing(RuntimeError):
    pass


async def _coverage_mean(client: httpx.AsyncClient, prop: str, depth: str, b: Bounds) -> float:
    params = [
        ("map", f"/map/{prop}.map"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", f"{prop}_{depth}_mean"),
        ("FORMAT", "image/tiff"),
        ("SUBSET", f"long({b[0] - _BUFFER_DEG:.5f},{b[2] + _BUFFER_DEG:.5f})"),
        ("SUBSET", f"lat({b[1] - _BUFFER_DEG:.5f},{b[3] + _BUFFER_DEG:.5f})"),
        ("SUBSETTINGCRS", "http://www.opengis.net/def/crs/EPSG/0/4326"),
        ("OUTPUTCRS", "http://www.opengis.net/def/crs/EPSG/0/4326"),
    ]
    response = await client.get(WCS_URL, params=params)
    response.raise_for_status()
    with rasterio.open(BytesIO(response.content)) as ds:
        values = ds.read(1).astype(float)
        nodata = ds.nodata
    valid = values[(values > 0) & (values != nodata)] if nodata is not None else values[values > 0]
    if valid.size == 0:
        raise SoilDataMissing(f"SoilGrids has no {prop} data at {depth}")
    return float(valid.mean())


async def fetch_raw(bounds: Bounds) -> dict[str, list[float]]:
    """Raw SoilGrids values per property and depth (clay/sand g/kg, soc dg/kg)."""
    key = ",".join(f"{v:.4f}" for v in bounds)
    cached = read_json("soilgrids", key)
    if cached is not None:
        return cached
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def one(client: httpx.AsyncClient, prop: str, depth: str) -> float:
        async with semaphore:
            return await _coverage_mean(client, prop, depth, bounds)

    async with httpx.AsyncClient(timeout=15) as client:
        jobs = {
            prop: [one(client, prop, depth) for depth, _ in DEPTHS] for prop in PROPERTIES
        }
        results = {prop: await asyncio.gather(*coros) for prop, coros in jobs.items()}
    write_json("soilgrids", key, results)
    return results


def available_water(sand: float, clay: float, organic_matter_pct: float) -> float:
    """Field capacity − wilting point (m³/m³), Saxton & Rawls (2006); inputs as fractions."""
    om = min(organic_matter_pct, 8.0)
    s, c = sand, clay
    wp_t = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om
    wp_t += 0.068 * s * c + 0.031
    wp = wp_t + (0.14 * wp_t - 0.02)
    fc_t = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om
    fc_t += 0.452 * s * c + 0.299
    fc = fc_t + (1.283 * fc_t**2 - 0.374 * fc_t - 0.015)
    return max(fc - wp, 0.02)


def soil_category(sand_pct: float, clay_pct: float) -> tuple[str, str, str]:
    """Texture group and IUNG drought-susceptibility category (I = most susceptible)."""
    if sand_pct >= 85 and clay_pct < 6:
        return "piasek luźny lub słabogliniasty", "I", "bardzo podatna na suszę"
    if sand_pct >= 70 and clay_pct < 10:
        return "piasek gliniasty", "II", "podatna na suszę"
    if clay_pct < 20:
        return "glina lekka, glina piaszczysta lub pył", "III", "średnio podatna na suszę"
    return "glina średnia lub ciężka, ił", "IV", "mało podatna na suszę"


def build_profile(raw: dict[str, list[float]]) -> SoilProfile:
    layers = []
    awc_mm = 0.0
    for i, (label, thickness_cm) in enumerate(DEPTHS):
        clay = raw["clay"][i] / 10  # g/kg → %
        sand = raw["sand"][i] / 10
        soc = raw["soc"][i] / 100  # dg/kg → %
        layers.append(
            SoilLayer(
                depth=label,
                clay_pct=round(clay, 1),
                sand_pct=round(sand, 1),
                silt_pct=round(max(100 - clay - sand, 0), 1),
                organic_carbon_pct=round(soc, 2),
            )
        )
        awc_mm += available_water(sand / 100, clay / 100, soc * 1.724) * thickness_cm * 10
    topsoil = layers[:3]
    weights = np.array([t for _, t in DEPTHS[:3]], dtype=float)

    def top(attr: str) -> float:
        return float(np.average([getattr(layer, attr) for layer in topsoil], weights=weights))

    texture, category, label = soil_category(top("sand_pct"), top("clay_pct"))
    return SoilProfile(
        texture=texture,
        category=category,
        category_label=label,
        awc_mm_per_m=round(awc_mm, 1),  # 0–100 cm profile = per metre
        organic_carbon_pct=round(top("organic_carbon_pct"), 2),
        layers=layers,
        resolution_m=RESOLUTION_M,
    )


# Used when SoilGrids is unreachable: a medium soil, flagged as assumed in the report.
DEFAULT_PROFILE = SoilProfile(
    texture="nieznana (przyjęto glinę lekką)",
    category="III",
    category_label="średnio podatna na suszę (założenie)",
    awc_mm_per_m=150.0,
    organic_carbon_pct=1.0,
    layers=[],
    resolution_m=RESOLUTION_M,
    assumed=True,
)
