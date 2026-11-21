from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from retencja_api import api, config
from retencja_api.accounts import ratelimit
from retencja_api.crops import CROPS_BY_ID
from retencja_api.models import (
    AnalysisReport,
    Diagnosis,
    ModuleResult,
    Parcel,
    Range,
    Recommendation,
)

WRITE = {"X-HydroSoil": "1"}
PASSWORD = "dobre-haslo-123"


def make_parcel(parcel_id: str = "040706_5.0016.51/1") -> Parcel:
    return Parcel(id=parcel_id, voivodeship="kujawsko-pomorskie", county="powiat inowrocławski",
                  commune="Kruszwica", region="Karczyn", number=parcel_id.rsplit(".", 1)[-1],
                  area_ha=17.3, geometry={"type": "Polygon", "coordinates": []})


def make_report(parcel: Parcel, level: str = "moderate", crop: str = "zboza_ozime",
                analysis_date: str = "2025-06-01") -> AnalysisReport:
    """A minimal report with no module data, as the archive and batch only read the summary."""
    missing = ModuleResult(status="unavailable", message="offline", duration_ms=0)
    return AnalysisReport(
        parcel=parcel,
        crop=CROPS_BY_ID[crop],
        analysis_date=analysis_date,
        generated_at=datetime.now(UTC),
        diagnosis=Diagnosis(level=level, headline=f"Ocena {level}", evidence=[], causes=[],
                            confidence="low", limitations=[], missing_data=[]),
        recommendations=[
            Recommendation(key="k", category="soil", title="Mulczowanie", action="a", why="w",
                           effect_m3=Range(low=1, high=2), effect_note=None, when="teraz",
                           cost="niski", formalities=None)
        ],
        water=missing, soil=missing, satellite=missing, hydro=missing, land=missing,
        terrain=missing, edo=missing,
    )


@pytest.fixture
def accounts_db(tmp_path, monkeypatch):
    """A fresh accounts database and rate limits for each test."""
    monkeypatch.setattr(config, "ACCOUNTS_DB_PATH", tmp_path / "accounts.sqlite3")
    for window in (ratelimit.login_per_user, ratelimit.login_global, ratelimit.registrations):
        window.clear()
    return tmp_path / "accounts.sqlite3"


@pytest.fixture
def client(accounts_db) -> TestClient:
    return TestClient(api.app)


def register(client: TestClient, username: str = "rolnik", password: str = PASSWORD):
    return client.post("/api/account/register", json={"username": username, "password": password},
                       headers=WRITE)
