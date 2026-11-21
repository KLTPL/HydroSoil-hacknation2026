import asyncio
import json
from datetime import date

import httpx
import pytest
from conftest import WRITE, make_parcel, make_report, register
from fastapi.testclient import TestClient
from shapely.geometry import box

from retencja_api import api
from retencja_api.accounts import auth, batch, data_routes, parcels
from retencja_api.parcel.uldk import ParcelNotFound

PARCEL_ID = "040706_5.0016.51/1"
OTHER_ID = "040706_5.0016.52"
TODAY = date.today().isoformat()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """ULDK lookups and the report builder are stubbed; levels are set per parcel id."""
    levels = {PARCEL_ID: "moderate", OTHER_ID: "severe"}

    async def parcel_by_id(parcel_id: str):
        if parcel_id not in levels:
            raise ParcelNotFound(parcel_id)
        return make_parcel(parcel_id), box(0, 0, 100, 100)

    async def build(parcel, geom, crop, day, budget_s=None, on_module=None):
        return make_report(parcel, levels[parcel.id], crop.id, day.isoformat())

    for module in (api, data_routes, batch):
        monkeypatch.setattr(module, "get_parcel_by_id", parcel_by_id)
    for module in (api, batch):
        monkeypatch.setattr(module, "build_report", build)
    return levels


def save(client: TestClient, parcel_id: str = PARCEL_ID, **extra):
    return client.post("/api/account/parcels", headers=WRITE,
                       json={"parcel_id": parcel_id, "crop": "zboza_ozime", **extra})


def analyse(client: TestClient, parcel_id: str = PARCEL_ID, poll: bool = False):
    return client.get("/api/analysis", params={"parcel_id": parcel_id, "crop": "zboza_ozime",
                                               "date": TODAY, "poll": str(poll).lower()})


def test_saved_parcels_crud(client):
    register(client)

    created = save(client, name="  Pole za stodołą ")
    assert created.status_code == 201, created.text
    saved = created.json()
    assert saved["name"] == "Pole za stodołą"
    assert saved["number"] == "51/1"
    assert save(client).status_code == 409  # already on the list

    renamed = client.patch(f"/api/account/parcels/{saved['id']}", headers=WRITE,
                           json={"name": "Duże pole", "crop": "rzepak"})
    assert renamed.json()["name"] == "Duże pole"
    assert renamed.json()["crop"] == "rzepak"
    cleared = client.patch(f"/api/account/parcels/{saved['id']}", headers=WRITE,
                           json={"name": ""})
    assert cleared.json()["name"] is None
    assert cleared.json()["crop"] == "rzepak"

    assert [p["id"] for p in client.get("/api/account/parcels").json()] == [saved["id"]]
    assert client.delete(f"/api/account/parcels/{saved['id']}", headers=WRITE).status_code == 204
    assert client.get("/api/account/parcels").json() == []


def test_saving_validates_crop_and_parcel(client):
    register(client)
    assert client.post("/api/account/parcels", headers=WRITE,
                       json={"parcel_id": PARCEL_ID, "crop": "x"}).status_code == 422
    assert save(client, "000000_0.0000.0").status_code == 404


def test_users_never_see_each_others_parcels_or_reports(client):
    register(client, "alicja")
    saved = save(client).json()
    analyse(client)
    (report,) = client.get("/api/account/reports").json()

    bob = TestClient(api.app)
    register(bob, "bartek")
    assert bob.get("/api/account/parcels").json() == []
    assert bob.get("/api/account/reports").json() == []
    assert bob.get("/api/account/reports", params={"parcel_id": PARCEL_ID}).json() == []
    assert bob.get(f"/api/account/reports/{report['id']}").status_code == 404
    assert bob.patch(f"/api/account/parcels/{saved['id']}", headers=WRITE,
                     json={"name": "moje"}).status_code == 404
    assert bob.delete(f"/api/account/parcels/{saved['id']}", headers=WRITE).status_code == 404
    # Alicja's data is untouched.
    assert client.get("/api/account/parcels").json()[0]["name"] is None
    assert client.get(f"/api/account/reports/{report['id']}").status_code == 200


def test_anonymous_analysis_is_not_archived(client, accounts_db):
    assert analyse(client).status_code == 200
    register(client)
    assert client.get("/api/account/reports").json() == []


def test_archive_keeps_each_analysis_and_compares_with_the_previous(client, offline):
    register(client)
    analyse(client)
    offline[PARCEL_ID] = "severe"
    analyse(client)

    newest, oldest = client.get("/api/account/reports", params={"parcel_id": PARCEL_ID}).json()
    assert (newest["level"], oldest["level"]) == ("severe", "moderate")
    assert newest["top_recommendation"] == "Mulczowanie"

    archived = client.get(f"/api/account/reports/{newest['id']}").json()
    assert archived["report"]["diagnosis"]["level"] == "severe"
    assert archived["previous"]["id"] == oldest["id"]
    first = client.get(f"/api/account/reports/{oldest['id']}").json()
    assert first["previous"] is None


def test_polling_refresh_updates_the_latest_snapshot(client, offline):
    register(client)
    analyse(client)
    offline[PARCEL_ID] = "watch"  # e.g. terrain arrived and refined the verdict
    analyse(client, poll=True)

    (only,) = client.get("/api/account/reports").json()
    assert only["level"] == "watch"


def test_streamed_analysis_is_archived(client):
    register(client)
    response = client.get("/api/analysis/stream",
                          params={"parcel_id": PARCEL_ID, "crop": "zboza_ozime", "date": TODAY})
    assert response.status_code == 200
    assert len(client.get("/api/account/reports").json()) == 1


def _rows(body: str) -> list[dict]:
    rows = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if fields.get("event") == "row":
            rows.append(json.loads(fields["data"]))
    return rows


def test_batch_analyses_every_saved_parcel_and_archives_it(client):
    register(client)
    save(client, name="Pole A")
    save(client, OTHER_ID)

    response = client.get("/api/account/batch/stream", params={"date": TODAY})

    assert response.status_code == 200, response.text
    rows = {r["parcel_id"]: r for r in _rows(response.text)}
    assert rows[PARCEL_ID]["level"] == "moderate"
    assert rows[PARCEL_ID]["name"] == "Pole A"
    assert rows[OTHER_ID]["level"] == "severe"
    assert rows[OTHER_ID]["top_recommendation"] == "Mulczowanie"
    assert all(r["status"] == "ok" and r["report_id"] for r in rows.values())
    assert len(client.get("/api/account/reports").json()) == 2
    listed = client.get("/api/account/parcels").json()
    assert all(p["last_analysed_at"] for p in listed)


def test_batch_reports_a_failing_parcel_without_stopping(client, offline, monkeypatch):
    register(client)
    save(client)
    save(client, OTHER_ID)

    async def flaky(parcel_id: str):
        if parcel_id == OTHER_ID:
            raise httpx.ConnectError("down")
        return make_parcel(parcel_id), box(0, 0, 100, 100)

    monkeypatch.setattr(batch, "get_parcel_by_id", flaky)
    rows = {r["parcel_id"]: r for r in _rows(
        client.get("/api/account/batch/stream", params={"date": TODAY}).text)}

    assert rows[PARCEL_ID]["status"] == "ok"
    assert rows[OTHER_ID]["status"] == "error"
    assert rows[OTHER_ID]["message"]


def test_batch_requires_login_and_a_valid_date(client):
    assert client.get("/api/account/batch/stream").status_code == 401
    register(client)
    assert client.get("/api/account/batch/stream", params={"date": "2001-01-01"}).status_code == 422


async def test_batch_limits_concurrency(accounts_db, monkeypatch):
    active = 0
    peak = 0

    async def slow(parcel, geom, crop, day, budget_s=None, on_module=None):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return make_report(parcel)

    async def parcel_by_id(parcel_id: str):
        return make_parcel(parcel_id), box(0, 0, 100, 100)

    monkeypatch.setattr(batch, "build_report", slow)
    monkeypatch.setattr(batch, "get_parcel_by_id", parcel_by_id)
    user = auth.create_user("rolnik", "dobre-haslo-123")
    saved = [parcels.save_parcel(user.id, make_parcel(f"040706_5.0016.{n}"), "zboza_ozime", None)
             for n in range(6)]

    rows = [row async for row in batch.run_batch(user.id, saved, date(2025, 6, 1))]

    assert len(rows) == 6
    assert peak == batch.BATCH_CONCURRENCY
    assert not batch.is_running(user.id)
