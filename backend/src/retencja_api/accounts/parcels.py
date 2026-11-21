"""Saved parcels ("Moje działki"): every query is scoped to the owning user."""

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime

from retencja_api.accounts import archive, db
from retencja_api.accounts.schemas import SavedParcel
from retencja_api.models import GeoJSON, Parcel

MAX_SAVED_PARCELS = 100

COLUMNS = "id, parcel_id, crop, name, number, region, commune, area_ha, created_at, geometry"


class AlreadySaved(Exception):
    pass


class TooManyParcels(Exception):
    pass


def _model(row: sqlite3.Row, last_analysed_at: datetime | None = None) -> SavedParcel:
    geometry = row["geometry"]
    return SavedParcel.model_validate({
        **dict(row),
        "geometry": json.loads(geometry) if geometry else None,
        "last_analysed_at": last_analysed_at,
    })


def list_parcels(user_id: int) -> list[SavedParcel]:
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM saved_parcels WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
    latest = archive.last_analysed(user_id)
    return [_model(r, latest.get(r["parcel_id"])) for r in rows]


def get_parcel(user_id: int, saved_id: int) -> SavedParcel | None:
    with db.connect() as conn:
        row = conn.execute(
            f"SELECT {COLUMNS} FROM saved_parcels WHERE id = ? AND user_id = ?",
            (saved_id, user_id),
        ).fetchone()
    return _model(row) if row else None


def save_parcel(user_id: int, parcel: Parcel, crop: str, name: str | None) -> SavedParcel:
    with db.connect() as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM saved_parcels WHERE user_id = ?", (user_id,)
        ).fetchone()
        if count >= MAX_SAVED_PARCELS:
            raise TooManyParcels
        try:
            cursor = conn.execute(
                "INSERT INTO saved_parcels (user_id, parcel_id, crop, name, number, region, "
                "commune, area_ha, created_at, geometry) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, parcel.id, crop, name, parcel.number, parcel.region, parcel.commune,
                 parcel.area_ha, db.stamp(db.now()), json.dumps(parcel.geometry)),
            )
        except sqlite3.IntegrityError:
            raise AlreadySaved(parcel.id) from None
    saved = get_parcel(user_id, cursor.lastrowid)
    assert saved is not None
    return saved


def update_parcel(
    user_id: int, saved_id: int, crop: str | None, name: str | None, set_name: bool
) -> SavedParcel | None:
    """Changes the crop and, when `set_name`, the name (None removes it).
    None if the parcel is not the user's."""
    with db.connect() as conn:
        if crop is not None:
            conn.execute(
                "UPDATE saved_parcels SET crop = ? WHERE id = ? AND user_id = ?",
                (crop, saved_id, user_id),
            )
        if set_name:
            conn.execute(
                "UPDATE saved_parcels SET name = ? WHERE id = ? AND user_id = ?",
                (name, saved_id, user_id),
            )
    return get_parcel(user_id, saved_id)


def set_geometries(user_id: int, geometries: Mapping[int, GeoJSON]) -> None:
    """Stores outlines of parcels saved before the list kept them (saved id → GeoJSON)."""
    with db.connect() as conn:
        conn.executemany(
            "UPDATE saved_parcels SET geometry = ? WHERE id = ? AND user_id = ?",
            [(json.dumps(g), saved_id, user_id) for saved_id, g in geometries.items()],
        )


def delete_parcel(user_id: int, saved_id: int) -> bool:
    """Removes the parcel from the list; its archived reports are kept."""
    with db.connect() as conn:
        cursor = conn.execute(
            "DELETE FROM saved_parcels WHERE id = ? AND user_id = ?", (saved_id, user_id)
        )
    return cursor.rowcount > 0
