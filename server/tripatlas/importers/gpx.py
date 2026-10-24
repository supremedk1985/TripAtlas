from __future__ import annotations

import gpxpy

from ..core.geo import Point


def parse_gpx(data: bytes) -> list[Point]:
    """Track points (and route/waypoints with a time) from a GPX file. Points without a timestamp are skipped —
    without time they cannot be placed on a timeline."""
    gpx = gpxpy.parse(data.decode("utf-8", errors="replace"))
    out = []
    for track in gpx.tracks:
        for seg in track.segments:
            prev = None
            for p in seg.points:
                if p.time is None:
                    continue
                speed = p.speed * 3.6 if p.speed is not None else (
                    p.speed_between(prev) * 3.6 if prev is not None and p.speed_between(prev) else 0.0)
                out.append(Point(p.time.timestamp(), p.latitude, p.longitude, round(speed or 0, 1),
                                 round(p.elevation or 0)))
                prev = p
    for p in gpx.waypoints:
        if p.time is not None:
            out.append(Point(p.time.timestamp(), p.latitude, p.longitude, 0.0, round(p.elevation or 0)))
    out.sort(key=lambda x: x.t)
    return out
