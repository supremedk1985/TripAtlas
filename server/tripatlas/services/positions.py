"""Reading and writing positions."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..core.geo import Point
from ..db.models import Position, Tracker


def load_points(db: Session, tracker_id: int, start: float | None = None, end: float | None = None) -> list[Point]:
    q = select(Position.t, Position.lat, Position.lon, Position.speed_kmh, Position.altitude_m).where(
        Position.tracker_id == tracker_id
    )
    if start is not None:
        q = q.where(Position.t >= start)
    if end is not None:
        q = q.where(Position.t <= end)
    return [Point(*row) for row in db.execute(q.order_by(Position.t))]


def add_points(db: Session, tracker: Tracker, points: Iterable[Point], source: str, batch: int = 2000) -> int:
    """Insert points, ignoring timestamps the tracker already has. Returns the number of new rows."""
    rows = [
        {
            "tracker_id": tracker.id,
            "t": p.t,
            "lat": p.lat,
            "lon": p.lon,
            "speed_kmh": p.speed_kmh or 0,
            "altitude_m": p.altitude_m or 0,
            "source": source,
        }
        for p in points
    ]
    added = 0
    dialect = db.bind.dialect.name if db.bind else "sqlite"
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        if dialect == "sqlite":
            stmt = sqlite_insert(Position).values(chunk).on_conflict_do_nothing(index_elements=["tracker_id", "t"])
        else:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(Position).values(chunk).on_conflict_do_nothing(index_elements=["tracker_id", "t"])
        added += db.execute(stmt).rowcount or 0
    if added:
        tracker.dirty = True
    db.commit()
    return added


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
