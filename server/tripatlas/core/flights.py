"""Photos taken on board an aircraft, and the flights they belong to. Pure functions.

Phones keep their GPS on in the air, so in-flight photos carry positions somewhere along the route — a village in
France the family never set foot in. Two signals identify them:
  1. speed: the same camera's previous or next photo lies further away than a car could drive in the time between
     (> AIR_SPEED_KMH). Comparing across cameras is useless — two family members' phones in different cities
     produce "jumps" of thousands of km/h without anyone flying;
  2. altitude: the GPS altitude stored in the photo's EXIF. Cruising altitude (~11,000 m) is unmistakable; climb and
     descent photos are recognised together with the speed signal.
Only speed candidates get their altitude read (that costs a download of the file header each)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .geo import distance_km

AIR_SPEED_KMH = 250.0
# Above this, a photo is taken in the air no matter how fast the neighbours moved (higher than any place people
# usually stand; Alpine summits up to 4,800 m are rare enough, and they would not come with a speed jump either).
CRUISE_ALTITUDE_M = 5000.0
# Above this, together with a fast neighbour, it is a climb or descent.
AIRBORNE_ALTITUDE_M = 1500.0
# With a fast neighbour within NEAR_S, a lower altitude still means "in the air" (approach over flat land).
LOW_AIRBORNE_ALTITUDE_M = 800.0
NEAR_S = 30 * 60
# Neighbours further apart in time than this say nothing about speed.
MAX_GAP_S = 6 * 3600
# In-flight photos further apart than this belong to different flights.
FLIGHT_GAP_S = 3 * 3600
# Departure / arrival: the last ground photo before and the first after, if within this time.
GROUND_WINDOW_S = 12 * 3600


@dataclass(frozen=True)
class GeoPhoto:
    id: str
    t: float
    lat: float
    lon: float
    device: str  # camera make + model; photos of different devices are never compared
    city: str | None = None


def _speed(a: GeoPhoto, b: GeoPhoto) -> tuple[float, float]:
    """(km/h, seconds apart)"""
    dt = abs(b.t - a.t)
    d = distance_km(a.lat, a.lon, b.lat, b.lon)
    if dt == 0:
        return (float("inf") if d > 1 else 0.0), 0.0
    return d / (dt / 3600), dt


def by_device(photos: Sequence[GeoPhoto]) -> dict[str, list[GeoPhoto]]:
    out: dict[str, list[GeoPhoto]] = {}
    for p in photos:
        if p.device:
            out.setdefault(p.device, []).append(p)
    for lst in out.values():
        lst.sort(key=lambda p: p.t)
    return out


def neighbour_speeds(photos: Sequence[GeoPhoto]) -> dict[str, tuple[float, float]]:
    """For every photo: (fastest speed to a neighbour within MAX_GAP_S, the fastest speed within NEAR_S)."""
    out: dict[str, tuple[float, float]] = {}
    for lst in by_device(photos).values():
        for i, p in enumerate(lst):
            fastest, fastest_near = 0.0, 0.0
            for j in (i - 1, i + 1):
                if 0 <= j < len(lst):
                    v, dt = _speed(p, lst[j])
                    if dt <= MAX_GAP_S:
                        fastest = max(fastest, v)
                    if dt <= NEAR_S:
                        fastest_near = max(fastest_near, v)
            out[p.id] = (fastest, fastest_near)
    return out


def candidates(photos: Sequence[GeoPhoto]) -> list[str]:
    """Photos worth reading the altitude of."""
    return [pid for pid, (v, _) in neighbour_speeds(photos).items() if v > AIR_SPEED_KMH]


def is_airborne(altitude_m: float | None, speed_kmh: float, speed_near_kmh: float) -> bool:
    if altitude_m is None:
        return False
    if altitude_m >= CRUISE_ALTITUDE_M:
        return True
    if altitude_m >= AIRBORNE_ALTITUDE_M and speed_kmh > AIR_SPEED_KMH:
        return True
    return altitude_m >= LOW_AIRBORNE_ALTITUDE_M and speed_near_kmh > AIR_SPEED_KMH


@dataclass
class Flight:
    start: float
    end: float
    photo_ids: list[str]
    max_altitude_m: float
    origin: tuple[float, float] | None = None
    destination: tuple[float, float] | None = None
    origin_name: str | None = None
    destination_name: str | None = None
    path: list[tuple[float, float]] = field(default_factory=list)  # positions of the in-flight photos, in order


def group_flights(photos: Sequence[GeoPhoto], airborne: dict[str, float]) -> list[Flight]:
    """Group in-flight photos (id → altitude) into flights, per device, and find where each flight started and ended:
    the device's last ground photo before and first after (within GROUND_WINDOW_S)."""
    flights: list[Flight] = []
    for lst in by_device(photos).values():
        current: list[GeoPhoto] = []

        def close(group: list[GeoPhoto], lst=lst) -> None:
            if not group:
                return
            first, last = group[0], group[-1]
            i0, i1 = lst.index(first), lst.index(last)
            before = next((p for p in reversed(lst[:i0]) if p.id not in airborne), None)
            after = next((p for p in lst[i1 + 1 :] if p.id not in airborne), None)
            near_before = before is not None and first.t - before.t <= GROUND_WINDOW_S
            near_after = after is not None and after.t - last.t <= GROUND_WINDOW_S
            flights.append(
                Flight(
                    start=first.t,
                    end=last.t,
                    photo_ids=[p.id for p in group],
                    max_altitude_m=max(airborne[p.id] for p in group),
                    origin=(before.lat, before.lon) if near_before else None,
                    destination=(after.lat, after.lon) if near_after else None,
                    origin_name=before.city if near_before else None,
                    destination_name=after.city if near_after else None,
                    path=[(p.lat, p.lon) for p in group],
                )
            )

        for p in lst:
            if p.id not in airborne:
                continue
            if current and p.t - current[-1].t > FLIGHT_GAP_S:
                close(current)
                current = []
            current.append(p)
        close(current)
    flights.sort(key=lambda f: f.start)
    return flights


# A flight must get somewhere: GPS glitches in a mountain village (900 m, one position jumping by 30 km) otherwise
# look like a take-off. Real flights either reach cruise altitude or connect places at least this far apart.
MIN_FLIGHT_KM = 100.0


def plausible(f: Flight) -> bool:
    if f.max_altitude_m >= CRUISE_ALTITUDE_M and len(f.photo_ids) > 1:
        return True
    if f.origin and f.destination:
        return distance_km(*f.origin, *f.destination) >= MIN_FLIGHT_KM
    if len(f.path) > 1:
        return distance_km(*f.path[0], *f.path[-1]) >= MIN_FLIGHT_KM
    return False
