"""The background loop: sync Traccar → recompute changed trackers → look up unknown places. One thread, one round
every `sync_interval_minutes`; a round can also be requested (e.g. after an import or a settings change)."""

from __future__ import annotations

import logging
import threading
import time

from sqlalchemy import select

from ..config import get_config
from ..db.models import Stay, Tracker
from ..db.session import db_session
from . import settings
from .backup import make_snapshot
from .flights import refresh as refresh_flights
from .places import cached, get_place
from .sync import sync_all
from .trips import recompute_dirty

log = logging.getLogger(__name__)

# Place lookups per round — Nominatim allows one request per second, and each place costs several requests.
PLACES_PER_ROUND = 20


class BackgroundJobs:
    def __init__(self):
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_result: dict = {}
        self.running = False
        self.last_run_at: float | None = None
        self.last_duration_s: float | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="tripatlas-jobs", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def trigger(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        interval = get_config().sync_interval_minutes * 60
        while not self._stop.is_set():
            self.run_once()
            self._wake.wait(interval)
            self._wake.clear()

    def run_once(self) -> dict:
        self.running = True
        started = time.time()
        result: dict = {}
        try:
            with db_session() as db:
                if not settings.household(db).setup_complete:
                    return result
                sync_errors: list[str] = []
                try:
                    result["synced"] = sync_all(db, sync_errors)
                except Exception as e:  # a failing source must not stop the other steps
                    log.warning("Sync failed: %s", e)
                    sync_errors.append(str(e))
                if sync_errors:
                    result["sync_error"] = "; ".join(sync_errors)[:500]
                result["recomputed"] = recompute_dirty(db)
                result["places"] = enrich_places(db)
                try:
                    if make_snapshot():
                        result["snapshot"] = True
                except Exception as e:  # a full disk must not stop sync and detection
                    log.warning("Database snapshot failed: %s", e)
                try:
                    result["flights"] = refresh_flights(db)
                except Exception as e:  # photos are optional; never stop the loop over them
                    log.warning("Flight detection failed: %s", e)
        except Exception:
            log.exception("Background round failed")
        finally:
            self.running = False
            self.last_result = result
            self.last_run_at = started
            self.last_duration_s = round(time.time() - started, 1)
        return result


def enrich_places(db, limit: int = PLACES_PER_ROUND) -> int:
    """Look up stays whose place is not cached yet; mark their trackers for recomputation so names appear."""
    hh = settings.household(db)
    if not hh.place_info_enabled:
        return 0
    done, dirty = 0, set()
    for st in db.scalars(select(Stay).order_by(Stay.arrival.desc())):
        if done >= limit:
            break
        if cached(db, st.lat, st.lon, hh.default_locale):
            continue
        try:
            get_place(db, st.lat, st.lon, hh.default_locale)
        except Exception as e:  # network trouble: try again next round
            log.info("Place lookup failed: %s", e)
            break
        done += 1
        dirty.add(st.tracker_id)
    for tid in dirty:
        t = db.get(Tracker, tid)
        if t:
            t.dirty = True
    db.commit()
    return done


jobs = BackgroundJobs()
