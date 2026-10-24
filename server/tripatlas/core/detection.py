"""Trip, stay and drive detection. Pure functions over a time-sorted list of `Point`s; everything configurable lives
in `DetectionSettings`. These rules were tuned on real camper-van data — the docstrings say why each threshold is what
it is, so please keep them up to date when changing a rule (and add a test for the case that motivated it)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .geo import Point, distance_km, index_before, path_length_km, point_distance_km, slice_by_time


@dataclass(frozen=True)
class DetectionSettings:
    home_lat: float
    home_lon: float
    timezone: str = "UTC"
    # Further away than this from home counts as "away".
    home_radius_km: float = 4.0
    # A trip needs at least this many nights away and must reach at least this distance — day trips are not trips.
    min_nights: int = 1
    min_distance_km: float = 15.0
    # The hour (local time) whose location defines where a night was spent.
    night_hour: int = 3
    # Consecutive nights at most this far apart are the same stay (same campsite). 20 km merged two different
    # campsites into one stay during testing; 5 km keeps them apart.
    stay_merge_km: float = 5.0
    # Arrival/departure at a stay = first/last point within this radius of the night location.
    stay_near_km: float = 2.0
    # The last point before night_hour may be at most this old; trackers are often silent at night.
    night_max_age_h: float = 18.0
    # Drives: a stop is a pause of at least this long between moving points; shorter drives are manoeuvring.
    drive_pause_s: float = 600
    drive_min_km: float = 0.5

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def is_home(self, lat: float, lon: float) -> bool:
        return distance_km(self.home_lat, self.home_lon, lat, lon) <= self.home_radius_km

    def home_distance(self, lat: float, lon: float) -> float:
        return distance_km(self.home_lat, self.home_lon, lat, lon)


def night_times(start: float, end: float, s: DetectionSettings) -> list[float]:
    """All instants `night_hour` local time within [start, end] — one per night."""
    tz = s.tz
    out = []
    day = datetime.fromtimestamp(start, tz).date() - timedelta(days=1)
    last = datetime.fromtimestamp(end, tz).date()
    while day <= last:
        instant = datetime.combine(day, time(s.night_hour, 0), tz).timestamp()
        if start <= instant <= end:
            out.append(instant)
        day += timedelta(days=1)
    return out


@dataclass
class Trip:
    start: float
    end: float
    distance_km: float
    farthest_km: float
    nights: int
    destination: tuple[float, float]


def detect_trips(points: Sequence[Point], s: DetectionSettings, margin_s: float = 3600) -> list[Trip]:
    """Trips are periods away from home with at least `min_nights` nights away.

    - Walk through the "away" sections (further than home_radius_km from home).
    - Two sections belong to the SAME trip unless the tracker was home at night_hour in between (a quick stop at
      home to fetch something does not split a holiday; a night at home does).
    - If the tracker is silent at night while away, the section simply stays open — no point from home arrives.
    Start/end get `margin_s` added on both sides so departure and return are included."""
    sections: list[dict] = []
    current = None
    for p in points:
        d = s.home_distance(p.lat, p.lon)
        if d > s.home_radius_km:
            if current is None:
                current = {"start": p.t, "end": p.t, "farthest": d, "dest": (p.lat, p.lon)}
            else:
                current["end"] = p.t
                if d > current["farthest"]:
                    current["farthest"], current["dest"] = d, (p.lat, p.lon)
        elif current is not None:
            sections.append(current)
            current = None
    if current is not None:
        sections.append(current)

    merged: list[dict] = []
    for sec in sections:
        if merged and not night_times(merged[-1]["end"], sec["start"], s):
            m = merged[-1]
            m["end"] = sec["end"]
            if sec["farthest"] > m["farthest"]:
                m["farthest"], m["dest"] = sec["farthest"], sec["dest"]
        else:
            merged.append(dict(sec))

    trips = []
    for m in merged:
        nights = len(night_times(m["start"], m["end"], s))
        if nights < s.min_nights or m["farthest"] < s.min_distance_km:
            continue
        start, end = m["start"] - margin_s, m["end"] + margin_s
        trips.append(
            Trip(
                start=start,
                end=end,
                distance_km=round(path_length_km(slice_by_time(points, start, end)), 1),
                farthest_km=round(m["farthest"], 1),
                nights=nights,
                destination=(round(m["dest"][0], 5), round(m["dest"][1], 5)),
            )
        )
    return trips


@dataclass
class Stay:
    arrival: float
    departure: float
    lat: float
    lon: float
    nights: int


def detect_stays(points: Sequence[Point], s: DetectionSettings) -> list[Stay]:
    """Stays are the places where nights were spent.

    For each night the location is the last point before night_hour (at most night_max_age_h old). Exception for
    trackers that only record while driving (dashcams): a longer silence still counts if the points before and after
    are less than 2 km apart — the vehicle was parked there. Consecutive nights within stay_merge_km form ONE stay.
    Arrival is searched backwards from the FIRST night's location, departure forwards from the LAST night's location
    — not from the centroid, which can lie between two campsites with no point near it. Day trips from the stay belong
    to the stay. Nights at home are not stays."""
    if not points:
        return []
    nights = []
    for instant in night_times(points[0].t, points[-1].t, s):
        i = index_before(points, instant)
        if i < 0:
            continue
        # A long silence only counts if the vehicle is at the same place afterwards (dashcam case, see docstring).
        too_old = instant - points[i].t > s.night_max_age_h * 3600
        if too_old and (i + 1 >= len(points) or point_distance_km(points[i], points[i + 1]) > 2):
            continue
        p = points[i]
        if s.is_home(p.lat, p.lon):
            continue
        nights.append((i, p.lat, p.lon))

    groups: list[list[tuple[int, float, float]]] = []
    for n in nights:
        if groups and distance_km(groups[-1][-1][1], groups[-1][-1][2], n[1], n[2]) <= s.stay_merge_km:
            groups[-1].append(n)
        else:
            groups.append([n])

    stays: list[Stay] = []
    for g in groups:
        lat = sum(n[1] for n in g) / len(g)
        lon = sum(n[2] for n in g) / len(g)
        a = g[0][0]
        while a > 0 and distance_km(g[0][1], g[0][2], points[a - 1].lat, points[a - 1].lon) <= s.stay_near_km:
            a -= 1
        b = g[-1][0]
        while (
            b + 1 < len(points)
            and distance_km(g[-1][1], g[-1][2], points[b + 1].lat, points[b + 1].lon) <= s.stay_near_km
        ):
            b += 1
        arrival = max(points[a].t, stays[-1].departure if stays else points[a].t)
        stays.append(
            Stay(
                arrival=arrival,
                departure=max(points[b].t, arrival),
                lat=round(lat, 5),
                lon=round(lon, 5),
                nights=len(g),
            )
        )
    return stays


@dataclass
class Drive:
    start: float
    end: float
    distance_km: float
    max_speed_kmh: float
    origin: tuple[float, float]
    destination: tuple[float, float]
    origin_is_home: bool
    destination_is_home: bool


def detect_drives(points: Sequence[Point], s: DetectionSettings) -> list[Drive]:
    """Every drive, including ones without an overnight stop.

    A point is "moving" if it reports > 5 km/h or lies > 50 m from the previous point. A stop is a pause of at least
    drive_pause_s between two moving points — including a gap without any points (tracker asleep). Drives shorter
    than drive_min_km are manoeuvring and dropped."""
    moving = [
        i for i, p in enumerate(points) if (p.speed_kmh or 0) > 5 or (i and point_distance_km(points[i - 1], p) > 0.05)
    ]
    groups: list[list[int]] = []
    for i in moving:
        if groups and points[i].t - points[groups[-1][-1]].t < s.drive_pause_s:
            groups[-1].append(i)
        else:
            groups.append([i])
    drives = []
    for g in groups:
        a, b = max(g[0] - 1, 0), g[-1]  # start at the standing point before the first movement
        part = points[a : b + 1]
        length = path_length_km(part)
        if length < s.drive_min_km:
            continue
        o, d = points[a], points[b]
        drives.append(
            Drive(
                start=o.t,
                end=d.t,
                distance_km=round(length, 1),
                max_speed_kmh=round(max((x.speed_kmh or 0) for x in part)),
                origin=(round(o.lat, 5), round(o.lon, 5)),
                destination=(round(d.lat, 5), round(d.lon, 5)),
                origin_is_home=s.is_home(o.lat, o.lon),
                destination_is_home=s.is_home(d.lat, d.lon),
            )
        )
    return drives
