"""Sign-in, sign-out, own profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.deps import COOKIE_NAME, current_user
from ..auth.security import (create_session, end_session, hash_password, login_throttle, verify_password)
from ..config import get_config
from ..db.models import Role, User
from ..db.session import get_db
from ..services.secrets import encrypt
from .schemas import LOCALES, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, username=u.username, display_name=u.display_name, role=u.role, locale=u.locale,
                   can_see_live=u.can_see_live, has_immich_key=bool(u.immich_api_key),
                   tracker_ids=[t.id for t in u.trackers])


def set_session_cookie(response: Response, token: str) -> None:
    cfg = get_config()
    response.set_cookie(COOKIE_NAME, token, max_age=cfg.session_days * 86400, httponly=True, samesite="lax",
                        secure=cfg.secure_cookies, path="/")


class LoginIn(BaseModel):
    username: str
    password: str
    # "app": return a long-lived bearer token instead of setting a cookie
    client: str = "web"
    device_name: str = ""


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    keys = (f"user:{body.username.lower()}", f"ip:{ip}")
    if login_throttle.blocked(*keys):
        raise HTTPException(429, "Too many failed attempts — try again in 15 minutes")
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.lower()))
    if user is None or not verify_password(user.password_hash, body.password):
        login_throttle.failed(*keys)
        raise HTTPException(401, "Wrong username or password")
    login_throttle.succeeded(*keys)
    if body.client == "app":
        token = create_session(db, user, kind="app", label=body.device_name or "App")
        return {"token": token, "user": user_out(user)}
    set_session_cookie(response, create_session(db, user, label=request.headers.get("user-agent", "")))
    return {"user": user_out(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE_NAME)
    if token:
        end_session(db, token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)


class ProfileIn(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=120)
    locale: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(None, min_length=8, max_length=200)
    immich_api_key: str | None = None


@router.put("/me", response_model=UserOut)
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.locale is not None:
        if body.locale not in LOCALES:
            raise HTTPException(400, "Unsupported language")
        user.locale = body.locale
    if body.new_password is not None:
        if user.role == Role.child:
            raise HTTPException(403, "Ask an administrator to change your password")
        if not body.current_password or not verify_password(user.password_hash, body.current_password):
            raise HTTPException(400, "Current password is wrong")
        user.password_hash = hash_password(body.new_password)
    if body.immich_api_key is not None:
        if user.role == Role.child:
            raise HTTPException(403, "Read-only account")
        user.immich_api_key = encrypt(body.immich_api_key) if body.immich_api_key else None
    db.commit()
    return user_out(user)
