"""Assessment modules of the report. Each returns a ModuleResult: data with its sources,
or a plain-language reason why the data is pending or unavailable."""

import logging
import time
from datetime import UTC, date, datetime, timedelta

import httpx

from retencja_api.assessment.crop_params import CropParams
from retencja_api.assessment.scenarios import build_scenarios
from retencja_api.assessment.smsr import smsr_check
from retencja_api.assessment.water_balance import assess_water
from retencja_api.background import run_within
from retencja_api.drought.edo import CDI_CLASSES, CdiNotPublishedError, fetch_cdi
from retencja_api.hydro.imgw import fetch_warnings, warnings_for
from retencja_api.landcover.worldcover import land_cover
from retencja_api.meteo.nasa_power import fetch_daily_power
from retencja_api.meteo.openmeteo import fetch_daily
from retencja_api.models import (
    DataSource,
    EdoDrought,
    HydroStatus,
    LandCover,
    ModuleResult,
    SoilProfile,
    VegetationState,
    WaterBalance,
)
from retencja_api.satellite.service import vegetation_state
from retencja_api.soil.soilgrids import SoilDataMissing, build_profile, fetch_raw

log = logging.getLogger(__name__)

SOURCES = {
    "meteo": (
        "Open-Meteo Historical Weather API (reanaliza ERA5 / ERA5-Land, ECMWF)",
        "https://open-meteo.com/en/docs/historical-weather-api",
        "Dane CC BY 4.0; API bezpłatne do użytku niekomercyjnego",
    ),
    "power": (
        "NASA POWER (reanaliza MERRA-2), ET0 liczone metodą FAO-56 Penman-Monteith",
        "https://power.larc.nasa.gov/",
        "Dane publiczne NASA, bez ograniczeń; wymagane podanie źródła",
    ),
    "soil": (
        "SoilGrids 2.0 (ISRIC), siatka 250 m",
        "https://soilgrids.org",
        "CC BY 4.0",
    ),
    "satellite": (
        "Copernicus Sentinel-2 L2A (ESA) przez Microsoft Planetary Computer",
        "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a",
        "Dane Copernicus: bezpłatne i otwarte (rozp. UE 1159/2013)",
    ),
    "land": (
        "ESA WorldCover 2021 (10 m) przez Microsoft Planetary Computer",
        "https://esa-worldcover.org",
        "CC BY 4.0 © ESA WorldCover project",
    ),
    "edo": (
        "Europejskie Obserwatorium Suszy (EDO, Copernicus EMS), wskaźnik CDI v4.1",
        "https://drought.emergency.copernicus.eu/data/wcs-service",
        "Dane Copernicus: bezpłatne i otwarte (rozp. UE 1159/2013), wymagane podanie źródła",
    ),
    "hydro": (
        "IMGW-PIB, ostrzeżenia hydrologiczne (dane publiczne)",
        "https://danepubliczne.imgw.pl/api/data/warningshydro",
        "Dane publiczne IMGW-PIB, wymagane podanie źródła",
    ),
}
SOIL_BUDGET_S = 12.0
HYDRO_CURRENT_DAYS = 2  # IMGW serves only warnings in force now


def _source(name: str, cached_at: datetime | None = None) -> DataSource:
    """Source entry; `cached_at` is when cached data was originally downloaded."""
    title, url, licence = SOURCES[name]
    return DataSource(
        name=title,
        url=url,
        license=licence,
        retrieved="live" if cached_at is None else "cached",
        retrieved_at=cached_at or datetime.now(UTC),
    )


class _Timer:
    def __init__(self) -> None:
        self.started = time.monotonic()

    def ms(self) -> int:
        return round((time.monotonic() - self.started) * 1000)


async def soil_module(bounds_wgs84: tuple[float, float, float, float]) -> ModuleResult[SoilProfile]:
    timer = _Timer()
    key = "soil:" + ",".join(f"{v:.4f}" for v in bounds_wgs84)
    try:
        raw, downloaded = await run_within(key, lambda: fetch_raw(bounds_wgs84), SOIL_BUDGET_S)
    except (TimeoutError, httpx.HTTPError, SoilDataMissing) as exc:
        log.warning("Soil unavailable: %r", exc)
        return ModuleResult(
            status="unavailable",
            message="Brak danych glebowych SoilGrids dla działki; przyjęto glebę średnią.",
            duration_ms=timer.ms(),
        )
    return ModuleResult(
        status="ok",
        data=build_profile(raw),
        sources=[_source("soil", downloaded)],
        duration_ms=timer.ms(),
    )


def weather_period(day: date, years: int) -> tuple[date, date]:
    """History from the autumn before the oldest compared year (soil-water spin-up)."""
    return date(day.year - years - 1, 11, 1), day


async def water_module(
    lat: float,
    lon: float,
    crop: CropParams,
    day: date,
    awc_mm_per_m: float,
    years: int,
    humus_gain_mm: float = 0.0,
    smsr_crop: tuple[str, str] | None = None,
) -> ModuleResult[WaterBalance]:
    """`smsr_crop`: (crop id, IUNG soil category) for the official drought criterion."""
    timer = _Timer()
    yesterday = date.today() - timedelta(days=1)
    effective = min(day, yesterday)  # today's weather is not complete yet
    start, end = weather_period(effective, years)
    source = "meteo"
    try:
        weather, downloaded = await fetch_daily(lat, lon, start, end)
    except httpx.HTTPError as exc:
        log.warning("Open-Meteo unavailable, falling back to NASA POWER: %r", exc)
        source = "power"
        try:
            weather, downloaded = await fetch_daily_power(lat, lon, start, end)
        except httpx.HTTPError as exc2:
            log.warning("NASA POWER unavailable: %r", exc2)
            return ModuleResult(
                status="unavailable",
                message="Nie udało się pobrać danych pogodowych (Open-Meteo ani NASA POWER).",
                duration_ms=timer.ms(),
            )
    effective = min(effective, weather.last_complete_day())
    data = assess_water(weather, crop, awc_mm_per_m, effective, years)
    if smsr_crop is not None:
        data.smsr = smsr_check(weather, *smsr_crop, effective)
    depletion_mm = data.taw_mm * (1 - data.available_pct.value / 100)
    scenarios = build_scenarios(
        weather, crop, data.taw_mm, depletion_mm, effective, years, humus_gain_mm
    )
    data = data.model_copy(update={"scenarios": scenarios})
    message = (
        f"Najnowsze dostępne dane pogodowe są z {effective:%d.%m.%Y}; ocena dotyczy tego dnia."
        if effective != day
        else None
    )
    return ModuleResult(
        status="ok",
        message=message,
        data=data,
        sources=[_source(source, downloaded)],
        duration_ms=timer.ms(),
    )


async def satellite_module(
    parcel_id: str, geometry_wgs84: dict, day: date, years: int, budget_s: float
) -> ModuleResult[VegetationState]:
    timer = _Timer()
    key = f"satellite:{parcel_id}:{day}"
    try:
        data = await run_within(
            key, lambda: vegetation_state(parcel_id, geometry_wgs84, day, years), budget_s
        )
    except TimeoutError:
        return ModuleResult(
            status="pending",
            message="Pobieram zdjęcia satelitarne Sentinel-2 z 10 lat. Wyniki pojawią się same.",
            duration_ms=timer.ms(),
        )
    except httpx.HTTPError as exc:
        log.warning("Satellite unavailable: %r", exc)
        return ModuleResult(
            status="unavailable",
            message="Serwis zdjęć satelitarnych nie odpowiada. Spróbuj ponownie później.",
            duration_ms=timer.ms(),
        )
    if data.current is None:
        message = (
            f"Brak bezchmurnego zdjęcia działki w {data.window_days} dniach przed datą analizy; "
            "pokazujemy tylko lata, dla których było zdjęcie."
        )
    else:
        message = None
    return ModuleResult(
        status="ok", message=message, data=data, sources=[_source("satellite")],
        duration_ms=timer.ms(),
    )


async def hydro_module(voivodeship: str, day: date) -> ModuleResult[HydroStatus]:
    timer = _Timer()
    if (date.today() - day).days > HYDRO_CURRENT_DAYS:
        return ModuleResult(
            status="unavailable",
            message=(
                "IMGW publikuje tylko bieżące ostrzeżenia hydrologiczne (bez archiwum), "
                f"więc dla {day:%d.%m.%Y} nie można ich sprawdzić."
            ),
            duration_ms=timer.ms(),
        )
    try:
        warnings = await fetch_warnings()
    except httpx.HTTPError as exc:
        log.warning("IMGW unavailable: %r", exc)
        return ModuleResult(
            status="unavailable",
            message="Serwis ostrzeżeń IMGW nie odpowiada.",
            duration_ms=timer.ms(),
        )
    return ModuleResult(
        status="ok",
        data=warnings_for(voivodeship, warnings),
        sources=[_source("hydro")],
        duration_ms=timer.ms(),
    )


EDO_RECENT_CAVEAT = date(2025, 5, 15)  # JRC: soil moisture inputs uncertain since then


async def edo_module(lat: float, lon: float, day: date) -> ModuleResult[EdoDrought]:
    timer = _Timer()
    try:
        dekad, value, downloaded = await fetch_cdi(lat, lon, day)
    except (httpx.HTTPError, CdiNotPublishedError) as exc:
        log.warning("EDO CDI unavailable: %r", exc)
        return ModuleResult(
            status="unavailable",
            message="Europejskie Obserwatorium Suszy nie odpowiada lub nie ma mapy dla tej daty.",
            duration_ms=timer.ms(),
        )
    if value not in CDI_CLASSES:
        return ModuleResult(
            status="unavailable",
            message="Brak wartości wskaźnika CDI w tym miejscu.",
            duration_ms=timer.ms(),
        )
    label, drought = CDI_CLASSES[value]
    message = (
        "JRC zaleca ostrożność przy interpretacji CDI od połowy maja 2025 r. "
        "(niepewne dane o wilgotności gleby)."
        if dekad >= EDO_RECENT_CAVEAT
        else None
    )
    return ModuleResult(
        status="ok",
        message=message,
        data=EdoDrought(dekad=dekad, cdi_class=value, label=label, drought=drought),
        sources=[_source("edo", downloaded)],
        duration_ms=timer.ms(),
    )


LAND_BUDGET_S = 10.0


async def land_module(parcel_id: str, geometry_wgs84: dict) -> ModuleResult[LandCover]:
    timer = _Timer()
    try:
        data, downloaded = await run_within(
            f"land:{parcel_id}", lambda: land_cover(parcel_id, geometry_wgs84), LAND_BUDGET_S
        )
    except (TimeoutError, httpx.HTTPError) as exc:
        log.warning("Land cover unavailable: %r", exc)
        return ModuleResult(
            status="unavailable",
            message="Nie udało się sprawdzić pokrycia terenu (ESA WorldCover).",
            duration_ms=timer.ms(),
        )
    return ModuleResult(
        status="ok", data=data, sources=[_source("land", downloaded)], duration_ms=timer.ms()
    )
