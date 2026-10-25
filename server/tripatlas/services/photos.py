"""Immich access per user, with small in-memory caches (Immich is local and fast, but a map with 40,000 markers
should not be fetched on every pan)."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.detection import DetectionSettings
from ..core.geo import Point, ts_to_iso
from ..core.photos import Photo, pick_cover, place_photos
from ..db.models import Tracker, User
from ..integrations.immich import ImmichClient, ImmichError
from . import settings
from .positions import load_points
from .secrets import decrypt

_cache: dict[tuple, tuple[float, object]] = {}
_lock = threading.Lock()


# How far back accounts without live access see (positions, ongoing trips, photos)
LIVE_DELAY_S = 6 * 3600

def cached[T](key: tuple, seconds: float, fetch: Callable[[], T]) -> T:
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < seconds:
            return hit[1]  # type: ignore[return-value]
    value = fetch()
    with _lock:
        _cache[key] = (time.time(), value)
        if len(_cache) > 200:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:50]:
                _cache.pop(k, None)
    return value


def api_key_for(db: Session, user: User | None) -> str:
    """The user's own key if set, else the household key."""
    if user is not None and user.immich_api_key:
        key = decrypt(user.immich_api_key)
        if key:
            return key
    return settings.immich(db).api_key


def client_for(db: Session, user: User | None) -> ImmichClient:
    cfg = settings.immich(db)
    key = api_key_for(db, user)
    if not cfg.url or not key:
        raise ImmichError("Immich is not configured")
    return ImmichClient(cfg.url, key)


def key_id(db: Session, user: User | None) -> str:
    """Cache key that separates what different Immich keys may see, without keeping the key itself around."""
    return hashlib.sha256(api_key_for(db, user).encode()).hexdigest()[:16]


def markers(db: Session, user: User) -> list[dict]:
    # Without live access a fresh photo would tell where someone is right now: only photos older than the live
    # delay (in steps of 10 minutes, so the cache still works)
    before = None if user.can_see_live else int((time.time() - LIVE_DELAY_S) // 600 * 600)

    def fetch():
        with client_for(db, user) as c:
            return [
                {"id": m["id"], "lat": m["lat"], "lon": m["lon"], "city": m.get("city"), "country": m.get("country")}
                for m in c.map_markers(taken_before=ts_to_iso(before) if before else None)
                if m.get("lat") is not None and m.get("lon") is not None
            ]

    return cached(("markers", key_id(db, user), before), 300, fetch)


def photos_between(db: Session, user: User | None, start: float, end: float) -> list[Photo]:
    def fetch():
        with client_for(db, user) as c:
            return c.photos_between(ts_to_iso(start), ts_to_iso(end))

    ongoing = end > time.time() - 3600
    return cached(("period", key_id(db, user), int(start), int(end)), 120 if ongoing else 900, fetch)


def higher_priority_tracks(db: Session, tracker: Tracker, start: float, end: float) -> list[list[Point]]:
    others = db.scalars(
        select(Tracker).where(Tracker.id != tracker.id, Tracker.photo_priority > tracker.photo_priority)
    )
    return [pts for o in others if (pts := load_points(db, o.id, start - 6 * 3600, end + 6 * 3600))]


def tracker_photos(
    db: Session,
    user: User | None,
    tracker: Tracker,
    points: list[Point],
    start: float,
    end: float,
    s: DetectionSettings,
) -> tuple[list[Photo], int]:
    """Photos taken on this tracker's journey between start and end, each with a location."""
    photos = photos_between(db, user, start, end)
    return place_photos(points, photos, s, higher_priority_tracks(db, tracker, start, end))


COVER_QUERY = "beautiful landscape scenery vacation"


def choose_cover(client: ImmichClient, placed: list[Photo], start: float, end: float) -> str | None:
    """Favourites first; otherwise ask Immich's image search for a beautiful landscape among this journey's photos
    (the "photo nearest to the destination" turned out to be a puddle); otherwise any landscape photo."""
    ids = {p.id for p in placed if not p.is_video}
    favs = [p for p in placed if p.is_favorite and p.id in ids]
    if favs:
        return (next((p for p in favs if p.landscape), favs[0])).id
    try:
        hits = [p for p in client.smart_search(COVER_QUERY, ts_to_iso(start), ts_to_iso(end)) if p.id in ids]
    except ImmichError:
        hits = []
    if hits:
        return (next((p for p in hits if p.landscape), hits[0])).id
    return pick_cover(placed)


# Policies under which Immich makes a smaller copy of large videos for playback. With "required" (Immich's default)
# or "disabled", a phone video is streamed as recorded — often 15–25 Mbit/s, more than a weak mobile connection carries.
SMALL_VIDEO_POLICIES = {"optimal", "bitrate", "all"}
_video_check: dict = {"at": 0.0, "result": None}


def video_check(db: Session) -> dict:
    """Whether Immich keeps small copies of videos for playback. `ok` is None when it cannot be told (no Immich, or a
    key without administrator rights). Asked at most once an hour."""
    if time.time() - _video_check["at"] < 3600 and _video_check["result"] is not None:
        return _video_check["result"]
    result: dict = {"ok": None, "policy": None, "target": None}
    try:
        with client_for(db, None) as c:
            ff = c.video_transcoding()
        if ff is not None:
            policy, target = ff.get("transcode"), str(ff.get("targetResolution") or "")
            result = {"ok": policy in SMALL_VIDEO_POLICIES and target != "original", "policy": policy, "target": target}
    except ImmichError:
        pass
    _video_check.update(at=time.time(), result=result)
    return result
