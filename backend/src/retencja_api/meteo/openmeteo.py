"""Daily weather history at the parcel from the Open-Meteo historical weather API
(ERA5 / ERA5-Land reanalysis blended with recent high-resolution model data)."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

import httpx
import numpy as np

from retencja_api.cache import cached_at, read_json, write_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = (
    "precipitation_sum",
    "et0_fao_evapotranspiration",
    "temperature_2m_max",
    "soil_moisture_0_to_100cm_mean",
)
# Data of the last days may still be revised; older responses are cached for good.
_FINAL_AFTER_DAYS = 10
# One history per grid cell serves every analysis date: 10 compared years plus spin-up
# before the oldest date the app accepts.
HISTORY_START = date(2005, 11, 1)
# After a 429 the free quota is spent (often for the rest of the day); skip Open-Meteo
# for a while instead of spending each poll on a refused request.
RATE_LIMIT_BACKOFF = timedelta(hours=1)
_rate_limited_until: datetime | None = None


class RateLimitedError(httpx.HTTPError):
    """Open-Meteo refused recently with 429; not asked again until the backoff ends."""


@dataclass(frozen=True)
class DailyWeather:
    days: list[date]
    precipitation: np.ndarray  # mm/day
    et0: np.ndarray  # FAO-56 reference evapotranspiration, mm/day
    tmax: np.ndarray  # °C
    soil_moisture: np.ndarray  # m³/m³ in 0–100 cm (ERA5-Land), NaN where missing
    latitude: float  # grid cell actually used
    longitude: float
    soil_moisture_source: str = "ERA5-Land"

    def last_complete_day(self) -> date:
        valid = np.flatnonzero(np.isfinite(self.precipitation) & np.isfinite(self.et0))
        return self.days[int(valid[-1])]

    def index(self, day: date) -> int:
        return (day - self.days[0]).days

    def between(self, start: date, end: date) -> "DailyWeather":
        i, j = max(0, self.index(start)), self.index(end) + 1
        return replace(
            self,
            days=self.days[i:j],
            precipitation=self.precipitation[i:j],
            et0=self.et0[i:j],
            tmax=self.tmax[i:j],
            soil_moisture=self.soil_moisture[i:j],
        )

    def followed_by(self, later: "DailyWeather") -> "DailyWeather":
        return replace(
            self,
            days=self.days + later.days,
            precipitation=np.concatenate([self.precipitation, later.precipitation]),
            et0=np.concatenate([self.et0, later.et0]),
            tmax=np.concatenate([self.tmax, later.tmax]),
            soil_moisture=np.concatenate([self.soil_moisture, later.soil_moisture]),
        )


async def _request(lat: float, lon: float, start: date, end: date) -> dict:
    global _rate_limited_until
    now = datetime.now(UTC)
    if _rate_limited_until is not None and now < _rate_limited_until:
        raise RateLimitedError(f"Open-Meteo rate limit, retry after {_rate_limited_until}")
    params = {
        "latitude": f"{lat:.2f}",
        "longitude": f"{lon:.2f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARS),
        "timezone": "Europe/Warsaw",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(ARCHIVE_URL, params=params)
        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            _rate_limited_until = now + RATE_LIMIT_BACKOFF
        response.raise_for_status()
        return response.json()


async def fetch_daily(
    lat: float, lon: float, start: date, end: date
) -> tuple[DailyWeather, datetime | None]:
    """Daily series for the 0.1° grid cell containing the point.

    The long history of a cell is fetched once a month and cached (the free API counts
    long requests as many calls); only the last, still-revised days are fetched each time.
    Returns the series and, if nothing had to be downloaded now, when it was downloaded.
    """
    lat, lon = round(lat, 1), round(lon, 1)
    # History ends on a month boundary, so its cache entry is reused for a whole month.
    settled = date.today() - timedelta(days=_FINAL_AFTER_DAYS)
    history_start = min(start, HISTORY_START)
    history_end = settled.replace(day=1) - timedelta(days=1)
    key = f"{lat:.1f},{lon:.1f}:{history_start}:{history_end}"
    history = read_json("open-meteo", key)
    downloaded = cached_at("open-meteo", key)
    if history is None:
        history = await _request(lat, lon, history_start, history_end)
        write_json("open-meteo", key, history)
    weather = parse_daily(history)
    if end > history_end:
        recent = await _request(lat, lon, history_end + timedelta(days=1), end)
        weather = weather.followed_by(parse_daily(recent))
        downloaded = None
    return weather.between(start, end), downloaded


def parse_daily(payload: dict) -> DailyWeather:
    daily = payload["daily"]

    def series(name: str) -> np.ndarray:
        return np.array([np.nan if v is None else v for v in daily[name]], dtype=float)

    return DailyWeather(
        days=[date.fromisoformat(d) for d in daily["time"]],
        precipitation=series("precipitation_sum"),
        et0=series("et0_fao_evapotranspiration"),
        tmax=series("temperature_2m_max"),
        soil_moisture=series("soil_moisture_0_to_100cm_mean"),
        latitude=payload["latitude"],
        longitude=payload["longitude"],
    )
