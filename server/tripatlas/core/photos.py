"""Which photos belong to a tracker's journey, and where were they taken? Pure functions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from .detection import DetectionSettings
from .geo import Point, distance_km, location_at, position_at

# A photo with its own GPS belongs to a tracker only if it was taken within this distance of the tracker's location
# at that time. Without this check, a second vehicle parked at home got every holiday photo of the family.
MATCH_RADIUS_KM = 50.0

RAW_EXTENSIONS = (".raf", ".dng", ".nef", ".cr2", ".cr3", ".arw", ".orf", ".rw2", ".pef", ".srw")


@dataclass(frozen=True)
class Photo:
    id: str
    t: float
    lat: float | None = None
    lon: float | None = None
    is_video: bool = False
    is_favorite: bool = False
    city: str | None = None
    country: str | None = None
    width: int | None = None
    height: int | None = None
    # True if the location was derived from the track instead of the photo's own GPS
    estimated: bool = False

    @property
    def has_gps(self) -> bool:
        return self.lat is not None and self.lon is not None

    @property
    def landscape(self) -> bool:
        return bool(self.width and self.height and self.width > self.height)


def matches_tracker(points: Sequence[Point], photo: Photo, radius_km: float = MATCH_RADIUS_KM) -> bool:
    """A geotagged photo matches if it was taken near the tracker. Unknown tracker location (no signal): yes."""
    loc = location_at(points, photo.t)
    return loc is None or distance_km(loc[0], loc[1], photo.lat, photo.lon) <= radius_km


def claimed_by(points: Sequence[Point], photo: Photo, s: DetectionSettings, radius_km: float = MATCH_RADIUS_KM) -> bool:
    """Does a (higher-priority) tracker claim this photo? With GPS: if its known location was near. Without GPS
    (many system cameras have none): if it was away from home at that time. Unknown location: no.

    Use case: a family travels in the camper van while the car stays at home or follows — the photos belong to the
    van, not to both."""
    loc = location_at(points, photo.t)
    if loc is None:
        return False
    if photo.has_gps:
        return distance_km(loc[0], loc[1], photo.lat, photo.lon) <= radius_km
    return not s.is_home(loc[0], loc[1])


def place_photos(
    points: Sequence[Point],
    photos: Sequence[Photo],
    s: DetectionSettings,
    higher_priority: Sequence[Sequence[Point]] = (),
) -> tuple[list[Photo], int]:
    """Photos of this tracker's journey, with a location for each. Photos without GPS get the tracker's position at
    capture time, marked `estimated` (on foot one can be far from the vehicle). Returns (placed, without_location)."""
    placed, unplaced = [], 0
    for ph in photos:
        if any(claimed_by(other, ph, s) for other in higher_priority):
            continue
        if ph.has_gps:
            if matches_tracker(points, ph):
                placed.append(ph)
            continue
        pos = position_at(points, ph.t)
        if pos is None:
            unplaced += 1
            continue
        placed.append(replace(ph, lat=round(pos[0], 6), lon=round(pos[1], 6), estimated=True))
    placed.sort(key=lambda p: p.t)
    return placed, unplaced


def most_common_city(
    photos: Sequence[Photo],
    near: tuple[float, float] | None = None,
    within_km: float = 30,
    exclude_home: DetectionSettings | None = None,
) -> str | None:
    """The city that appears most often among photos with real GPS — a good name for a place."""
    counts: dict[str, int] = {}
    for ph in photos:
        if ph.estimated or not ph.city:
            continue
        if near and distance_km(near[0], near[1], ph.lat, ph.lon) > within_km:
            continue
        if exclude_home and exclude_home.is_home(ph.lat, ph.lon):
            continue
        counts[ph.city] = counts.get(ph.city, 0) + 1
    return max(counts, key=counts.get) if counts else None


def pick_cover(photos: Sequence[Photo], near: tuple[float, float] | None = None) -> str | None:
    """A cover image: favourites first, then landscape images, real GPS before estimated; near a place if given,
    otherwise the middle of the period."""
    images = [p for p in photos if not p.is_video]
    if not images:
        return None
    for pool in (
        [p for p in images if p.is_favorite],
        [p for p in images if p.landscape and not p.estimated],
        [p for p in images if not p.estimated],
        images,
    ):
        if pool:
            if near:
                return min(pool, key=lambda p: distance_km(near[0], near[1], p.lat, p.lon)).id
            return pool[len(pool) // 2].id
    return None
