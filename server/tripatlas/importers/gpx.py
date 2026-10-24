"""GPX 1.0/1.1. Read as a stream: an export of every ride a bike app ever recorded is easily a few hundred MB, and a
parser that builds the whole document in memory would not survive it."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import BinaryIO

from ..core.geo import Point, distance_km

_POINTS = {"trkpt", "rtept", "wpt"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element, name: str) -> str | None:
    for c in el:
        if _local(c.tag) == name:
            return (c.text or "").strip() or None
    return None


def _time(value: str | None) -> float | None:
    if not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).timestamp()


def iter_gpx(src: BinaryIO) -> Iterator[Point]:
    """Points of tracks, routes and waypoints that carry a time, in file order. Without time a point cannot be
    placed on a timeline and is skipped. Speed: from <speed> (GPX 1.0) or from the previous point of the segment."""
    prev: tuple[float, float, float] | None = None
    for event, el in ET.iterparse(src, events=("start", "end")):
        tag = _local(el.tag)
        if event == "start":
            if tag in ("trkseg", "rte"):
                prev = None
            continue
        if tag in _POINTS:
            t = _time(_child(el, "time"))
            if t is not None:
                lat, lon = float(el.get("lat", "nan")), float(el.get("lon", "nan"))
                ele = _child(el, "ele")
                speed = _child(el, "speed")
                kmh = float(speed) * 3.6 if speed else 0.0
                if not speed and prev is not None and tag != "wpt" and t > prev[0]:
                    kmh = distance_km(prev[1], prev[2], lat, lon) / ((t - prev[0]) / 3600)
                if lat == lat and lon == lon:   # not NaN
                    yield Point(t, lat, lon, round(kmh, 1), round(float(ele)) if ele else 0)
                    if tag != "wpt":
                        prev = (t, lat, lon)
            el.clear()
        elif tag in ("trkseg", "trk", "rte"):
            el.clear()


def parse_gpx(data: bytes) -> list[Point]:
    return sorted(iter_gpx(io.BytesIO(data)), key=lambda p: p.t)
