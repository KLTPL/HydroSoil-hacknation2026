"""SQLite storage for optional user accounts: users, sessions, saved parcels, report archive.

One short-lived connection per operation (requests run in FastAPI's thread pool);
all SQL is parameterized."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from retencja_api import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS saved_parcels (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parcel_id TEXT NOT NULL,
    crop TEXT NOT NULL,
    name TEXT,
    number TEXT NOT NULL,
    region TEXT NOT NULL,
    commune TEXT NOT NULL,
    area_ha REAL NOT NULL,
    created_at TEXT NOT NULL,
    geometry TEXT,
    UNIQUE (user_id, parcel_id)
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parcel_id TEXT NOT NULL,
    crop TEXT NOT NULL,
    analysis_date TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    level TEXT NOT NULL,
    water_pct REAL,
    top_recommendation TEXT,
    body BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS reports_user_parcel ON reports(user_id, parcel_id, generated_at);
"""

_initialised: set[Path] = set()


def _migrate(conn: sqlite3.Connection) -> None:
    """Adds columns introduced after a database was created."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(saved_parcels)")}
    if "geometry" not in columns:  # outline for the "Moje działki" thumbnail (GeoJSON, WGS84)
        conn.execute("ALTER TABLE saved_parcels ADD COLUMN geometry TEXT")


def now() -> datetime:
    """Current time; a function so tests can move the clock (session expiry)."""
    return datetime.now(UTC)


def stamp(moment: datetime) -> str:
    """Fixed-width UTC timestamp, so stored values compare correctly as text."""
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Connection to the accounts database, committed on success, rolled back on error."""
    path = config.ACCOUNTS_DB_PATH
    if path not in _initialised:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if path not in _initialised:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            _migrate(conn)
            _initialised.add(path)
        with conn:
            yield conn
    finally:
        conn.close()
