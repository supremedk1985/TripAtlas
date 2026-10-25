"""The vertical timeline of a trip: departure, alternating drives and stays, return. Pure."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from .detection import DetectionSettings, Stay
from .geo import Point, path_length_km, slice_by_time
from .photos import Photo, most_common_city, pick_cover


@dataclass
class TimelineEntry:
    kind: Literal["drive", "stay", "ongoing"]
    start: float
    end: float
    distance_km: float
    photo_count: int
    cover_photo: str | None
    place: str | None
    lat: float | None = None
    lon: float | None = None
    nights: int = 0
    extra: dict = field(default_factory=dict)


def build_timeline(
    points: Sequence[Point], stays: Sequence[Stay], photos: Sequence[Photo], s: DetectionSettings
) -> list[TimelineEntry]:
    if not points:
        return []

    def between(a: float, b: float) -> list[Photo]:
        return [p for p in photos if a <= p.t <= b]

    def km(a: float, b: float) -> float:
        return round(path_length_km(slice_by_time(points, a, b), s.max_gap_s), 1)

    out: list[TimelineEntry] = []
    t = points[0].t
    for st in stays:
        if st.arrival > t:
            ph = between(t, st.arrival)
            out.append(
                TimelineEntry("drive", t, st.arrival, km(t, st.arrival), len(ph), pick_cover(ph), most_common_city(ph))
            )
        ph = between(st.arrival, st.departure)
        where = (st.lat, st.lon)
        out.append(
            TimelineEntry(
                "stay",
                st.arrival,
                st.departure,
                km(st.arrival, st.departure),
                len(ph),
                pick_cover(ph, where),
                most_common_city(ph, near=where),
                st.lat,
                st.lon,
                st.nights,
            )
        )
        t = st.departure
    end = points[-1].t
    if end > t:
        ph = between(t, end)
        back_home = s.is_home(points[-1].lat, points[-1].lon)
        out.append(
            TimelineEntry(
                "drive" if back_home else "ongoing", t, end, km(t, end), len(ph), pick_cover(ph), most_common_city(ph)
            )
        )
    return out
