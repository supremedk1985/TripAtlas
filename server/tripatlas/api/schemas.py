"""Request/response models shared by several routers."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..db.models import Role, TrackerKind

LOCALES = ("en", "de")


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: Role
    locale: str
    can_see_live: bool
    has_immich_key: bool
    tracker_ids: list[int]


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    role: Role = Role.member
    locale: str = "en"
    can_see_live: bool | None = None
    tracker_ids: list[int] = []


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=120)
    password: str | None = Field(None, min_length=8, max_length=200)
    role: Role | None = None
    locale: str | None = None
    can_see_live: bool | None = None
    tracker_ids: list[int] | None = None
    immich_api_key: str | None = None   # "" removes the personal key


class TrackerOut(BaseModel):
    id: int
    name: str
    kind: TrackerKind
    color: str
    traccar_device_id: int | None
    photo_priority: int
    has_avatar: bool
    position_count: int | None = None
    first: float | None = None
    last: float | None = None
    latest: dict | None = None


class TrackerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: TrackerKind = TrackerKind.vehicle
    color: str = Field("#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    traccar_device_id: int | None = None
    photo_priority: int = 0


class TrackerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    kind: TrackerKind | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    traccar_device_id: int | None = None
    photo_priority: int | None = None


class AnnotationIn(BaseModel):
    tracker_id: int
    kind: str = Field(pattern=r"^(trip|stay)$")
    day_key: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    title: str = Field("", max_length=200)
    note_html: str = Field("", max_length=300_000)
