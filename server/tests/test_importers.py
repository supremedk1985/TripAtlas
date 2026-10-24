import json

from tripatlas.core.countries import country_code
from tripatlas.importers import detect_format
from tripatlas.importers.geojson import parse_geojson
from tripatlas.importers.google import parse_google
from tripatlas.importers.gpx import parse_gpx
from tripatlas.integrations.traccar import points_from_traccar

GPX = b"""<?xml version="1.0"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
 <trk><trkseg>
  <trkpt lat="51.0" lon="8.0"><ele>100</ele><time>2026-07-01T10:00:00Z</time></trkpt>
  <trkpt lat="51.01" lon="8.0"><time>2026-07-01T10:01:00Z</time></trkpt>
  <trkpt lat="51.02" lon="8.0"></trkpt>
 </trkseg></trk>
</gpx>"""


def test_gpx():
    pts = parse_gpx(GPX)
    assert len(pts) == 2, "points without time are skipped"
    assert pts[0].altitude_m == 100 and 60 < pts[1].speed_kmh < 70


def test_google_records():
    data = json.dumps({"locations": [{"latitudeE7": 488500000, "longitudeE7": 23500000, "timestamp": "2019-05-01T10:00:00Z"},
                                     {"latitudeE7": 488501000, "longitudeE7": 23500000, "timestampMs": "1556704860000"}]}).encode()
    pts = parse_google(data)
    assert len(pts) == 2 and abs(pts[0].lat - 48.85) < 1e-6


def test_google_on_device_timeline():
    data = json.dumps({"semanticSegments": [
        {"startTime": "2024-06-01T10:00:00.000+02:00", "endTime": "2024-06-01T11:00:00.000+02:00",
         "timelinePath": [{"point": "48.85°, 2.35°", "time": "2024-06-01T10:05:00.000+02:00"}]},
        {"startTime": "2024-06-01T12:00:00.000+02:00", "endTime": "2024-06-01T18:00:00.000+02:00",
         "visit": {"topCandidate": {"placeLocation": {"latLng": "52.0°, 9.0°"}}}}],
        "rawSignals": [{"position": {"LatLng": "51.9°, 8.3°", "timestamp": "2024-06-01T10:30:00.000+02:00"}}]}).encode()
    pts = parse_google(data)
    assert len(pts) == 4
    assert [round(p.lat, 1) for p in pts] == [48.9, 51.9, 52.0, 52.0]


def test_google_ios_timeline():
    data = json.dumps([{"startTime": "2024-06-01T10:00:00.000+02:00", "endTime": "2024-06-01T11:00:00.000+02:00",
                        "timelinePath": [{"point": "geo:48.85,2.35", "durationMinutesOffsetFromStartTime": "5"}]}]).encode()
    pts = parse_google(data)
    assert len(pts) == 1 and pts[0].lon == 2.35


def test_geojson_and_detection():
    data = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [2.35, 48.85, 70]}, "properties": {"timestamp": 1700000000}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [2.36, 48.85]}, "properties": {"time": "2023-11-14T22:14:00Z"}},
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": []}, "properties": {}}]}).encode()
    pts = parse_geojson(data)
    assert len(pts) == 2 and pts[0].altitude_m == 70
    assert detect_format("x.json", data) == "geojson"
    assert detect_format("Records.json", b'{"locations": []}') == "google"
    assert detect_format("track.GPX", b"") == "gpx"
    assert detect_format("photo.jpg", b"") is None


def test_traccar_conversion():
    pts = points_from_traccar([
        {"fixTime": "2026-10-16T08:01:00.000+00:00", "latitude": 1, "longitude": 2, "speed": 10, "altitude": 5},
        {"fixTime": "2026-10-16T08:00:00.000+00:00", "latitude": 1, "longitude": 2, "speed": 0, "valid": False},
        {"fixTime": "2026-10-16T07:59:00.000+00:00", "latitude": 1, "longitude": 2, "speed": 0}])
    assert len(pts) == 2 and pts[0].t < pts[1].t and pts[1].speed_kmh == 18.5


def test_country_codes():
    assert country_code("The Netherlands") == "NL"
    assert country_code("Niederlande") == "NL"
    assert country_code("Deutschland") == country_code("Germany") == "DE"
    assert country_code("Österreich") == "AT"
    assert country_code("fr") == "FR"
    assert country_code("Atlantis") is None
