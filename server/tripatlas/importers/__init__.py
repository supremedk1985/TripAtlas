"""File importers. Each takes the raw file bytes and returns time-sorted Points; detection does the rest.

To add a format: write `parse_<format>(data: bytes) -> list[Point]`, register it in IMPORTERS, add a test with a small
sample file in tests/data/."""
from __future__ import annotations

from collections.abc import Callable

from ..core.geo import Point
from .geojson import parse_geojson
from .google import parse_google
from .gpx import parse_gpx

IMPORTERS: dict[str, Callable[[bytes], list[Point]]] = {
    "gpx": parse_gpx,
    "google": parse_google,
    "geojson": parse_geojson,
}


def detect_format(filename: str, data: bytes) -> str | None:
    name = filename.lower()
    if name.endswith(".gpx"):
        return "gpx"
    if name.endswith((".geojson",)):
        return "geojson"
    if name.endswith(".json"):
        head = data[:4096].lstrip()
        if b'"type"' in head and b"FeatureCollection" in head:
            return "geojson"
        return "google"
    return None
