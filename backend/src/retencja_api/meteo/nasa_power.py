"""Fallback daily weather from NASA POWER (MERRA-2 reanalysis, ~50 km grid), used when
Open-Meteo is unavailable or over its free quota. ET0 is computed here with the FAO-56
Penman-Monteith equation (Hargreaves where solar radiation is not yet published)."""

from datetime import date, timedelta

import httpx
import numpy as np

from retencja_api.cache import read_json, write_json
from retencja_api.meteo.openmeteo import DailyWeather

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = ("PRECTOTCORR", "T2M_MAX", "T2M_MIN", "T2M", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN",
          "GWETROOT")
_FILL = -999.0
_SETTLED_DAYS = 10


async def _request(lat: float, lon: float, start: date, end: date) -> dict:
    params = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "latitude": f"{lat:.2f}",
        "longitude": f"{lon:.2f}",
        "start": f"{start:%Y%m%d}",
        "end": f"{end:%Y%m%d}",
        "format": "JSON",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(POWER_URL, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_daily_power(lat: float, lon: float, start: date, end: date) -> DailyWeather:
    lat, lon = round(lat, 1), round(lon, 1)
    settled = date.today() - timedelta(days=_SETTLED_DAYS)
    final_end = min(end, settled.replace(day=1) - timedelta(days=1))
    key = f"{lat:.1f},{lon:.1f}:{start}:{final_end}"
    history = read_json("nasa-power", key)
    if history is None:
        history = await _request(lat, lon, start, final_end)
        write_json("nasa-power", key, history)
    payloads = [history]
    if final_end < end:
        payloads.append(await _request(lat, lon, final_end + timedelta(days=1), end))
    return parse_power(payloads)


def parse_power(payloads: list[dict]) -> DailyWeather:
    series: dict[str, list[float]] = {p: [] for p in PARAMS}
    days: list[date] = []
    for payload in payloads:
        params = payload["properties"]["parameter"]
        keys = sorted(params["PRECTOTCORR"])
        days += [date(int(k[:4]), int(k[4:6]), int(k[6:])) for k in keys]
        for p in PARAMS:
            series[p] += [params[p][k] for k in keys]
    arr = {p: np.where(np.array(v) == _FILL, np.nan, np.array(v, dtype=float))
           for p, v in series.items()}
    lon, lat, elevation = payloads[0]["geometry"]["coordinates"]
    et0 = penman_monteith(
        days, lat, elevation, arr["T2M"], arr["T2M_MAX"], arr["T2M_MIN"], arr["RH2M"],
        arr["WS2M"], arr["ALLSKY_SFC_SW_DWN"],
    )
    return DailyWeather(
        days=days,
        precipitation=arr["PRECTOTCORR"],
        et0=et0,
        tmax=arr["T2M_MAX"],
        soil_moisture=arr["GWETROOT"],  # root-zone wetness 0–1 (relative, not m³/m³)
        latitude=lat,
        longitude=lon,
        soil_moisture_source="MERRA-2 (NASA POWER)",
    )


def _sat_vapour(t: np.ndarray) -> np.ndarray:
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def extraterrestrial_radiation(days: list[date], lat: float) -> np.ndarray:
    """Ra in MJ m⁻² day⁻¹ (FAO-56 eq. 21)."""
    j = np.array([d.timetuple().tm_yday for d in days], dtype=float)
    phi = np.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365)
    delta = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    return (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws)
    )


def penman_monteith(
    days: list[date], lat: float, elevation: float, t: np.ndarray, tmax: np.ndarray,
    tmin: np.ndarray, rh: np.ndarray, u2: np.ndarray, rs: np.ndarray,
) -> np.ndarray:
    """FAO-56 reference evapotranspiration (mm/day); Hargreaves (eq. 52) where Rs is missing."""
    ra = extraterrestrial_radiation(days, lat)
    pressure = 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    gamma = 0.000665 * pressure
    delta = 4098 * _sat_vapour(t) / (t + 237.3) ** 2
    es = (_sat_vapour(tmax) + _sat_vapour(tmin)) / 2
    ea = rh / 100 * es
    rso = (0.75 + 2e-5 * elevation) * ra
    rnl = (
        4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2
        * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0)))
        * (1.35 * np.clip(rs / rso, 0.25, 1.0) - 0.35)
    )
    rn = 0.77 * rs - rnl
    et0 = (0.408 * delta * rn + gamma * 900 / (t + 273) * u2 * (es - ea)) / (
        delta + gamma * (1 + 0.34 * u2)
    )
    hargreaves = 0.0023 * (t + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0)) * 0.408 * ra
    return np.maximum(np.where(np.isfinite(rs), et0, hargreaves), 0)
