"""Current hydrological drought warnings from the IMGW-PIB public data API.

IMGW publishes only warnings in force now (no archive). Warnings name a voivodeship
and hydrological catchment codes; catchment geometry is not published, so parcels are
matched by voivodeship and the warning text names the catchment.
"""

import httpx

from retencja_api.models import HydroStatus, HydroWarning

WARNINGS_URL = "https://danepubliczne.imgw.pl/api/data/warningshydro"
DROUGHT_EVENT = "Susza hydrologiczna"


async def fetch_warnings() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(WARNINGS_URL)
        response.raise_for_status()
        return response.json()


def warnings_for(voivodeship: str, warnings: list[dict]) -> HydroStatus:
    voivodeship = voivodeship.lower()
    drought, other = [], 0
    for warning in warnings:
        areas = [a for a in warning["obszary"] if a["wojewodztwo"].lower() == voivodeship]
        if not areas:
            continue
        if warning["zdarzenie"] != DROUGHT_EVENT:
            other += 1
            continue
        valid_to = warning.get("data_do")
        drought.append(
            HydroWarning(
                number=warning["numer"],
                event=warning["zdarzenie"],
                probability_pct=int(warning["prawdopodobienstwo"]),
                valid_from=warning["data_od"],
                valid_to=None if not valid_to or valid_to.startswith("9999") else valid_to,
                office=warning["biuro"],
                area="; ".join(a["opis"] for a in areas),
                description=warning["przebieg"],
            )
        )
    return HydroStatus(voivodeship=voivodeship, drought_warnings=drought, other_warnings=other)
