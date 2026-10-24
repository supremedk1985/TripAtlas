"""Trips, their timeline, photos and user annotations."""
from __future__ import annotations

import re
import time

import nh3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.deps import current_user, require_editor, tracker_for, visible_trackers
from ..core.detection import detect_stays
from ..core.geo import thin_out
from ..core.timeline import build_timeline
from ..db.models import Annotation, Trip, User
from ..db.session import get_db
from ..integrations.immich import ImmichError
from ..services import photos as photo_service
from ..services import settings
from ..services.positions import load_points
from ..services.trips import day_key
from .schemas import AnnotationIn

router = APIRouter(tags=["trips"])


def _annotations(db: Session, tracker_ids: list[int], kind: str) -> dict[tuple[int, str], Annotation]:
    rows = db.scalars(select(Annotation).where(Annotation.tracker_id.in_(tracker_ids), Annotation.kind == kind))
    return {(a.tracker_id, a.day_key): a for a in rows}


def trip_summary(t: Trip, ann: Annotation | None) -> dict:
    return {"id": t.id, "tracker_id": t.tracker_id, "day_key": t.day_key, "start": t.start, "end": t.end,
            "ongoing": t.ongoing, "distance_km": t.distance_km, "farthest_km": t.farthest_km, "nights": t.nights,
            "destination": [t.dest_lat, t.dest_lon], "auto_title": t.auto_title, "title": ann.title if ann else "",
            "has_note": bool(ann and ann.note_html), "places": t.places or [], "countries": t.countries or [],
            "photo_count": t.photo_count, "cover_asset": t.cover_asset}


def _visible_trip(db: Session, user: User, trip_id: int) -> Trip:
    t = db.get(Trip, trip_id)
    if t is None:
        raise HTTPException(404, "Trip not found")
    tracker_for(db, user, t.tracker_id)
    if t.ongoing and not user.can_see_live:
        raise HTTPException(404, "Trip not found")
    return t


@router.get("/api/trips")
def list_trips(tracker_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ids = [tracker_for(db, user, tracker_id).id] if tracker_id else [t.id for t in visible_trackers(db, user)]
    if not ids:
        return []
    q = select(Trip).where(Trip.tracker_id.in_(ids)).order_by(Trip.start.desc())
    if not user.can_see_live:
        q = q.where(Trip.ongoing.is_(False))
    ann = _annotations(db, ids, "trip")
    return [trip_summary(t, ann.get((t.tracker_id, t.day_key))) for t in db.scalars(q)]


@router.get("/api/trips/{trip_id}")
def trip_detail(trip_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = _visible_trip(db, user, trip_id)
    ann = _annotations(db, [t.tracker_id], "trip").get((t.tracker_id, t.day_key))
    stay_ann = _annotations(db, [t.tracker_id], "stay")
    out = trip_summary(t, ann)
    out["note_html"] = ann.note_html if ann else ""
    out["stays"] = []
    for st in t.stays:
        a = stay_ann.get((t.tracker_id, st.day_key))
        out["stays"].append({"id": st.id, "day_key": st.day_key, "arrival": st.arrival, "departure": st.departure,
                             "lat": st.lat, "lon": st.lon, "nights": st.nights, "place_name": st.place_name,
                             "country_code": st.country_code, "photo_count": st.photo_count,
                             "cover_asset": st.cover_asset, "title": a.title if a else "",
                             "note_html": a.note_html if a else ""})
    return out


@router.get("/api/trips/{trip_id}/track")
def trip_track(trip_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = _visible_trip(db, user, trip_id)
    pts = load_points(db, t.tracker_id, t.start, t.end)
    return {"points": [list(p) for p in thin_out(pts)], "raw_count": len(pts)}


@router.get("/api/trips/{trip_id}/photos")
def trip_photos(trip_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """The trip's photos as seen with the user's own Immich access, each with a location."""
    t = _visible_trip(db, user, trip_id)
    s = settings.household(db).detection()
    tracker = tracker_for(db, user, t.tracker_id)
    pts = load_points(db, t.tracker_id, t.start, t.end)
    try:
        placed, unplaced = photo_service.tracker_photos(db, user, tracker, pts, t.start, t.end, s)
    except ImmichError as e:
        return {"photos": [], "without_location": 0, "error": str(e)}
    return {"photos": [p.__dict__ for p in placed], "without_location": unplaced}


@router.get("/api/trips/{trip_id}/timeline")
def trip_timeline(trip_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    t = _visible_trip(db, user, trip_id)
    s = settings.household(db).detection()
    tracker = tracker_for(db, user, t.tracker_id)
    pts = load_points(db, t.tracker_id, t.start, t.end)
    try:
        placed, _ = photo_service.tracker_photos(db, user, tracker, pts, t.start, t.end, s)
    except ImmichError:
        placed = []
    stays = detect_stays(pts, s)
    entries = build_timeline(pts, stays, placed, s)
    by_day = {st.day_key: st for st in t.stays}
    stay_ann = _annotations(db, [t.tracker_id], "stay")
    out = []
    for e in entries:
        d = {k: v for k, v in e.__dict__.items() if k != "extra"}
        if e.kind == "stay":
            key = day_key(e.start, s)
            d["day_key"] = key
            cached = by_day.get(key)
            if cached and not d["place"]:
                d["place"] = cached.place_name
            a = stay_ann.get((t.tracker_id, key))
            d["title"] = a.title if a else ""
            d["note_html"] = a.note_html if a else ""
        out.append(d)
    return {"entries": out}


# --- annotations ------------------------------------------------------------------------------------------------

_EMPTY_HTML = re.compile(r"<[^>]*>|&nbsp;|\s")
# Notes are rich text from the editor. Everything outside this allow-list is removed before storing.
NOTE_TAGS = {"p", "br", "b", "strong", "i", "em", "u", "s", "h2", "h3", "ul", "ol", "li", "a", "blockquote"}
NOTE_ATTRIBUTES = {"a": {"href"}}


def clean_note(html: str) -> str:
    html = nh3.clean(html or "", tags=NOTE_TAGS, attributes=NOTE_ATTRIBUTES, url_schemes={"http", "https", "mailto"},
                     link_rel="noopener noreferrer nofollow")
    return html if _EMPTY_HTML.sub("", html) else ""


@router.put("/api/annotations")
def put_annotation(body: AnnotationIn, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    """Set title and note of a trip or stay. Both empty deletes the annotation (the detected name applies again)."""
    tracker_for(db, user, body.tracker_id)
    html = clean_note(body.note_html)
    title = body.title.strip()
    row = db.scalar(select(Annotation).where(Annotation.tracker_id == body.tracker_id, Annotation.kind == body.kind,
                                             Annotation.day_key == body.day_key))
    if not title and not html:
        if row:
            db.delete(row)
            db.commit()
        return {"title": "", "note_html": ""}
    if row is None:
        row = Annotation(tracker_id=body.tracker_id, kind=body.kind, day_key=body.day_key)
        db.add(row)
    row.title, row.note_html, row.updated_by = title, html, user.id
    db.commit()
    return {"title": title, "note_html": html, "updated": time.time()}
