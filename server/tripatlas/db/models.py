"""Database schema. Change it only together with an Alembic migration (see docs/development.md).

Conventions: timestamps of recorded data are Unix seconds (int/float, UTC); `day_key` is a local calendar date
'YYYY-MM-DD' used to attach user content (titles, notes) to detected trips and stays — detection may shift a trip's
start by minutes when points are added later, the day almost never changes."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, deferred, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Role(enum.StrEnum):
    admin = "admin"  # everything, including users and connections
    member = "member"  # sees assigned trackers, edits titles/notes, imports into assigned trackers
    child = "child"  # read-only, simplified interface, never sees live positions


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False))
    locale: Mapped[str] = mapped_column(String(8), default="en")
    # Encrypted personal Immich API key; None = use the household key.
    immich_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_see_live: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Profile picture: a small square JPEG (the browser crops and scales it); loaded only when asked for
    avatar: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    avatar_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trackers: Mapped[list[Tracker]] = relationship(secondary="user_trackers", back_populates="users")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True
    )  # sha256 of the token; the token itself is never stored
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="web")  # web | app
    label: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class Setting(Base):
    """Household settings as key/value. Secrets are stored encrypted (services/secrets.py)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)


class TrackerKind(enum.StrEnum):
    vehicle = "vehicle"
    person = "person"
    # A bicycle: every ride is an entry of its own, also without a night away (see services/trips.py)
    bike = "bike"


class Tracker(Base):
    """Something that moves: a camper van, a car, a person. Positions come from Traccar and/or imports."""

    __tablename__ = "trackers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[TrackerKind] = mapped_column(Enum(TrackerKind, native_enum=False), default=TrackerKind.vehicle)
    color: Mapped[str] = mapped_column(String(9), default="#3b82f6")
    traccar_device_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    # When several trackers travel together, photos go to the one with the highest priority.
    photo_priority: Mapped[int] = mapped_column(Integer, default=0)
    synced_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Positions or settings changed since the last trip detection run.
    dirty: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar: Mapped[bytes | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    users: Mapped[list[User]] = relationship(secondary="user_trackers", back_populates="trackers")


class UserTracker(Base):
    __tablename__ = "user_trackers"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"), primary_key=True)


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("tracker_id", "t"), Index("ix_positions_tracker_t", "tracker_id", "t"))
    id: Mapped[int] = mapped_column(primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"))
    t: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0)
    altitude_m: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(32), default="traccar")  # traccar | gpx | google | ...


class Trip(Base):
    """Detected trip — a cache, recomputed whenever positions change. User content lives in Annotation."""

    __tablename__ = "trips"
    __table_args__ = (UniqueConstraint("tracker_id", "day_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"), index=True)
    day_key: Mapped[str] = mapped_column(String(10))
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    ongoing: Mapped[bool] = mapped_column(Boolean, default=False)
    distance_km: Mapped[float] = mapped_column(Float)
    farthest_km: Mapped[float] = mapped_column(Float)
    nights: Mapped[int] = mapped_column(Integer)
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lon: Mapped[float] = mapped_column(Float)
    auto_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    places: Mapped[list | None] = mapped_column(JSON, nullable=True)  # names of the stays, in order
    countries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    cover_asset: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stays: Mapped[list[Stay]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="Stay.arrival"
    )


class Stay(Base):
    __tablename__ = "stays"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"))
    day_key: Mapped[str] = mapped_column(String(10))
    arrival: Mapped[float] = mapped_column(Float)
    departure: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    nights: Mapped[int] = mapped_column(Integer)
    place_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    cover_asset: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trip: Mapped[Trip] = relationship(back_populates="stays")


class Annotation(Base):
    """Custom title and rich-text note for a trip or a stay, keyed by tracker + kind + local start day."""

    __tablename__ = "annotations"
    __table_args__ = (UniqueConstraint("tracker_id", "kind", "day_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))  # trip | stay
    day_key: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200), default="")
    note_html: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class Place(Base):
    """Cached knowledge about a place: reverse-geocoded name plus an encyclopedia summary. Keyed by a coarse grid
    cell (~1 km) and language so nearby stays share one lookup."""

    __tablename__ = "places"
    __table_args__ = (UniqueConstraint("cell", "lang"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cell: Mapped[str] = mapped_column(String(32))
    lang: Mapped[str] = mapped_column(String(8))
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    wikidata: Mapped[str | None] = mapped_column(String(32), nullable=True)
    article_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    article_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Child-friendly text (e.g. Klexikon for German) — None if no such source has an article.
    kids_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    kids_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sights: Mapped[list | None] = mapped_column(JSON, nullable=True)  # nearby articles [{title, url, distance_m}]
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | running | done | failed
    added: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PhotoCheck(Base):
    """GPS altitude read from a photo's EXIF (for flight detection, core/flights.py). One row per checked asset,
    also when there was no altitude, so no photo is downloaded twice."""

    __tablename__ = "photo_checks"
    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
