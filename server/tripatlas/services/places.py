"""Cached place lookups (name, country, encyclopedia summary) keyed by a ~1 km grid cell and language."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_config
from ..db.models import Place, utcnow
from ..integrations.places import PlaceLookup

log = logging.getLogger(__name__)

# Encyclopedias change slowly; refresh after this long.
MAX_AGE = timedelta(days=180)


def cell_of(lat: float, lon: float) -> str:
    return f"{round(lat, 2):.2f},{round(lon, 2):.2f}"


def cached(db: Session, lat: float, lon: float, lang: str) -> Place | None:
    return db.scalar(select(Place).where(Place.cell == cell_of(lat, lon), Place.lang == lang))


def get_place(db: Session, lat: float, lon: float, lang: str, refresh: bool = False) -> Place:
    """Return cached place info, looking it up online if missing or stale."""
    row = cached(db, lat, lon, lang)
    if row and not refresh and row.fetched_at and utcnow() - _aware(row.fetched_at) < MAX_AGE:
        return row
    with PlaceLookup(f"TripAtlas/0.1 ({get_config().contact})") as lookup:
        info = lookup.lookup(lat, lon, lang)
    if row is None:
        row = Place(cell=cell_of(lat, lon), lang=lang)
        db.add(row)
    for f in ("name", "country", "country_code", "wikidata", "article_title", "article_url", "summary",
              "thumbnail_url", "kids_summary", "kids_url", "sights"):
        setattr(row, f, getattr(info, f))
    row.fetched_at = utcnow()
    db.commit()
    return row


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def place_dict(p: Place | None, kids: bool = False) -> dict | None:
    if p is None:
        return None
    d = {"name": p.name, "country": p.country, "country_code": p.country_code}
    if kids:
        d.update(summary=p.kids_summary, url=p.kids_url, thumbnail_url=p.thumbnail_url)
    else:
        d.update(summary=p.summary, url=p.article_url, title=p.article_title, thumbnail_url=p.thumbnail_url,
                 kids_summary=p.kids_summary, sights=p.sights or [])
    return d
