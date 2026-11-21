import asyncio
from datetime import UTC, date, datetime

import httpx
import pytest
from shapely.geometry import box

from retencja_api import report
from retencja_api.api import earliest_analysis_date
from retencja_api.crops import CROPS_BY_ID
from retencja_api.models import (
    Assumptions,
    ModuleResult,
    Parcel,
    Range,
    RetentionAnalysis,
    RetentionSummary,
)

PARCEL = Parcel(
    id="040706_5.0016.51/1",
    voivodeship="kujawsko-pomorskie",
    county="powiat inowrocławski",
    commune="Kruszwica",
    region="Karczyn",
    number="51/1",
    area_ha=17.3,
    geometry={"type": "Polygon", "coordinates": [[[18, 52], [18.1, 52], [18, 52.1], [18, 52]]]},
)
GEOM = box(0, 0, 100, 100)
CROP = CROPS_BY_ID["zboza_ozime"]


def _analysis() -> RetentionAnalysis:
    return RetentionAnalysis(
        parcel_id=PARCEL.id,
        computed_at=datetime.now(UTC),
        summary=RetentionSummary(site_count=0, storage_m3=0, retained_m3=Range(low=0, high=0)),
        sites=[],
        assumptions=Assumptions(
            dem_source="test",
            resolution_m=2,
            design_rain_mm=30,
            runoff_coeff=Range(low=0.05, high=0.25),
            min_depth_m=0.15,
            min_area_m2=300,
        ),
    )


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setattr(report, "cached_analysis", lambda _id: None)


@pytest.fixture(autouse=True)
def offline_modules(monkeypatch):
    """Assessment modules are covered by their own tests; here they report no data."""

    def unavailable(*_args, **_kwargs):
        async def result():
            return ModuleResult(status="unavailable", message="offline", duration_ms=0)

        return result()

    for name in ("soil_module", "water_module", "satellite_module", "hydro_module", "land_module",
                 "edo_module"):
        monkeypatch.setattr(report, name, unavailable)


async def test_terrain_ok_reports_live_source(monkeypatch):
    async def fast(_id, _geom):
        return _analysis()

    monkeypatch.setattr(report, "analyze_parcel", fast)

    result = await report.build_report(PARCEL, GEOM, CROP, date(2025, 6, 1))

    assert result.terrain.status == "ok"
    assert result.terrain.sources[0].retrieved == "live"
    assert result.analysis_date == date(2025, 6, 1)


async def test_slow_terrain_is_pending_and_keeps_running(monkeypatch):
    finished = asyncio.Event()

    async def slow(_id, _geom):
        await asyncio.sleep(0.2)
        finished.set()
        return _analysis()

    monkeypatch.setattr(report, "analyze_parcel", slow)
    monkeypatch.setattr(report, "TERRAIN_TIME_BUDGET_S", 0.01)

    result = await report.build_report(PARCEL, GEOM, CROP, date(2025, 6, 1))

    assert result.terrain.status == "pending"
    assert result.terrain.data is None
    await asyncio.wait_for(finished.wait(), 1)  # background computation was not cancelled


async def test_upstream_failure_is_reported_as_unavailable(monkeypatch):
    async def failing(_id, _geom):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(report, "analyze_parcel", failing)

    result = await report.build_report(PARCEL, GEOM, CROP, date(2025, 6, 1))

    assert result.terrain.status == "unavailable"
    assert result.terrain.message


async def test_missing_modules_are_listed_and_lower_confidence(monkeypatch):
    async def fast(_id, _geom):
        return _analysis()

    monkeypatch.setattr(report, "analyze_parcel", fast)

    result = await report.build_report(PARCEL, GEOM, CROP, date(2025, 6, 1))

    assert result.diagnosis.confidence == "low"
    assert len(result.diagnosis.missing_data) == 5  # all but terrain
    assert all("offline" in m for m in result.diagnosis.missing_data)


def test_earliest_analysis_date_handles_leap_day():
    assert earliest_analysis_date(date(2028, 2, 29)) == date(2018, 2, 28)
    assert earliest_analysis_date(date(2026, 11, 21)) == date(2016, 11, 21)


async def test_huge_parcel_skips_terrain(monkeypatch):
    async def never(_id, _geom):
        raise AssertionError("terrain must not be computed")

    monkeypatch.setattr(report, "analyze_parcel", never)

    result = await report.terrain_module(PARCEL.id, box(0, 0, 2000, 2000), 1.0)  # 400 ha

    assert result.status == "unavailable"
    assert "400 ha" in result.message
