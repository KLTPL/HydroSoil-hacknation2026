"""Archive of analyses run by logged-in users: full AnalysisReport snapshots (zlib JSON)
plus the few fields needed to list and compare them."""

import zlib
from datetime import timedelta
from sqlite3 import Row

from retencja_api.accounts import db
from retencja_api.accounts.schemas import ArchivedReport, ReportSummary
from retencja_api.models import AnalysisReport

# Oldest snapshots beyond this are dropped, per user and parcel.
MAX_REPORTS_PER_PARCEL = 50
# A polling refresh (terrain arrived later) replaces a snapshot at most this old.
REFRESH_WINDOW = timedelta(minutes=30)

SUMMARY_COLUMNS = (
    "id, parcel_id, crop, analysis_date, generated_at, level, water_pct, top_recommendation"
)


def water_pct(report: AnalysisReport) -> float | None:
    water = report.water.data
    return round(water.available_pct.value, 1) if water else None


def top_recommendation(report: AnalysisReport) -> str | None:
    return report.recommendations[0].title if report.recommendations else None


def _summary(row: Row | dict[str, object]) -> ReportSummary:
    return ReportSummary.model_validate(dict(row))


def record(user_id: int, report: AnalysisReport, *, refresh: bool = False) -> int:
    """Stores the report; returns its archive id."""
    body = zlib.compress(report.model_dump_json().encode())
    fields = (
        report.diagnosis.level,
        water_pct(report),
        top_recommendation(report),
        db.stamp(report.generated_at),
        body,
    )
    key = (user_id, report.parcel.id, report.crop.id, report.analysis_date.isoformat())
    with db.connect() as conn:
        if refresh:
            row = conn.execute(
                "SELECT id FROM reports WHERE user_id = ? AND parcel_id = ? AND crop = ? "
                "AND analysis_date = ? AND generated_at >= ? ORDER BY generated_at DESC LIMIT 1",
                (*key, db.stamp(db.now() - REFRESH_WINDOW)),
            ).fetchone()
            if row is not None:
                conn.execute(
                    "UPDATE reports SET level = ?, water_pct = ?, top_recommendation = ?, "
                    "generated_at = ?, body = ? WHERE id = ?",
                    (*fields, row["id"]),
                )
                return row["id"]
        cursor = conn.execute(
            "INSERT INTO reports (user_id, parcel_id, crop, analysis_date, level, water_pct, "
            "top_recommendation, generated_at, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*key, *fields),
        )
        conn.execute(
            "DELETE FROM reports WHERE user_id = ? AND parcel_id = ? AND id NOT IN ("
            "SELECT id FROM reports WHERE user_id = ? AND parcel_id = ? "
            "ORDER BY generated_at DESC LIMIT ?)",
            (user_id, key[1], user_id, key[1], MAX_REPORTS_PER_PARCEL),
        )
        return cursor.lastrowid


def list_reports(user_id: int, parcel_id: str | None = None) -> list[ReportSummary]:
    """Newest first; all of the user's parcels unless one is given."""
    with db.connect() as conn:
        if parcel_id is None:
            rows = conn.execute(
                f"SELECT {SUMMARY_COLUMNS} FROM reports WHERE user_id = ? "
                "ORDER BY generated_at DESC LIMIT 500",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {SUMMARY_COLUMNS} FROM reports WHERE user_id = ? AND parcel_id = ? "
                "ORDER BY generated_at DESC",
                (user_id, parcel_id),
            ).fetchall()
    return [_summary(r) for r in rows]


def get_report(user_id: int, report_id: int) -> ArchivedReport | None:
    """The snapshot and the analysis of the same parcel before it; None if not the user's."""
    with db.connect() as conn:
        row = conn.execute(
            f"SELECT {SUMMARY_COLUMNS}, body FROM reports WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        ).fetchone()
        if row is None:
            return None
        previous = conn.execute(
            f"SELECT {SUMMARY_COLUMNS} FROM reports WHERE user_id = ? AND parcel_id = ? "
            "AND generated_at < ? ORDER BY generated_at DESC LIMIT 1",
            (user_id, row["parcel_id"], row["generated_at"]),
        ).fetchone()
    report = AnalysisReport.model_validate_json(zlib.decompress(row["body"]))
    summary = _summary({k: row[k] for k in row.keys() if k != "body"})
    return ArchivedReport(
        summary=summary,
        previous=_summary(previous) if previous else None,
        report=report,
    )


def last_analysed(user_id: int) -> dict[str, str]:
    """parcel_id → timestamp of its newest archived analysis."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT parcel_id, MAX(generated_at) AS latest FROM reports WHERE user_id = ? "
            "GROUP BY parcel_id",
            (user_id,),
        ).fetchall()
    return {r["parcel_id"]: r["latest"] for r in rows}
