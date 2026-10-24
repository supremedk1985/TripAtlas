"""Pull new positions from Traccar into the local database."""

from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.geo import iso_to_ts
from ..db.models import Tracker
from ..integrations.traccar import TraccarClient, TraccarError
from . import settings
from .positions import add_points

log = logging.getLogger(__name__)

CHUNK_S = 30 * 86400  # one request per 30 days of history
OVERLAP_S = 3600  # re-read the last hour: positions can arrive late (buffered by the tracker)
DEFAULT_HISTORY_DAYS = 365 * 3


def traccar_client(db: Session) -> TraccarClient:
    cfg = settings.traccar(db)
    if not cfg.configured:
        raise TraccarError("Traccar is not configured")
    return TraccarClient(cfg.url, token=cfg.token, email=cfg.email, password=cfg.password)


def sync_tracker(db: Session, client: TraccarClient, tracker: Tracker, now: float | None = None) -> int:
    if tracker.traccar_device_id is None:
        return 0
    now = now or time.time()
    hh = settings.household(db)
    start = (
        tracker.synced_until - OVERLAP_S
        if tracker.synced_until
        else (iso_to_ts(hh.history_start) if hh.history_start else now - DEFAULT_HISTORY_DAYS * 86400)
    )
    added = 0
    while start < now:
        end = min(start + CHUNK_S, now)
        pts = client.positions(tracker.traccar_device_id, start, end)
        added += add_points(db, tracker, pts, "traccar")
        start = end
    tracker.synced_until = now
    db.commit()
    return added


def sync_all(db: Session, errors: list[str] | None = None) -> dict[str, int]:
    """Sync every tracker linked to a Traccar device. Returns {tracker name: new positions}; trackers that failed
    are listed in `errors` (so the status page can say so instead of "ready")."""
    trackers = list(db.scalars(select(Tracker).where(Tracker.traccar_device_id.is_not(None))))
    if not trackers:
        return {}
    out = {}
    with traccar_client(db) as client:
        for t in trackers:
            try:
                out[t.name] = sync_tracker(db, client, t)
            except TraccarError as e:
                log.warning("Sync of %s failed: %s", t.name, e)
                db.rollback()
                if errors is not None:
                    errors.append(f"{t.name}: {e}")
    return out
