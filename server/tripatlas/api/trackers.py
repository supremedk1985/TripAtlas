"""Trackers: list, manage, raw tracks and drives."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth.deps import current_user, require_admin, tracker_for, visible_trackers
from ..core.detection import detect_drives
from ..core.geo import thin_out
from ..db.models import Position, Tracker, User
from ..db.session import get_db
from ..services import settings
from ..services.jobs import jobs
from ..services.positions import bounds, latest, load_points
from ..services.trips import tracker_settings
from .schemas import TrackerCreate, TrackerOut, TrackerUpdate

router = APIRouter(prefix="/api/trackers", tags=["trackers"])

AVATAR_MAX_BYTES = 2 * 1024 * 1024
# Users without live access see positions only after this delay, so a track never reveals where someone is now.
from ..services.photos import LIVE_DELAY_S  # noqa: E402  (one value for positions and photos)

IMAGE_MAGIC = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"RIFF": "image/webp"}


def tracker_out(db: Session, t: Tracker, user: User, with_stats: bool = True) -> TrackerOut:
    out = TrackerOut(
        id=t.id,
        name=t.name,
        kind=t.kind,
        color=t.color,
        traccar_device_id=t.traccar_device_id,
        photo_priority=t.photo_priority,
        has_avatar=t.avatar is not None,
    )
    if with_stats:
        out.first, out.last, out.position_count = bounds(db, t.id)
        if user.can_see_live:
            p = latest(db, t.id)
            if p:
                out.latest = {"t": p.t, "lat": p.lat, "lon": p.lon, "speed_kmh": p.speed_kmh}
    return out


@router.get("", response_model=list[TrackerOut])
def list_trackers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [tracker_out(db, t, user) for t in visible_trackers(db, user)]


@router.post("", response_model=TrackerOut, status_code=201)
def create_tracker(body: TrackerCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.traccar_device_id is not None and db.scalar(
        select(Tracker).where(Tracker.traccar_device_id == body.traccar_device_id)
    ):
        raise HTTPException(409, "This Traccar device is already linked")
    t = Tracker(**body.model_dump())
    db.add(t)
    db.commit()
    jobs.trigger()
    return tracker_out(db, t, admin)


@router.patch("/{tracker_id}", response_model=TrackerOut)
def update_tracker(
    tracker_id: int, body: TrackerUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    t = tracker_for(db, admin, tracker_id)
    data = body.model_dump(exclude_unset=True)
    if "traccar_device_id" in data and data["traccar_device_id"] != t.traccar_device_id:
        t.synced_until = None  # a different device: fetch its whole history
    if "kind" in data and data["kind"] != t.kind:
        t.dirty = True  # a bike counts every ride: its trips have to be recognised again
    if "photo_priority" in data:
        for other in db.scalars(select(Tracker)):
            other.dirty = True  # priorities decide which tracker gets a photo
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    jobs.trigger()
    return tracker_out(db, t, admin)


@router.delete("/{tracker_id}", status_code=204)
def delete_tracker(tracker_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    t = tracker_for(db, admin, tracker_id)
    db.execute(delete(Position).where(Position.tracker_id == t.id))
    db.delete(t)
    db.commit()


@router.put("/{tracker_id}/avatar", status_code=204)
async def put_avatar(
    tracker_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    data = await file.read(AVATAR_MAX_BYTES + 1)
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(413, "Image too large (max. 2 MB)")
    if not any(data.startswith(m) for m in IMAGE_MAGIC):
        raise HTTPException(400, "PNG, JPEG or WebP only")
    t = tracker_for(db, admin, tracker_id)
    t.avatar = data
    db.commit()


@router.get("/{tracker_id}/avatar")
def get_avatar(tracker_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = tracker_for(db, user, tracker_id)
    if t.avatar is None:
        raise HTTPException(404, "No avatar")
    kind = next((v for m, v in IMAGE_MAGIC.items() if t.avatar.startswith(m)), "application/octet-stream")
    return Response(t.avatar, media_type=kind, headers={"Cache-Control": "private, max-age=3600"})


def _range(user: User, start: float, end: float) -> tuple[float, float]:
    if end <= start:
        raise HTTPException(400, "end must be after start")
    if not user.can_see_live:
        end = min(end, time.time() - LIVE_DELAY_S)
    return start, end


@router.get("/{tracker_id}/track")
def track(tracker_id: int, start: float, end: float, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Positions in [start, end] (Unix seconds), thinned out: [[t, lat, lon, speed_kmh, altitude_m], …]."""
    t = tracker_for(db, user, tracker_id)
    start, end = _range(user, start, end)
    pts = load_points(db, t.id, start, end)
    return {"points": [list(p) for p in thin_out(pts)], "raw_count": len(pts)}


@router.get("/{tracker_id}/drives")
def drives(
    tracker_id: int, start: float, end: float, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    t = tracker_for(db, user, tracker_id)
    s = settings.household(db).detection()
    if s is None:
        raise HTTPException(409, "Home location not set")
    s = tracker_settings(t, s)
    start, end = _range(user, start, end)
    return [d.__dict__ for d in detect_drives(load_points(db, t.id, start, end), s)]
