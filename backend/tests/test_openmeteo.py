from datetime import date, timedelta

import httpx
import pytest

from retencja_api.meteo import openmeteo


def _payload(start: date, end: date) -> dict:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return {
        "latitude": 52.0,
        "longitude": 17.0,
        "daily": {
            "time": [d.isoformat() for d in days],
            **{name: [1.0] * len(days) for name in openmeteo.DAILY_VARS},
        },
    }


@pytest.fixture
def requests(monkeypatch, tmp_path):
    monkeypatch.setattr("retencja_api.cache.CACHE_DIR", tmp_path)
    calls: list[tuple[date, date]] = []

    async def fake_request(lat, lon, start, end):
        calls.append((start, end))
        return _payload(start, end)

    monkeypatch.setattr(openmeteo, "_request", fake_request)
    return calls


async def test_one_history_download_serves_every_analysis_date(requests):
    for start, end in [(date(2012, 11, 1), date(2023, 6, 15)),
                       (date(2008, 11, 1), date(2019, 7, 20))]:
        weather, _ = await openmeteo.fetch_daily(52.04, 17.01, start, end)
        assert weather.days[0] == start and weather.days[-1] == end
    assert len(requests) == 1


async def test_recent_days_are_appended_to_the_history(requests):
    end = date.today() - timedelta(days=1)
    weather, downloaded = await openmeteo.fetch_daily(52.0, 17.0, date(2015, 11, 1), end)
    assert weather.days[-1] == end
    assert len(weather.days) == (end - date(2015, 11, 1)).days + 1
    assert downloaded is None
    assert len(requests) == 2


async def test_rate_limit_skips_open_meteo_until_backoff_ends(monkeypatch):
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(429, json={"reason": "Daily API request limit exceeded"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(openmeteo.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=transport, **kw))
    monkeypatch.setattr(openmeteo, "_rate_limited_until", None)
    with pytest.raises(httpx.HTTPStatusError):
        await openmeteo._request(52.0, 17.0, date(2020, 1, 1), date(2020, 1, 31))
    with pytest.raises(openmeteo.RateLimitedError):
        await openmeteo._request(52.0, 17.0, date(2020, 1, 1), date(2020, 1, 31))
    assert len(sent) == 1
