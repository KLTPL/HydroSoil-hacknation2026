"""Saved parcels ("Moje działki"): every query is scoped to the owning user."""

import sqlite3

from retencja_api.accounts import archive, db
from retencja_api.accounts.schemas import SavedParcel
from retencja_api.models import Parcel

MAX_SAVED_PARCELS = 100

COLUMNS = "id, parcel_id, crop, name, number, region, commune, area_ha, created_at"


class AlreadySaved(Exception):
    pass


class TooManyParcels(Exception):
    pass


def list_parcels(user_id: int) -> list[SavedParcel]:
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM saved_parcels WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
    latest = archive.last_analysed(user_id)
    return [
        SavedParcel.model_validate({**dict(r), "last_analysed_at": latest.get(r["parcel_id"])})
        for r in rows
    ]


def get_parcel(user_id: int, saved_id: int) -> SavedParcel | None:
    with db.connect() as conn:
        row = conn.execute(
            f"SELECT {COLUMNS} FROM saved_parcels WHERE id = ? AND user_id = ?",
            (saved_id, user_id),
        ).fetchone()
    return SavedParcel.model_validate(dict(row)) if row else None


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
                "commune, area_ha, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, parcel.id, crop, name, parcel.number, parcel.region, parcel.commune,
                 parcel.area_ha, db.stamp(db.now())),
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


def delete_parcel(user_id: int, saved_id: int) -> bool:
    """Removes the parcel from the list; its archived reports are kept."""
    with db.connect() as conn:
        cursor = conn.execute(
            "DELETE FROM saved_parcels WHERE id = ? AND user_id = ?", (saved_id, user_id)
        )
    return cursor.rowcount > 0
