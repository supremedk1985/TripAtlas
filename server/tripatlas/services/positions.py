"""Reading and writing positions."""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Iterator
from itertools import islice

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..core.geo import Point, drop_spikes
from ..db.models import Position, Tracker


def load_points(db: Session, tracker_id: int, start: float | None = None, end: float | None = None) -> list[Point]:
    q = select(Position.t, Position.lat, Position.lon, Position.speed_kmh, Position.altitude_m).where(
        Position.tracker_id == tracker_id
    )
    if start is not None:
        q = q.where(Position.t >= start)
    if end is not None:
        q = q.where(Position.t <= end)
    # single corrupt fixes stay in the database (they came from Traccar) but never reach routes, trips or bounds
    return drop_spikes([Point(*row) for row in db.execute(q.order_by(Position.t))])


IMPORT_MIN_GAP_S = 10
# An imported point within this many seconds of one the tracker already has is the same point — the same ride from
# another export, with times rounded or cut off differently. Less than half the import spacing, so no ride is lost.
IMPORT_SAME_POINT_S = 4


def thin(points: Iterable[Point], min_gap_s: float = IMPORT_MIN_GAP_S) -> Iterator[Point]:
    """At most one point per `min_gap_s` seconds. Recording apps write every second; for trips a point every
    10 s is plenty (about 70 m by bike) and keeps a decade of rides small. Deterministic, so importing the same file
    again keeps the same timestamps — and those are then recognised as duplicates. Files need not be sorted: a jump
    back in time (the next ride of an export listed newest first) starts a new run.
    Times are rounded to whole seconds: the same ride exported by two apps (one with milliseconds, one without) is
    then the same ride, and its points are recognised as duplicates."""
    last: float | None = None
    for p in points:
        p = p._replace(t=float(round(p.t)))
        if last is None or abs(p.t - last) >= min_gap_s:
            last = p.t
            yield p


def _near(sorted_ts: list[float], t: float, within_s: float) -> bool:
    """Is there a time in `sorted_ts` at most `within_s` seconds from `t`?"""
    i = bisect.bisect_left(sorted_ts, t - within_s)
    return i < len(sorted_ts) and sorted_ts[i] <= t + within_s


def add_points_counted(
    db: Session, tracker: Tracker, points: Iterable[Point], source: str, batch: int = 2000, same_within_s: float = 0
) -> tuple[int, int]:
    """Insert points in batches straight from an iterator (nothing is held beyond one batch), ignoring timestamps
    the tracker already has (`same_within_s`: also points that close to an existing one — for file imports) and
    impossible coordinates. Nothing is committed until the end, so a caller can roll a failed import back
    completely. Returns (new rows, points kept)."""
    added = seen = 0
    dialect = db.bind.dialect.name if db.bind else "sqlite"
    it = iter(points)
    while chunk := [
        {
            "tracker_id": tracker.id,
            "t": p.t,
            "lat": p.lat,
            "lon": p.lon,
            "speed_kmh": p.speed_kmh or 0,
            "altitude_m": p.altitude_m or 0,
            "source": source,
        }
        for p in islice((q for q in it if -90 <= q.lat <= 90 and -180 <= q.lon <= 180), batch)
    ]:
        seen += len(chunk)
        if same_within_s:
            lo, hi = min(r["t"] for r in chunk) - same_within_s, max(r["t"] for r in chunk) + same_within_s
            have = sorted(
                db.scalars(
                    select(Position.t).where(Position.tracker_id == tracker.id, Position.t >= lo, Position.t <= hi)
                )
            )

            chunk = [r for r in chunk if not _near(have, r["t"], same_within_s)]
            if not chunk:
                continue
        if dialect == "sqlite":
            stmt = sqlite_insert(Position).values(chunk).on_conflict_do_nothing(index_elements=["tracker_id", "t"])
        else:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(Position).values(chunk).on_conflict_do_nothing(index_elements=["tracker_id", "t"])
        added += db.execute(stmt).rowcount or 0
    if added:
        tracker.dirty = True
    db.commit()
    return added, seen


def add_points(db: Session, tracker: Tracker, points: Iterable[Point], source: str, batch: int = 2000) -> int:
    """Insert points, ignoring timestamps the tracker already has. Returns the number of new rows."""
    return add_points_counted(db, tracker, points, source, batch)[0]


def bounds(db: Session, tracker_id: int) -> tuple[float | None, float | None, int]:
    row = db.execute(
        select(func.min(Position.t), func.max(Position.t), func.count()).where(Position.tracker_id == tracker_id)
    ).one()
    return row[0], row[1], row[2]


def latest(db: Session, tracker_id: int) -> Point | None:
    row = db.execute(
        select(Position.t, Position.lat, Position.lon, Position.speed_kmh, Position.altitude_m)
        .where(Position.tracker_id == tracker_id)
        .order_by(Position.t.desc())
        .limit(1)
    ).first()
    return Point(*row) if row else None
