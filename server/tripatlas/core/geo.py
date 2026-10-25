"""Geometry and time helpers shared by all detectors. Pure functions, no I/O."""

from __future__ import annotations

import bisect
import itertools
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

EARTH_RADIUS_KM = 6371.0


class Point(NamedTuple):
    """One recorded position. `t` is a Unix timestamp in seconds (UTC)."""

    t: float
    lat: float
    lon: float
    speed_kmh: float = 0.0
    altitude_m: float = 0.0


def distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle distance (haversine)."""
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def point_distance_km(a: Point, b: Point) -> float:
    return distance_km(a.lat, a.lon, b.lat, b.lon)


# Consecutive points further apart than this count only if the implied speed is plausible on the ground: sparse
# recordings (a point every 10–15 minutes, e.g. Google location history) still add up, GPS jumps do not.
MAX_SEGMENT_KM = 5.0
MAX_GROUND_KMH = 200.0


def path_length_km(points: Sequence[Point], max_gap_s: float | None = None) -> float:
    """Length of a track, skipping implausible jumps (see MAX_SEGMENT_KM, MAX_GROUND_KMH) and, if given, stretches
    without points longer than `max_gap_s`."""
    total = 0.0
    for a, b in itertools.pairwise(points):
        if max_gap_s is not None and b.t - a.t > max_gap_s:
            continue
        d = point_distance_km(a, b)
        hours = (b.t - a.t) / 3600
        if d < MAX_SEGMENT_KM or (hours > 0 and d / hours <= MAX_GROUND_KMH):
            total += d
    return total


def drop_spikes(points: Sequence[Point]) -> list[Point]:
    """Leaves out single points that jump far away and straight back — a corrupt GPS fix (e.g. a dashcam that wrote
    8.0 instead of 0812.3 as longitude put one point of a drive near London). A point goes when it is implausibly far
    from both neighbours (see MAX_SEGMENT_KM, MAX_GROUND_KMH) while the neighbours are close to each other."""
    if len(points) < 3:
        return list(points)

    def jump(a: Point, b: Point) -> float:
        d = point_distance_km(a, b)
        hours = abs(b.t - a.t) / 3600
        return d if d > MAX_SEGMENT_KM and (hours == 0 or d / hours > MAX_GROUND_KMH) else 0.0

    out = [points[0]]
    for i in range(1, len(points) - 1):
        prev, p, nxt = out[-1], points[i], points[i + 1]
        there, back = jump(prev, p), jump(p, nxt)
        if there and back and point_distance_km(prev, nxt) < min(there, back) / 2:
            continue
        out.append(p)
    out.append(points[-1])
    return out


def thin_out(points: Sequence[Point], min_meters: float = 15, max_seconds: float = 900) -> list[Point]:
    """Drop points that add nothing: keep a point only if it is more than `min_meters` away from the last kept one
    or more than `max_seconds` later. A parked tracker reporting every few minutes would otherwise dominate the
    payload. First and last point are always kept."""
    if len(points) <= 2:
        return list(points)
    kept = [points[0]]
    for p in points[1:-1]:
        q = kept[-1]
        if point_distance_km(q, p) * 1000 >= min_meters or p.t - q.t >= max_seconds:
            kept.append(p)
    kept.append(points[-1])
    return kept


def slice_by_time(points: Sequence[Point], start: float, end: float) -> list[Point]:
    """Points with start <= t <= end. `points` must be sorted by time."""
    times = [p.t for p in points]
    return list(points[bisect.bisect_left(times, start) : bisect.bisect_right(times, end)])


def index_before(points: Sequence[Point], t: float) -> int:
    """Index of the last point with p.t <= t, or -1."""
    lo, hi = 0, len(points)
    while lo < hi:
        mid = (lo + hi) // 2
        if points[mid].t <= t:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1


def position_at(points: Sequence[Point], t: float, window_s: float = 1800) -> tuple[float, float] | None:
    """Interpolated position at time `t`, or None if the nearest recorded point is more than `window_s` away
    (an estimate across a long gap is worthless)."""
    if not points:
        return None
    if t <= points[0].t:
        return (points[0].lat, points[0].lon) if points[0].t - t <= window_s else None
    if t >= points[-1].t:
        return (points[-1].lat, points[-1].lon) if t - points[-1].t <= window_s else None
    i = index_before(points, t)
    a, b = points[i], points[i + 1]
    if min(t - a.t, b.t - t) > window_s:
        return None
    f = (t - a.t) / (b.t - a.t) if b.t > a.t else 0.0
    return (a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f)


def location_at(points: Sequence[Point], t: float) -> tuple[float, float] | None:
    """Where was the tracker at time `t`? Like `position_at` with a generous window, plus one rule: if the tracker
    went silent for a long time but the points before and after the gap are at the same place (< 2 km), it was
    parked there the whole time. Trackers often sleep while the ignition is off."""
    pos = position_at(points, t, window_s=6 * 3600)
    if pos is None and points and points[0].t <= t <= points[-1].t:
        i = index_before(points, t)
        a, b = points[i], points[min(i + 1, len(points) - 1)]
        if point_distance_km(a, b) <= 2:
            pos = (a.lat, a.lon)
    return pos


def iso_to_ts(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def ts_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
