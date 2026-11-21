import sqlite3
from datetime import timedelta

from conftest import PASSWORD, WRITE, register
from fastapi.testclient import TestClient

from retencja_api import api
from retencja_api.accounts import auth, db, ratelimit
from retencja_api.accounts.deps import SESSION_COOKIE


def test_register_logs_in_with_an_httponly_session_cookie(client):
    response = register(client)

    assert response.status_code == 200, response.text
    assert response.json() == {"username": "rolnik"}
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api" in cookie
    assert client.get("/api/account/me").json() == {"username": "rolnik"}


def test_anonymous_visitor_is_simply_not_logged_in(client):
    assert client.get("/api/account/me").json() == {"username": None}
    assert client.get("/api/account/parcels").status_code == 401


def test_password_is_stored_as_argon2_hash(client, accounts_db):
    register(client)

    (stored,) = sqlite3.connect(accounts_db).execute("SELECT password_hash FROM users").fetchone()
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


def test_session_token_is_stored_hashed(client, accounts_db):
    register(client)

    (token_hash,) = sqlite3.connect(accounts_db).execute(
        "SELECT token_hash FROM sessions"
    ).fetchone()
    assert client.cookies[SESSION_COOKIE] != token_hash


def test_duplicate_username_is_rejected_case_insensitively(client):
    register(client, "Rolnik")
    response = register(TestClient(api.app), "rolnik")
    assert response.status_code == 409


def test_username_and_password_limits(client):
    assert register(client, "ab").status_code == 422
    assert register(client, "x" * 33).status_code == 422
    assert register(client, "zła nazwa").status_code == 422
    assert register(client, "rolnik", "krotkie").status_code == 422
    assert register(client, "rolnik", "x" * 129).status_code == 422


def test_writes_without_the_csrf_header_are_refused(client):
    response = client.post("/api/account/register",
                           json={"username": "rolnik", "password": PASSWORD})
    assert response.status_code == 403


def test_writes_from_another_origin_are_refused(client):
    response = client.post(
        "/api/account/register",
        json={"username": "rolnik", "password": PASSWORD},
        headers={**WRITE, "Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_login_and_logout(client):
    register(client)
    other = TestClient(api.app)

    wrong = other.post("/api/account/login", json={"username": "rolnik", "password": "zle-haslo-1"},
                       headers=WRITE)
    assert wrong.status_code == 401
    ok = other.post("/api/account/login", json={"username": "ROLNIK", "password": PASSWORD},
                    headers=WRITE)
    assert ok.status_code == 200
    assert other.get("/api/account/me").json() == {"username": "rolnik"}

    token = other.cookies[SESSION_COOKIE]
    assert other.post("/api/account/logout", headers=WRITE).status_code == 200
    assert auth.session_user(token) is None  # deleted on the server, not only in the browser
    assert other.get("/api/account/me").json() == {"username": None}


def test_unknown_user_cannot_log_in(client):
    response = client.post("/api/account/login",
                           json={"username": "nikt", "password": PASSWORD}, headers=WRITE)
    assert response.status_code == 401


def test_session_expires(client, monkeypatch):
    register(client)
    later = db.now() + auth.SESSION_TTL + timedelta(minutes=1)
    monkeypatch.setattr(db, "now", lambda: later)

    assert client.get("/api/account/me").json() == {"username": None}
    assert client.get("/api/account/parcels").status_code == 401


def test_forged_cookie_is_ignored(client):
    client.cookies.set(SESSION_COOKIE, "forged")
    assert client.get("/api/account/me").json() == {"username": None}


def test_repeated_wrong_passwords_are_rate_limited(client, monkeypatch):
    register(client)
    attempt = {"username": "rolnik", "password": "zle-haslo-1"}
    for _ in range(ratelimit.login_per_user.limit):
        assert client.post("/api/account/login", json=attempt, headers=WRITE).status_code == 401

    # Even the right password is refused while the account is locked.
    right = {"username": "rolnik", "password": PASSWORD}
    assert client.post("/api/account/login", json=right, headers=WRITE).status_code == 429

    start = ratelimit.clock()
    monkeypatch.setattr(ratelimit, "clock", lambda: start + ratelimit.login_per_user.window_s + 1)
    assert client.post("/api/account/login", json=right, headers=WRITE).status_code == 200


def test_registrations_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(ratelimit.registrations, "limit", 2)
    assert register(TestClient(api.app), "rolnik1").status_code == 200
    assert register(TestClient(api.app), "rolnik2").status_code == 200
    assert register(TestClient(api.app), "rolnik3").status_code == 429
