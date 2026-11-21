"""Account endpoints: register, log in, log out, who am I.

Handlers are plain functions: FastAPI runs them in its thread pool, so Argon2 hashing
and SQLite calls do not block the event loop serving analyses."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from retencja_api.accounts import auth, ratelimit
from retencja_api.accounts.deps import (
    SESSION_COOKIE,
    clear_session_cookie,
    optional_user,
    same_origin,
    set_session_cookie,
)
from retencja_api.accounts.schemas import Credentials, Me, User

router = APIRouter(prefix="/api/account", tags=["account"])

TOO_MANY = "Zbyt wiele prób logowania. Spróbuj ponownie za kilkanaście minut."


@router.get("/me")
def me(user: Annotated[User | None, Depends(optional_user)]) -> Me:
    return Me(username=user.username if user else None)


@router.post("/register", dependencies=[Depends(same_origin)])
def register(credentials: Credentials, response: Response) -> Me:
    if ratelimit.registrations.blocked(ratelimit.GLOBAL):
        raise HTTPException(429, "Zbyt wiele nowych kont w krótkim czasie. Spróbuj później.")
    try:
        user = auth.create_user(credentials.username, credentials.password)
    except auth.UsernameTaken:
        raise HTTPException(409, "Ta nazwa użytkownika jest już zajęta") from None
    ratelimit.registrations.hit(ratelimit.GLOBAL)
    set_session_cookie(response, auth.create_session(user))
    return Me(username=user.username)


@router.post("/login", dependencies=[Depends(same_origin)])
def login(credentials: Credentials, response: Response) -> Me:
    key = credentials.username.lower()
    if ratelimit.login_per_user.blocked(key) or ratelimit.login_global.blocked(ratelimit.GLOBAL):
        raise HTTPException(429, TOO_MANY)
    user = auth.authenticate(credentials.username, credentials.password)
    if user is None:
        ratelimit.login_per_user.hit(key)
        ratelimit.login_global.hit(ratelimit.GLOBAL)
        raise HTTPException(401, "Nieprawidłowa nazwa użytkownika lub hasło")
    ratelimit.login_per_user.reset(key)
    set_session_cookie(response, auth.create_session(user))
    return Me(username=user.username)


@router.post("/logout", dependencies=[Depends(same_origin)])
def logout(request: Request, response: Response) -> Me:
    if token := request.cookies.get(SESSION_COOKIE):
        auth.delete_session(token)
    clear_session_cookie(response)
    return Me(username=None)
