"""FastAPI dependencies for authentication and authorisation.

Clients authenticate with either
- the session cookie (web UI), or
- `Authorization: Bearer <token>` (mobile app; tokens come from POST /api/auth/login with `"client": "app"`).

Cookie-authenticated requests that change something must come from our own origin (CSRF protection on top of
SameSite=Lax). Bearer requests are not affected — browsers never attach that header on their own."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Role, Tracker, User
from ..db.session import get_db
from .security import user_for_token

COOKIE_NAME = "tripatlas_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _token(request: Request) -> tuple[str | None, bool]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    return request.cookies.get(COOKIE_NAME), True


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return  # non-browser client with a cookie (rare); SameSite already blocks cross-site form posts
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    if urlparse(origin).netloc != host:
        raise HTTPException(403, "Cross-site request refused")


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token, from_cookie = _token(request)
    if not token:
        return None
    user = user_for_token(db, token)
    if user is not None:
        user.role  # noqa: B018 - loaded now, so the next line can hand back the connection
    # End the read: the connection goes back to the pool until the endpoint itself needs one. Otherwise every request
    # kept it while waiting for a worker thread — dozens of photo requests at once emptied the pool (25.10.2026).
    db.commit()
    if user and from_cookie and request.method not in SAFE_METHODS:
        _check_origin(request)
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "Not signed in")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(403, "Administrators only")
    return user


def require_editor(user: User = Depends(current_user)) -> User:
    """Anyone who may change content (titles, notes, imports). Children may not."""
    if user.role == Role.child:
        raise HTTPException(403, "Read-only account")
    return user


def visible_trackers(db: Session, user: User) -> list[Tracker]:
    if user.role == Role.admin:
        return list(db.scalars(select(Tracker).order_by(Tracker.name)))
    return sorted(user.trackers, key=lambda t: t.name)


def tracker_for(db: Session, user: User, tracker_id: int) -> Tracker:
    """The tracker if the user may see it, else 404 (not 403: do not reveal that it exists)."""
    t = db.get(Tracker, tracker_id)
    if t is None or (user.role != Role.admin and t not in user.trackers):
        raise HTTPException(404, "Tracker not found")
    return t
