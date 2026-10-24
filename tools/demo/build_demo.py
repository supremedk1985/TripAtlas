#!/usr/bin/env python3
"""Build the demo data set: a made-up family ("Familie Beispiel") with a camper van and a car, five trips, a flight
and ~50 public-domain photos with GPS positions.

    python3 tools/demo/build_demo.py          # needs internet once: OSRM (routes) and Openverse (photos)

Writes tools/demo/data/ (positions per tracker, photo metadata, credits) and tools/demo/photos/ (JPEGs with EXIF).
Routes are real roads from the public OSRM demo server; photos are CC0 / public domain from Openverse — see
data/CREDITS.md. Nothing here belongs to a real family. Requires Pillow."""

from __future__ import annotations

import io
import json
import math
import random
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PHOTOS = HERE / "photos"
TZ = ZoneInfo("Europe/Berlin")
UA = "TripAtlas demo builder (https://github.com/supremedk1985/tripatlas)"
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=TZ)
random.seed(7)

HOME = ("Kassel", 51.3155, 9.4892)

# Places: name, lat, lon, country, photo search, number of photos
P = {
    "reims": ("Reims", 49.2536, 4.0341, "France", "reims cathedral|reims france", 2),
    "msm": ("Le Mont-Saint-Michel", 48.6150, -1.5100, "France", "mont saint michel|mont-saint-michel", 4),
    "camaret": ("Camaret-sur-Mer", 48.2780, -4.5960, "France", "brittany coast|finistere coast|brittany cliffs sea", 4),
    "carnac": ("Carnac", 47.5840, -3.0780, "France", "carnac stones|megaliths brittany|brittany beach", 4),
    "saumur": ("Saumur", 47.2580, -0.0760, "France", "saumur|loire castle", 2),
    "metz": ("Metz", 49.1190, 6.1757, "France", "metz|metz cathedral", 1),
    "innsbruck": ("Innsbruck", 47.2654, 11.3928, "Austria", "innsbruck|tyrol alps|austrian alps", 2),
    "lazise": ("Lazise", 45.5050, 10.7330, "Italy", "lake garda|lago di garda|garda lake", 5),
    "callantsoog": ("Callantsoog", 52.8390, 4.6970, "The Netherlands",
                    "north sea beach|netherlands beach|dunes beach", 3),
    "wernigerode": ("Wernigerode", 51.8350, 10.7850, "Germany", "wernigerode|harz mountains|harz germany", 3),
    "hamburg": ("Hamburg", 53.5440, 9.9660, "Germany", "hamburg harbour|hamburg port|hamburg", 3),
    "fra": ("Frankfurt am Main", 50.0500, 8.5700, "Germany", "airport terminal|airport airplane", 1),
    "palma": ("Palma", 39.5670, 2.6480, "Spain", "palma de mallorca|palma cathedral", 2),
    "mallorca": ("Alcúdia", 39.8380, 3.1200, "Spain", "mallorca beach|majorca beach|balearic beach", 3),
}

# Trips: tracker, then a list of (place key, nights) — 0 nights = a stop on the way
TRIPS = [
    ("van", datetime(2025, 8, 2, 8, 0, tzinfo=TZ),
     [("reims", 1), ("msm", 2), ("camaret", 3), ("carnac", 3), ("saumur", 1), ("metz", 1)]),
    ("van", datetime(2026, 3, 7, 9, 0, tzinfo=TZ), [("wernigerode", 1)]),
    ("van", datetime(2026, 4, 1, 8, 0, tzinfo=TZ), [("innsbruck", 1), ("lazise", 5)]),
    ("van", datetime(2026, 5, 14, 9, 0, tzinfo=TZ), [("callantsoog", 3)]),
    ("car", datetime(2026, 6, 20, 9, 30, tzinfo=TZ), [("hamburg", 1)]),
]
# Holiday by plane (no tracker): ground photo at the airport, photos from the window, a week on Mallorca
FLIGHT_DAY = datetime(2025, 10, 18, tzinfo=TZ)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def route(a: tuple[float, float], b: tuple[float, float], cache: dict) -> dict:
    key = f"{a[0]:.4f},{a[1]:.4f}->{b[0]:.4f},{b[1]:.4f}"
    if key not in cache:
        url = (f"https://router.project-osrm.org/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
               "?overview=full&geometries=geojson")
        r = get_json(url)["routes"][0]
        cache[key] = {"coords": [[round(c[1], 5), round(c[0], 5)] for c in r["geometry"]["coordinates"]],
                      "duration": r["duration"]}
        time.sleep(1.2)  # be gentle with the public demo server
    return cache[key]


def km(a, b) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def drive(points: list, start: datetime, r: dict, every_km: float = 2.0) -> datetime:
    """Positions along a route, roughly every `every_km`, with the time OSRM expects plus 20 % (breaks)."""
    coords = r["coords"]
    total = sum(km(a, b) for a, b in pairwise(coords)) or 1
    seconds = r["duration"] * 1.2
    done, last_emit = 0.0, -every_km
    for a, b in pairwise(coords):
        done += km(a, b)
        if done - last_emit >= every_km:
            t = start + timedelta(seconds=seconds * done / total)
            points.append([t.timestamp(), b[0], b[1], round(total / (seconds / 3600) * random.uniform(0.85, 1.1), 1)])
            last_emit = done
    return start + timedelta(seconds=seconds)


def parked(points: list, place: tuple[float, float], start: datetime, end: datetime) -> None:
    """A parked tracker reports rarely: on arrival, morning and evening."""
    points.append([start.timestamp(), place[0], place[1], 0])
    day = start.replace(hour=8, minute=30) + timedelta(days=1)
    while day < end:
        for h in (8, 21):
            t = day.replace(hour=h, minute=random.randint(0, 50))
            if start < t < end:
                jitter_lat, jitter_lon = random.uniform(-2e-4, 2e-4), random.uniform(-2e-4, 2e-4)
                points.append([t.timestamp(), place[0] + jitter_lat, place[1] + jitter_lon, 0])
        day += timedelta(days=1)


def openverse(queries: str, n: int, used: set) -> list[dict]:
    """Up to n CC0/public-domain landscape photos; `queries` are alternatives separated by "|"."""
    out = []
    for query in queries.split("|"):
        url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
            {"q": query, "license": "cc0,pdm", "page_size": 20, "aspect_ratio": "wide", "mature": "false"})
        for r in get_json(url).get("results", []):
            if r["url"] in used or (r.get("width") or 0) < 900:
                continue
            out.append(r)
            used.add(r["url"])
            if len(out) == n:
                return out
        time.sleep(1.0)
    return out


def save_photo(raw: bytes, path: Path, when: datetime, lat: float, lon: float, alt: float) -> tuple[int, int]:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((1600, 1600))
    exif = img.getexif()
    exif[0x010F] = "Demo"            # Make
    exif[0x0110] = "Phone"           # Model
    exif[0x0132] = when.strftime("%Y:%m:%d %H:%M:%S")
    sub = exif.get_ifd(0x8769)
    sub[0x9003] = when.strftime("%Y:%m:%d %H:%M:%S")   # DateTimeOriginal

    def dms(v: float):
        v = abs(v)
        d = int(v)
        m = int((v - d) * 60)
        s = (v - d - m / 60) * 3600
        return (float(d), float(m), round(s, 2))
    gps = exif.get_ifd(0x8825)
    gps[1] = "N" if lat >= 0 else "S"
    gps[2] = dms(lat)
    gps[3] = "E" if lon >= 0 else "W"
    gps[4] = dms(lon)
    gps[5] = 0
    gps[6] = round(float(alt), 1)
    img.save(path, "JPEG", quality=86, exif=exif)
    return img.size


def write_import_sample(cache: dict, home: tuple[float, float]) -> None:
    """A GPX file for the import part of the guide: a weekend in the Sauerland that no tracker recorded."""
    winterberg = (51.1940, 8.5330)
    pts: list = []
    t = drive(pts, datetime(2025, 6, 14, 9, 0, tzinfo=TZ), route(home, winterberg, cache))
    parked(pts, winterberg, t, datetime(2025, 6, 15, 15, 0, tzinfo=TZ))
    drive(pts, datetime(2025, 6, 15, 15, 0, tzinfo=TZ), route(winterberg, home, cache))
    rows = "\n".join(
        f'   <trkpt lat="{p[1]}" lon="{p[2]}">'
        f'<time>{datetime.fromtimestamp(p[0], UTC):%Y-%m-%dT%H:%M:%SZ}</time></trkpt>'
        for p in sorted(pts))
    (DATA / "sauerland-weekend.gpx").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="TripAtlas demo" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n <trk><name>Sauerland weekend</name><trkseg>\n'
        + rows + "\n </trkseg></trk>\n</gpx>\n")


def main() -> None:
    DATA.mkdir(exist_ok=True)
    PHOTOS.mkdir(exist_ok=True)
    cache_file = DATA / "routes-cache.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    tracks: dict[str, list] = {"van": [], "car": []}
    photos: list[dict] = []
    credits: list[str] = []
    used: set = set()
    home = (HOME[1], HOME[2])
    shots: list[tuple[str, datetime, tuple[float, float], float]] = []   # (place key, time, position, altitude)

    for tracker, start, legs in TRIPS:
        pts = tracks[tracker]
        here, t = home, start
        for key, nights in legs:
            _name, lat, lon, *_ = P[key]
            r = route(here, (lat, lon), cache)
            arrive = drive(pts, t, r)
            depart = (arrive + timedelta(days=nights)).replace(hour=9, minute=random.randint(0, 40))
            parked(pts, (lat, lon), arrive, depart)
            for d in range(max(nights, 1)):
                day = (arrive + timedelta(days=d)).replace(hour=0, minute=0)
                hours = (random.randint(10, 12), random.randint(14, 18))   # two photos a day …
                if d == 0:                                                # … on the day of arrival only after arriving
                    hours = tuple(min(arrive.hour + h, 21) for h in (1, 3))
                for hour in hours:
                    shots.append((key, day.replace(hour=hour, minute=random.randint(0, 59)), (lat, lon), 20.0))
            here, t = (lat, lon), depart
        r = route(here, home, cache)
        drive(pts, t, r)
    cache_file.write_text(json.dumps(cache))

    # Home: parked between trips, morning and evening, up to "now" (so the home suggestion has nights to count)
    for pts in tracks.values():
        pts.sort()
        day = datetime(2025, 7, 1, tzinfo=TZ)
        busy = [(pts[i][0], pts[i + 1][0]) for i in range(len(pts) - 1) if pts[i + 1][0] - pts[i][0] < 26 * 3600]
        while day < NOW:
            for h in (7, 20):
                ts = day.replace(hour=h).timestamp()
                if not any(a - 3600 <= ts <= b + 3600 for a, b in busy):
                    pts.append([ts, home[0] + random.uniform(-1e-4, 1e-4), home[1] + random.uniform(-1e-4, 1e-4), 0])
            day += timedelta(days=1)
        pts.sort()

    # The flight: airport (ground), climb, cruise over France and the Mediterranean, then Mallorca
    fd = FLIGHT_DAY
    shots.append(("fra", fd.replace(hour=8, minute=40), (50.0500, 8.5700), 110.0))
    for minute, pos, alt in ((9 * 60 + 25, (49.80, 8.35), 3100.0), (10 * 60 + 5, (46.60, 5.60), 11280.0),
                             (10 * 60 + 40, (43.40, 3.90), 11300.0), (11 * 60 + 15, (40.30, 2.90), 6200.0)):
        shots.append(("plane", fd.replace(hour=minute // 60, minute=minute % 60), pos, alt))
    for d, key in ((0, "palma"), (2, "mallorca"), (3, "mallorca"), (5, "mallorca"), (6, "palma")):
        lat, lon = P[key][1], P[key][2]
        shots.append((key, (fd + timedelta(days=d)).replace(hour=13 + d % 4, minute=(10 * d) % 60), (lat, lon), 30.0))

    # Fetch photos per place, as many as shots need
    wanted: dict[str, int] = {}
    for key, *_ in shots:
        wanted[key] = wanted.get(key, 0) + 1
    # Hand-picked photos (data/curated.json: place → list of Openverse results) win over a fresh search: automatic
    # results for a place name include war photos, football players and scanned documents.
    curated_file = DATA / "curated.json"
    curated = json.loads(curated_file.read_text()) if curated_file.exists() else {}
    pool: dict[str, list[dict]] = {}
    for key, n in wanted.items():
        if curated.get(key):
            pool[key] = list(curated[key])
        else:
            query = "airplane window clouds" if key == "plane" else P[key][4]
            pool[key] = openverse(query, n + 1, used)
        print(f"{key}: {len(pool[key])} candidates for {n} photos")

    for key, when, pos, alt in shots:
        if not pool.get(key):
            continue
        src = pool[key].pop(0)
        try:
            req = urllib.request.Request(src["url"], headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:  # skip unreachable images
            print("skip", src["url"], e)
            continue
        pid = str(uuid.uuid5(uuid.NAMESPACE_URL, src["url"]))
        lat = pos[0] + (random.uniform(-0.01, 0.01) if alt < 1000 else 0)
        lon = pos[1] + (random.uniform(-0.01, 0.01) if alt < 1000 else 0)
        w, h = save_photo(raw, PHOTOS / f"{pid}.jpg", when, lat, lon, alt)
        place = P.get(key)
        first_of_place = key in ("msm", "lazise") and not any(p["city"] == place[0] for p in photos)
        photos.append({"id": pid, "file": f"{pid}.jpg", "taken": when.isoformat(),
                       "lat": round(lat, 6), "lon": round(lon, 6),
                       "city": None if key == "plane" else place[0], "country": None if key == "plane" else place[3],
                       "width": w, "height": h, "favorite": first_of_place})
        link = src.get("foreign_landing_url") or src.get("landing") or src["url"]
        # credits show names, never e-mail addresses (some creators enter theirs as the name)
        creator = re.sub(r"\S+@\S+\.\w+", "", src.get("creator") or "").strip() or "unknown"
        credits.append(f"| {pid[:8]} | {src.get('title') or ''} | {creator} "
                       f"| {src['license'].upper()} | {link} |")
        time.sleep(0.3)

    write_import_sample(cache, home)
    cache_file.write_text(json.dumps(cache))
    rounded = {k: [[round(p[0]), p[1], p[2], p[3]] for p in v] for k, v in tracks.items()}
    (DATA / "positions.json").write_text(json.dumps(rounded))
    (DATA / "photos.json").write_text(json.dumps(photos, indent=0))
    (DATA / "CREDITS.md").write_text(
        "# Demo photo credits\n\nAll demo photos are CC0 or public domain (via [Openverse](https://openverse.org)).\n\n"
        "| id | title | creator | license | source |\n|---|---|---|---|---|\n" + "\n".join(credits) + "\n")
    print(f"{sum(len(v) for v in tracks.values())} positions, {len(photos)} photos")


if __name__ == "__main__":
    main()
