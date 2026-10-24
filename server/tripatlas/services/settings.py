"""Typed access to the household settings stored in the `settings` table."""
from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.detection import DetectionSettings
from ..db.models import Setting
from .secrets import decrypt, encrypt


class HouseholdSettings(BaseModel):
    name: str = "TripAtlas"
    setup_complete: bool = False
    home_lat: float | None = None
    home_lon: float | None = None
    home_radius_km: float = Field(4.0, ge=0.5, le=50)
    timezone: str = "UTC"
    default_locale: str = "en"
    # Ignore positions before this date (ISO), e.g. test data from the tracker's first days.
    history_start: str | None = None
    min_trip_nights: int = Field(1, ge=1, le=30)
    min_trip_distance_km: float = Field(15, ge=1)
    # Look up place descriptions online (Wikipedia, OpenStreetMap Nominatim). Off = no external requests.
    place_info_enabled: bool = True

    def detection(self) -> DetectionSettings | None:
        if self.home_lat is None or self.home_lon is None:
            return None
        return DetectionSettings(home_lat=self.home_lat, home_lon=self.home_lon, timezone=self.timezone,
                                 home_radius_km=self.home_radius_km, min_nights=self.min_trip_nights,
                                 min_distance_km=self.min_trip_distance_km)


class TraccarSettings(BaseModel):
    url: str = ""
    # Either an API token (Traccar ≥ 5.x, preferred) or e-mail + password.
    token: str = ""
    email: str = ""
    password: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and (self.token or (self.email and self.password)))


class ImmichSettings(BaseModel):
    url: str = ""
    # Household key: used for users without a personal key (children, typically).
    api_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.api_key)


_SECRET_FIELDS = {"traccar": ("token", "password"), "immich": ("api_key",)}
_MODELS = {"household": HouseholdSettings, "traccar": TraccarSettings, "immich": ImmichSettings}


def load(db: Session, key: str):
    model = _MODELS[key]
    row = db.get(Setting, key)
    data = dict(row.value) if row and isinstance(row.value, dict) else {}
    for f in _SECRET_FIELDS.get(key, ()):
        data[f] = decrypt(data.get(f))
    return model(**data)


def save(db: Session, key: str, value: BaseModel) -> None:
    data = value.model_dump()
    for f in _SECRET_FIELDS.get(key, ()):
        data[f] = encrypt(data[f]) if data.get(f) else ""
    row = db.get(Setting, key)
    if row:
        row.value = data
    else:
        db.add(Setting(key=key, value=data))
    db.commit()


def household(db: Session) -> HouseholdSettings:
    return load(db, "household")


def traccar(db: Session) -> TraccarSettings:
    return load(db, "traccar")


def immich(db: Session) -> ImmichSettings:
    return load(db, "immich")
