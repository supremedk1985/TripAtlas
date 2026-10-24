"""First-run wizard and household settings.

Wizard flow (the web UI walks through it in this order):
  1. POST /api/setup/admin           create the first administrator — only possible while no user exists
  2. PUT  /api/settings/household    name, home location, time zone, language
  3. POST /api/settings/traccar/test + PUT /api/settings/traccar   (optional — imports work without Traccar)
  4. POST /api/settings/immich/test  + PUT /api/settings/immich    (optional — no photos without Immich)
  5. POST /api/trackers              one per vehicle/person (from a Traccar device or empty for imports)
  6. POST /api/setup/complete        starts the background sync
Every step after the first is also reachable later from the admin settings."""
from __future__ import annotations

from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.deps import require_admin
from ..auth.security import create_session, hash_password
from ..db.models import Role, Tracker, User
from ..db.session import get_db
from ..integrations.immich import ImmichClient, ImmichError
from ..integrations.traccar import TraccarClient, TraccarError
from ..services import settings
from ..services.jobs import jobs
from ..services.settings import HouseholdSettings, ImmichSettings, TraccarSettings
from .auth import set_session_cookie, user_out
from .schemas import LOCALES

router = APIRouter(tags=["setup"])


@router.get("/api/setup/status")
def status(db: Session = Depends(get_db)):
    hh = settings.household(db)
    return {"has_admin": db.scalar(select(func.count()).select_from(User)) > 0,
            "setup_complete": hh.setup_complete, "name": hh.name, "default_locale": hh.default_locale}


class AdminIn(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    locale: str = "en"


@router.post("/api/setup/admin")
def create_admin(body: AdminIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if db.scalar(select(func.count()).select_from(User)) > 0:
        raise HTTPException(409, "Setup has already been started — sign in instead")
    user = User(username=body.username, display_name=body.display_name, password_hash=hash_password(body.password),
                role=Role.admin, locale=body.locale if body.locale in LOCALES else "en", can_see_live=True)
    db.add(user)
    db.commit()
    hh = settings.household(db)
    hh.default_locale = user.locale
    settings.save(db, "household", hh)
    set_session_cookie(response, create_session(db, user, label=request.headers.get("user-agent", "")))
    return {"user": user_out(user)}


@router.post("/api/setup/complete")
def complete(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    hh = settings.household(db)
    if hh.home_lat is None:
        raise HTTPException(400, "Set the home location first")
    hh.setup_complete = True
    settings.save(db, "household", hh)
    jobs.trigger()
    return {"ok": True}


# --- household ----------------------------------------------------------------------------------------------------

@router.get("/api/settings/household", response_model=HouseholdSettings)
def get_household(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return settings.household(db)


class HouseholdIn(BaseModel):
    name: str = Field("TripAtlas", min_length=1, max_length=80)
    home_lat: float = Field(ge=-90, le=90)
    home_lon: float = Field(ge=-180, le=180)
    home_radius_km: float = Field(4.0, ge=0.5, le=50)
    timezone: str
    default_locale: str = "en"
    history_start: str | None = None
    min_trip_nights: int = Field(1, ge=1, le=30)
    min_trip_distance_km: float = Field(15, ge=1)
    place_info_enabled: bool = True


@router.put("/api/settings/household", response_model=HouseholdSettings)
def put_household(body: HouseholdIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if body.timezone not in available_timezones():
        raise HTTPException(400, "Unknown time zone")
    hh = settings.household(db)
    changed = (hh.home_lat, hh.home_lon, hh.home_radius_km, hh.timezone, hh.history_start, hh.min_trip_nights,
               hh.min_trip_distance_km) != (body.home_lat, body.home_lon, body.home_radius_km, body.timezone,
                                            body.history_start, body.min_trip_nights, body.min_trip_distance_km)
    new = hh.model_copy(update=body.model_dump())
    settings.save(db, "household", new)
    if changed:   # detection depends on these — recompute everything
        for t in db.scalars(select(Tracker)):
            t.dirty = True
        db.commit()
        jobs.trigger()
    return new


@router.get("/api/settings/timezones")
def timezones():
    return sorted(available_timezones())


# --- Traccar ------------------------------------------------------------------------------------------------------

class TraccarIn(BaseModel):
    url: str = Field(max_length=300)
    token: str = ""
    email: str = ""
    # Empty password/token in an update keeps the stored one.
    password: str = ""


def _merged_traccar(db: Session, body: TraccarIn) -> TraccarSettings:
    old = settings.traccar(db)
    return TraccarSettings(url=body.url.strip(), email=body.email.strip(),
                           token=body.token or (old.token if not body.email else ""),
                           password=body.password or (old.password if body.email == old.email else ""))


@router.get("/api/settings/traccar")
def get_traccar(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    c = settings.traccar(db)
    return {"url": c.url, "email": c.email, "has_token": bool(c.token), "has_password": bool(c.password)}


@router.post("/api/settings/traccar/test")
def test_traccar(body: TraccarIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    c = _merged_traccar(db, body)
    try:
        with TraccarClient(c.url, c.token, c.email, c.password, timeout=15) as client:
            info = client.server_info()
            devices = client.devices()
    except TraccarError as e:
        raise HTTPException(400, str(e))
    return {"version": info.get("version"), "devices": [{"id": d["id"], "name": d.get("name"), "status": d.get("status")}
                                                         for d in devices]}


@router.put("/api/settings/traccar")
def put_traccar(body: TraccarIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    settings.save(db, "traccar", _merged_traccar(db, body))
    jobs.trigger()
    return {"ok": True}


@router.get("/api/settings/traccar/devices")
def traccar_devices(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    c = settings.traccar(db)
    try:
        with TraccarClient(c.url, c.token, c.email, c.password, timeout=15) as client:
            devices = client.devices()
    except TraccarError as e:
        raise HTTPException(502, str(e))
    linked = {t.traccar_device_id: t.id for t in db.scalars(select(Tracker))}
    return [{"id": d["id"], "name": d.get("name"), "status": d.get("status"), "tracker_id": linked.get(d["id"])}
            for d in devices]


# --- Immich -------------------------------------------------------------------------------------------------------

class ImmichIn(BaseModel):
    url: str = Field(max_length=300)
    api_key: str = ""   # empty in an update keeps the stored key


@router.get("/api/settings/immich")
def get_immich(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    c = settings.immich(db)
    return {"url": c.url, "has_api_key": bool(c.api_key)}


@router.post("/api/settings/immich/test")
def test_immich(body: ImmichIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    key = body.api_key or settings.immich(db).api_key
    try:
        with ImmichClient(body.url.strip(), key, timeout=15) as client:
            version = client.version()
            me = client.me()
    except ImmichError as e:
        raise HTTPException(400, str(e))
    return {"version": version, "user": me.get("name") or me.get("email")}


@router.put("/api/settings/immich")
def put_immich(body: ImmichIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    settings.save(db, "immich", ImmichSettings(url=body.url.strip(), api_key=body.api_key or settings.immich(db).api_key))
    for t in db.scalars(select(Tracker)):
        t.dirty = True   # photo counts and covers change
    db.commit()
    jobs.trigger()
    return {"ok": True}


# --- background jobs ----------------------------------------------------------------------------------------------

@router.get("/api/admin/jobs")
def job_status(_: User = Depends(require_admin)):
    return {"running": jobs.running, "last_result": jobs.last_result}


@router.post("/api/admin/jobs/run")
def job_run(_: User = Depends(require_admin)):
    jobs.trigger()
    return {"ok": True}
