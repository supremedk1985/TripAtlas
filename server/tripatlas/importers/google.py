"""Google location history. Two formats exist:

- Takeout "Records.json" (until 2024): {"locations": [{"latitudeE7", "longitudeE7", "timestamp" | "timestampMs", ...}]}
- On-device Timeline export (since 2024, "Timeline.json" / "location-history.json"): either
  {"semanticSegments": [{"timelinePath": [{"point": "48.85°, 2.35°", "time": ...}], "visit": {...}}, ...],
   "rawSignals": [{"position": {"LatLng": "48.85°, 2.35°", "timestamp": ...}}]}
  or (iOS) a list of segments with "visit"/"activity"/"timelinePath" and "geo:48.85,2.35" strings.
"""
from __future__ import annotations

import json
import re

from ..core.geo import Point, iso_to_ts

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _latlng(text: str) -> tuple[float, float] | None:
    nums = _NUM.findall(text or "")
    if len(nums) < 2:
        return None
    return float(nums[0]), float(nums[1])


def _ts(value) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            return int(value) / 1000
        return iso_to_ts(str(value))
    except ValueError:
        return None


def parse_google(data: bytes) -> list[Point]:
    doc = json.loads(data)
    out: list[Point] = []

    def add(t, ll, speed=0.0, alt=0.0):
        if t is not None and ll is not None:
            out.append(Point(t, ll[0], ll[1], speed, alt))

    if isinstance(doc, dict) and "locations" in doc:
        for loc in doc["locations"]:
            if "latitudeE7" not in loc:
                continue
            add(_ts(loc.get("timestamp") or loc.get("timestampMs")), (loc["latitudeE7"] / 1e7, loc["longitudeE7"] / 1e7),
                (loc.get("velocity") or 0) * 3.6, loc.get("altitude") or 0)
    segments = doc.get("semanticSegments", []) if isinstance(doc, dict) else doc if isinstance(doc, list) else []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        for p in seg.get("timelinePath", []) or []:
            if "time" in p:   # Android: absolute time per point
                add(_ts(p["time"]), _latlng(p.get("point", "")))
            elif "durationMinutesOffsetFromStartTime" in p:   # iOS: minutes after the segment start
                base = _ts(seg.get("startTime"))
                if base is not None:
                    add(base + int(p["durationMinutesOffsetFromStartTime"]) * 60, _latlng(p.get("point", "")))
        visit = seg.get("visit")
        if visit:
            cand = visit.get("topCandidate", {})
            ll = _latlng((cand.get("placeLocation") or {}).get("latLng", "") if isinstance(cand.get("placeLocation"), dict)
                         else cand.get("placeLocation", ""))
            for key in ("startTime", "endTime"):
                add(_ts(seg.get(key)), ll)
    if isinstance(doc, dict):
        for sig in doc.get("rawSignals", []):
            pos = sig.get("position")
            if pos:
                add(_ts(pos.get("timestamp")), _latlng(pos.get("LatLng", "")), (pos.get("speedMetersPerSecond") or 0) * 3.6,
                    pos.get("altitudeMeters") or 0)
    out.sort(key=lambda x: x.t)
    return out
