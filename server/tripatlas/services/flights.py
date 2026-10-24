"""Find in-flight photos in Immich and the flights they belong to (rules in core/flights.py).

Runs in the background job, at most every REFRESH_S: loads all assets with EXIF (one paged pass), reads the GPS
altitude of new speed candidates (CHECKS_PER_ROUND file headers per round, remembered in `photo_checks`), and stores
the result as the setting "flights": {"updated", "airborne": {asset id: altitude}, "flights": [...]}. Uses the
household Immich key — flights are household knowledge like trips."""

from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.flights import GeoPhoto, candidates, group_flights, is_airborne, neighbour_speeds, plausible
from ..core.geo import iso_to_ts
from ..db.models import PhotoCheck, Setting
from ..integrations.immich import ImmichError
from . import photos as photo_service

log = logging.getLogger(__name__)

REFRESH_S = 6 * 3600
CHECKS_PER_ROUND = 400


def stored(db: Session) -> dict:
    row = db.get(Setting, "flights")
    return row.value if row and isinstance(row.value, dict) else {}


def airborne_ids(db: Session) -> set[str]:
    return set(stored(db).get("airborne", {}))


def _geo_photos(assets) -> list[GeoPhoto]:
    out = []
    for a in assets:
        e = a.get("exifInfo") or {}
        if e.get("latitude") is None or e.get("longitude") is None or a.get("type") == "VIDEO":
            continue
        device = " ".join(x for x in (e.get("make"), e.get("model")) if x)
        try:
            t = iso_to_ts(a.get("fileCreatedAt") or a.get("localDateTime"))
        except (TypeError, ValueError):
            continue
        out.append(GeoPhoto(a["id"], t, e["latitude"], e["longitude"], device, e.get("city")))
    return out


def refresh(db: Session, force: bool = False) -> dict | None:
    """Recompute if due. Returns a short summary, or None if nothing was done."""
    current = stored(db)
    pending = current.get("pending", 0)
    if not force and not pending and time.time() - current.get("updated", 0) < REFRESH_S:
        return None
    try:
        client = photo_service.client_for(db, None)
    except ImmichError:
        return None
    with client:
        photos = _geo_photos(client.all_assets())
        speeds = neighbour_speeds(photos)
        cand = candidates(photos)
        checked = {
            r.asset_id: r.altitude_m for r in db.scalars(select(PhotoCheck).where(PhotoCheck.asset_id.in_(cand)))
        }
        todo = [pid for pid in cand if pid not in checked]
        for pid in todo[:CHECKS_PER_ROUND]:
            try:
                alt = client.gps_altitude(pid)
            except ImmichError as e:
                log.info("Altitude of %s unavailable: %s", pid, e)
                continue
            db.merge(PhotoCheck(asset_id=pid, altitude_m=alt))
            checked[pid] = alt
        db.commit()
    airborne = {pid: checked[pid] for pid in cand if is_airborne(checked.get(pid), *speeds[pid])}
    # Only photos of plausible flights count as taken in the air; the rest (GPS glitches) stay places.
    flights = [f for f in group_flights(photos, airborne) if plausible(f)]
    airborne = {pid: airborne[pid] for f in flights for pid in f.photo_ids}
    value = {
        "updated": time.time(),
        "pending": max(0, len(todo) - CHECKS_PER_ROUND),
        "airborne": airborne,
        "flights": [
            {
                "start": f.start,
                "end": f.end,
                "photo_ids": f.photo_ids,
                "max_altitude_m": f.max_altitude_m,
                "origin": f.origin,
                "destination": f.destination,
                "origin_name": f.origin_name,
                "destination_name": f.destination_name,
                "path": f.path,
            }
            for f in flights
        ],
    }
    row = db.get(Setting, "flights")
    if row:
        row.value = value
    else:
        db.add(Setting(key="flights", value=value))
    db.commit()
    return {
        "candidates": len(cand),
        "checked_now": min(len(todo), CHECKS_PER_ROUND),
        "airborne": len(airborne),
        "flights": len(flights),
    }
