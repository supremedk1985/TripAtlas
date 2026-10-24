"""GeoJSON FeatureCollections of Point features with a time property (as exported by Dawarich, OwnTracks
recorders and many apps). Accepted time properties: timestamp (seconds or ms), time, datetime (ISO)."""
from __future__ import annotations

import json

from ..core.geo import Point, iso_to_ts

TIME_KEYS = ("timestamp", "time", "datetime", "date", "tst")


def _time(props: dict) -> float | None:
    for k in TIME_KEYS:
        v = props.get(k)
        if v is None:
            continue
        try:
            if isinstance(v, (int, float)):
                return v / 1000 if v > 1e11 else float(v)
            return iso_to_ts(str(v))
        except ValueError:
            continue
    return None


def parse_geojson(data: bytes) -> list[Point]:
    doc = json.loads(data)
    out = []
    for f in doc.get("features", []):
        geom = f.get("geometry") or {}
        props = f.get("properties") or {}
        if geom.get("type") != "Point":
            continue
        t = _time(props)
        coords = geom.get("coordinates") or []
        if t is None or len(coords) < 2:
            continue
        speed = props.get("speed") or props.get("velocity") or 0
        out.append(Point(t, coords[1], coords[0], float(speed or 0), float(coords[2]) if len(coords) > 2 else 0.0))
    out.sort(key=lambda x: x.t)
    return out
