import json
from datetime import date

from fastapi.testclient import TestClient
from shapely.geometry import box

from retencja_api import api
from retencja_api.models import ModuleResult, Parcel


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            out.append((fields["event"], json.loads(fields["data"])))
    return out


def test_invalid_crop_is_rejected_before_the_stream_starts():
    response = TestClient(api.app).get(
        "/api/analysis/stream", params={"parcel_id": "040706_5.0016.51/1", "crop": "x"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Nieznana uprawa"


def test_stream_sends_each_module_then_the_report(monkeypatch):
    parcel = Parcel(id="000000_0.0001.1", voivodeship="v", county="c", commune="g", region="r",
                    number="1", area_ha=1.0, geometry={"type": "Polygon", "coordinates": []})

    async def fake_parcel(parcel_id: str):
        return parcel, box(0, 0, 100, 100)

    async def fake_report(parcel, geom, crop, day, budget_s=None, on_module=None):
        on_module("hydro", ModuleResult(status="unavailable", message="brak archiwum",
                                        duration_ms=1))
        return {"parcel_id": parcel.id, "date": day.isoformat()}

    monkeypatch.setattr(api, "get_parcel_by_id", fake_parcel)
    monkeypatch.setattr(api, "build_report", fake_report)
    response = TestClient(api.app).get(
        "/api/analysis/stream",
        params={
            "parcel_id": "000000_0.0001.1", "crop": "zboza_ozime", "date": date.today().isoformat()
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    assert [e for e, _ in events] == ["module", "report"]
    assert events[0][1]["fact"] == "brak archiwum"
    assert events[1][1]["parcel_id"] == "000000_0.0001.1"
