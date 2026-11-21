"""Users, password hashing (Argon2id) and server-side sessions."""

import hashlib
import secrets
import sqlite3
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from retencja_api.accounts import db
from retencja_api.accounts.schemas import User

SESSION_TTL = timedelta(days=30)

_hasher = PasswordHasher()
# Verified when the username does not exist, so a login takes as long either way
# and response time does not reveal which usernames are registered.
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


class UsernameTaken(Exception):
    pass


def create_user(username: str, password: str) -> User:
    password_hash = _hasher.hash(password)
    try:
        with db.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, db.stamp(db.now())),
            )
    except sqlite3.IntegrityError:
        raise UsernameTaken(username) from None
    return User(id=cursor.lastrowid, username=username)


def authenticate(username: str, password: str) -> User | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    stored = row["password_hash"] if row else _DUMMY_HASH
    try:
        _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return None
    if row is None:
        return None
    if _hasher.check_needs_rehash(stored):
        with db.connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_hasher.hash(password), row["id"]),
            )
    return User(id=row["id"], username=row["username"])


def _token_hash(token: str) -> str:
    # Only a hash is stored: a leaked database file does not leak usable sessions.
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = db.now()
    with db.connect() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (db.stamp(now),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_token_hash(token), user.id, db.stamp(now + SESSION_TTL)),
        )
    return token


def session_user(token: str) -> User | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT users.id, users.username, sessions.expires_at FROM sessions "
            "JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ?",
            (_token_hash(token),),
        ).fetchone()
    if row is None or row["expires_at"] < db.stamp(db.now()):
        return None
    return User(id=row["id"], username=row["username"])


def delete_session(token: str) -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
