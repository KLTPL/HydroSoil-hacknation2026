"""Request dependencies: who is logged in, CSRF guard, session cookie handling."""

from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response

from retencja_api import config
from retencja_api.accounts import archive, auth
from retencja_api.accounts.auth import SESSION_TTL
from retencja_api.accounts.schemas import User
from retencja_api.models import AnalysisReport

SESSION_COOKIE = "splyw_session"
# Browsers only send custom headers from this site's own scripts (other origins would
# need a CORS preflight, which the API never grants), so requiring it on every write
# blocks cross-site request forgery on top of the SameSite=Lax cookie.
CSRF_HEADER = "X-Splyw"


def optional_user(request: Request) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return auth.session_user(token)


def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "Zaloguj się, aby korzystać z tej funkcji")
    return user


def same_origin(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(403, "Brak nagłówka zabezpieczającego żądanie")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "Żądanie z innej strony zostało odrzucone")


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/api",
        httponly=True,
        secure=config.SECURE_COOKIES,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/api", httponly=True, secure=config.SECURE_COOKIES, samesite="lax"
    )


type Archiver = Callable[[AnalysisReport, bool], None]


def report_archiver(user: Annotated[User | None, Depends(optional_user)]) -> Archiver:
    """Stores analyses of logged-in users; anonymous analyses are not stored at all.
    The flag marks a polling refresh, which updates the latest snapshot instead of
    adding one."""

    def record(report: AnalysisReport, refresh: bool) -> None:
        if user is not None:
            archive.record(user.id, report, refresh=refresh)

    return record
