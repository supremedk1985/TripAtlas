"""Passwords, session tokens and login throttling."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from ..config import get_config
from ..db.models import Session, User, utcnow

_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _session_days(kind: str) -> int:
    return get_config().session_days if kind == "web" else 365


def create_session(db: DbSession, user: User, kind: str = "web", label: str = "") -> str:
    """Create a session and return the token. Only its hash is stored."""
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=_token_hash(token),
            user_id=user.id,
            kind=kind,
            label=label[:200],
            expires_at=utcnow() + timedelta(days=_session_days(kind)),
        )
    )
    db.commit()
    return token


def user_for_token(db: DbSession, token: str) -> User | None:
    s = db.scalar(select(Session).where(Session.token_hash == _token_hash(token)))
    if s is None:
        return None
    expires = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        db.delete(s)
        db.commit()
        return None
    now = utcnow()
    last = s.last_seen_at if s.last_seen_at.tzinfo else s.last_seen_at.replace(tzinfo=now.tzinfo)
    if (now - last).total_seconds() > 300:  # do not write on every request
        s.last_seen_at = now
        # Sliding expiry: whoever uses TripAtlas regularly is never signed out; only unused sessions expire.
        s.expires_at = now + timedelta(days=_session_days(s.kind))
        db.commit()
    return s.user


def end_session(db: DbSession, token: str) -> None:
    db.execute(delete(Session).where(Session.token_hash == _token_hash(token)))
    db.commit()


def end_other_sessions(db: DbSession, user_id: int, keep_token: str | None) -> None:
    q = delete(Session).where(Session.user_id == user_id)
    if keep_token:
        q = q.where(Session.token_hash != _token_hash(keep_token))
    db.execute(q)
    db.commit()


def end_all_sessions(db: DbSession, user_id: int) -> None:
    db.execute(delete(Session).where(Session.user_id == user_id))
    db.commit()


class LoginThrottle:
    """Slows down password guessing: after `limit` failures for the same key (username or client address) within
    `window` seconds, further attempts are refused until the window has passed. In-memory — resets on restart, which
    is acceptable for a family server."""

    def __init__(self, limit: int = 5, window: float = 900):
        self.limit, self.window = limit, window
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        now = time.monotonic()
        return [t for t in self._fails.get(key, []) if now - t < self.window]

    def blocked(self, *keys: str) -> bool:
        with self._lock:
            return any(len(self._recent(k)) >= self.limit for k in keys)

    def failed(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._fails[k] = [*self._recent(k), time.monotonic()]

    def succeeded(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)


login_throttle = LoginThrottle()                     # per account and address
address_throttle = LoginThrottle(limit=30)           # per address, across all names
# verified against when the name does not exist, so that takes as long as a wrong password
DUMMY_HASH = hash_password("no such user — timing equaliser")
