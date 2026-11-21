"""Request and response models of the account API (kept apart from the analysis models)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from retencja_api.models import AnalysisReport, DroughtLevel

USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    # Upper bound keeps hashing cost bounded; no composition rules beyond length.
    password: str = Field(min_length=8, max_length=128)


class User(BaseModel):
    id: int
    username: str


class Me(BaseModel):
    username: str | None  # None when not logged in (accounts are optional)


class SaveParcel(BaseModel):
    parcel_id: str = Field(min_length=5, max_length=64)
    crop: str = Field(max_length=40)
    name: str | None = Field(default=None, max_length=60)


class UpdateParcel(BaseModel):
    crop: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=60)


class SavedParcel(BaseModel):
    id: int
    parcel_id: str
    crop: str
    name: str | None
    number: str
    region: str
    commune: str
    area_ha: float
    created_at: datetime
    last_analysed_at: datetime | None = None


class ReportSummary(BaseModel):
    """One archived analysis, enough to list and compare without loading the report."""

    id: int
    parcel_id: str
    crop: str
    analysis_date: date
    generated_at: datetime
    level: DroughtLevel
    water_pct: float | None
    top_recommendation: str | None


class ArchivedReport(BaseModel):
    summary: ReportSummary
    previous: ReportSummary | None  # the analysis of the same parcel before this one
    report: AnalysisReport


class BatchRow(BaseModel):
    """One saved parcel in the batch analysis; sent as soon as its report is ready."""

    saved_id: int
    parcel_id: str
    name: str | None
    number: str
    region: str
    crop: str
    status: Literal["ok", "error"]
    message: str | None = None
    level: DroughtLevel | None = None
    headline: str | None = None
    water_pct: float | None = None
    top_recommendation: str | None = None
    analysed_at: datetime | None = None
    report_id: int | None = None
