"""Profile pictures. The browser crops and scales the picture to a small square JPEG before uploading, so the server
only checks what arrives and stores it with the user."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..auth.deps import current_user, require_admin, require_editor
from ..db.models import User
from ..db.session import get_db
from .auth import user_out
from .schemas import UserOut

router = APIRouter(tags=["users"])

MAX_BYTES = 300_000


@router.get("/api/users/{user_id}/avatar")
def get_avatar(user_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    u = db.get(User, user_id)
    if u is None or not u.avatar:
        raise HTTPException(404, "No picture")
    # the URL carries ?v=<avatar_version>, so a new picture is a new URL
    cache = {"Cache-Control": "private, max-age=31536000, immutable"}
    return Response(u.avatar, media_type="image/jpeg", headers=cache)


async def _store(u: User, request: Request, db: Session) -> UserOut:
    data = await request.body()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Picture too large")
    if not data.startswith(b"\xff\xd8\xff"):
        raise HTTPException(400, "Expected a JPEG picture")
    u.avatar = data
    u.avatar_updated = datetime.now(UTC)
    db.commit()
    return user_out(u)


def _clear(u: User, db: Session) -> UserOut:
    u.avatar = None
    u.avatar_updated = None
    db.commit()
    return user_out(u)


@router.put("/api/auth/me/avatar", response_model=UserOut)
async def set_my_avatar(request: Request, user: User = Depends(require_editor), db: Session = Depends(get_db)):
    """Children cannot change anything themselves; an administrator sets their picture."""
    return await _store(user, request, db)


@router.delete("/api/auth/me/avatar", response_model=UserOut)
def delete_my_avatar(user: User = Depends(require_editor), db: Session = Depends(get_db)):
    return _clear(user, db)


def _user(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    return u


@router.put("/api/users/{user_id}/avatar", response_model=UserOut)
async def set_avatar(user_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return await _store(_user(db, user_id), request, db)


@router.delete("/api/users/{user_id}/avatar", response_model=UserOut)
def delete_avatar(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return _clear(_user(db, user_id), db)
