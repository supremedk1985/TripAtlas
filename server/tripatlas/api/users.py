"""User management (administrators only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.deps import require_admin
from ..auth.security import end_all_sessions, hash_password
from ..db.models import Role, Tracker, User
from ..db.session import get_db
from ..services.secrets import encrypt
from .auth import user_out
from .schemas import LOCALES, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


def _trackers(db: Session, ids: list[int]) -> list[Tracker]:
    found = list(db.scalars(select(Tracker).where(Tracker.id.in_(ids)))) if ids else []
    if len(found) != len(set(ids)):
        raise HTTPException(400, "Unknown tracker")
    return found


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.display_name))]


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.scalar(select(User).where(func.lower(User.username) == body.username.lower())):
        raise HTTPException(409, "Username is taken")
    u = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=body.role,
        locale=body.locale if body.locale in LOCALES else "en",
        # Children never see where someone is right now, unless an admin explicitly allows it.
        can_see_live=body.can_see_live if body.can_see_live is not None else body.role != Role.child,
    )
    u.trackers = _trackers(db, body.tracker_ids)
    db.add(u)
    db.commit()
    return user_out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    if body.role is not None and body.role != Role.admin and u.role == Role.admin and _admin_count(db) == 1:
        raise HTTPException(400, "The last administrator cannot be demoted")
    for f in ("display_name", "role", "can_see_live"):
        v = getattr(body, f)
        if v is not None:
            setattr(u, f, v)
    if body.locale is not None and body.locale in LOCALES:
        u.locale = body.locale
    if body.password is not None:
        u.password_hash = hash_password(body.password)
        if u.id != admin.id:
            end_all_sessions(db, u.id)
    if body.tracker_ids is not None:
        u.trackers = _trackers(db, body.tracker_ids)
    if body.immich_api_key is not None:
        u.immich_api_key = encrypt(body.immich_api_key) if body.immich_api_key else None
    db.commit()
    return user_out(u)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "You cannot delete yourself")
    db.delete(u)
    db.commit()


def _admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == Role.admin)) or 0
