"""The photo layer (all geotagged photos, independent of trackers), thumbnails, places and "where I've been" pins."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import __version__
from ..auth.deps import current_user, visible_trackers
from ..config import get_config
from ..core.countries import country_code
from ..core.geo import distance_km
from ..db.models import Annotation, Role, Stay, Trip, User
from ..db.session import get_db
from ..integrations.immich import ImmichError
from ..integrations.places import PlaceLookup
from ..services import flights as flight_service
from ..services import photos as photo_service
from ..services import settings
from ..services.places import cached as cached_place
from ..services.places import get_place, place_dict

router = APIRouter(tags=["photos"])

_ASSET_ID = re.compile(r"^[0-9a-f-]{36}$")


@router.get("/api/photos/markers")
def markers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Every geotagged photo the user can see in Immich: [[id, lat, lon], …] — compact, the map clusters them.
    Photos taken on board an aircraft are left out: their positions are places nobody visited."""
    in_flight = flight_service.airborne_ids(db)
    try:
        marks = photo_service.markers(db, user)
        return {
            "markers": [[m["id"], round(m["lat"], 5), round(m["lon"], 5)] for m in marks if m["id"] not in in_flight]
        }
    except ImmichError as e:
        return {"markers": [], "error": str(e)}


@router.get("/api/photos/{asset_id}/thumbnail")
def thumbnail(
    asset_id: str, size: str = "thumbnail", db: Session = Depends(get_db), user: User = Depends(current_user)
):
    if not _ASSET_ID.match(asset_id) or size not in ("thumbnail", "preview"):
        raise HTTPException(400, "Invalid request")
    try:
        with photo_service.client_for(db, user) as c:
            data, kind = c.thumbnail(asset_id, size)
    except ImmichError as e:
        raise HTTPException(404 if "404" in str(e) or "400" in str(e) else 502, str(e)) from e
    # Same id = same image, forever; private because it is the user's photo.
    return Response(data, media_type=kind, headers={"Cache-Control": "private, max-age=2592000, immutable"})


@router.get("/api/photos/{asset_id}/info")
def photo_info(asset_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Whether an asset is a video (the map markers do not say), when it was taken, how long it runs."""
    if not _ASSET_ID.match(asset_id):
        raise HTTPException(400, "Invalid request")
    with photo_service.client_for(db, user) as c:
        a = c.asset(asset_id)
    return {
        "id": asset_id,
        "is_video": a.get("type") == "VIDEO",
        "taken_at": a.get("localDateTime"),
        "duration": a.get("duration"),
    }


@router.get("/api/photos/{asset_id}/video")
def video(asset_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Stream a video from Immich, passing Range through so the player can seek."""
    if not _ASSET_ID.match(asset_id):
        raise HTTPException(400, "Invalid request")
    client = photo_service.client_for(db, user)
    try:
        upstream = client.open_video(asset_id, request.headers.get("range"))
    except ImmichError:
        client.close()
        raise

    def body():
        try:
            yield from upstream.iter_raw(256 * 1024)
        finally:
            upstream.close()
            client.close()

    headers = {
        k: upstream.headers[k] for k in ("content-range", "accept-ranges", "content-length") if k in upstream.headers
    }
    # Already compressed — and the gzip middleware must not touch it (it would break Content-Length/Range).
    headers["Content-Encoding"] = "identity"
    headers["Cache-Control"] = "private, max-age=86400"
    return StreamingResponse(
        body(),
        status_code=upstream.status_code,
        headers=headers,
        media_type=upstream.headers.get("content-type", "video/mp4"),
    )


@router.get("/api/places/search")
def place_search(q: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Find a place by name or address (OpenStreetMap) — used to set the home location."""
    q = q.strip()
    if len(q) < 3:
        return []
    with PlaceLookup(f"TripAtlas/{__version__} ({get_config().contact})") as lookup:
        return lookup.search(q[:200], user.locale)


@router.get("/api/places")
def place(lat: float, lon: float, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """What is this place? Name, country, encyclopedia summary (child-friendly text for children)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(400, "Invalid coordinates")
    hh = settings.household(db)
    kids = user.role == Role.child
    if not hh.place_info_enabled:
        return place_dict(cached_place(db, lat, lon, user.locale), kids)
    return place_dict(get_place(db, lat, lon, user.locale), kids)


@router.get("/api/visited/photos")
def visited_photos(
    lat: float, lon: float, city: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """The photos of one pin, for the viewer: same city as the pin, or within 2 km of it. Up to 500 ids."""
    try:
        marks = photo_service.markers(db, user)
    except ImmichError:
        return {"ids": []}
    in_flight = flight_service.airborne_ids(db)
    ids = [
        m["id"]
        for m in marks
        if m["id"] not in in_flight
        and ((city and m.get("city") == city) or distance_km(lat, lon, m["lat"], m["lon"]) <= 2)
    ]
    return {"ids": ids[:500]}


@router.get("/api/visited")
def visited(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Pins for every place the user has been: overnight stays of the visible trackers plus every city that appears
    in the user's geotagged photos (that also covers journeys without a tracker, e.g. by plane)."""
    pins: dict[str, dict] = {}

    tracker_ids = [t.id for t in visible_trackers(db, user)]
    if tracker_ids:
        q = select(Stay, Trip).join(Trip, Stay.trip_id == Trip.id).where(Stay.tracker_id.in_(tracker_ids))
        if not user.can_see_live:
            q = q.where(Trip.ongoing.is_(False))
        titles = {
            (a.tracker_id, a.day_key): a.title
            for a in db.scalars(
                select(Annotation).where(Annotation.kind == "stay", Annotation.tracker_id.in_(tracker_ids))
            )
        }
        for st, trip in db.execute(q):
            place = cached_place(db, st.lat, st.lon, user.locale)
            name = titles.get((st.tracker_id, st.day_key)) or st.place_name or (place.name if place else None)
            key = f"stay:{round(st.lat, 2)},{round(st.lon, 2)}"
            pin = pins.setdefault(
                key,
                {
                    "lat": st.lat,
                    "lon": st.lon,
                    "name": name,
                    "country": st.country_code or (place.country_code if place else None),
                    "nights": 0,
                    "photos": 0,
                    "first": st.arrival,
                    "trip_ids": [],
                    "kind": "stay",
                },
            )
            pin["nights"] += st.nights
            pin["first"] = min(pin["first"], st.arrival)
            if trip.id not in pin["trip_ids"]:
                pin["trip_ids"].append(trip.id)

    try:
        marks = photo_service.markers(db, user)
    except ImmichError:
        marks = []
    # Photos taken on board an aircraft carry positions of places nobody visited — they become flights instead.
    flight_data = flight_service.stored(db)
    in_flight = set(flight_data.get("airborne", {}))
    marks = [m for m in marks if m["id"] not in in_flight]
    groups: dict[tuple, list[dict]] = {}
    for m in marks:
        if m.get("city"):
            groups.setdefault((m["city"], m.get("country")), []).append(m)
    for (city, country), ms in groups.items():
        lat = sum(m["lat"] for m in ms) / len(ms)
        lon = sum(m["lon"] for m in ms) / len(ms)
        near = next(
            (
                p
                for p in pins.values()
                if p["kind"] == "stay" and abs(p["lat"] - lat) < 0.05 and abs(p["lon"] - lon) < 0.08
            ),
            None,
        )
        if near:
            near["photos"] += len(ms)
            near["name"] = near["name"] or city
            near["country"] = near["country"] or country_code(country)
            continue
        pins[f"city:{city}|{country}"] = {
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "name": city,
            "country": country_code(country),
            "nights": 0,
            "photos": len(ms),
            "first": None,
            "trip_ids": [],
            "kind": "photos",
            "cover_asset": ms[len(ms) // 2]["id"],
        }

    # Countries as ISO codes; the client shows localised names.
    countries: dict[str, dict] = {}
    for p in pins.values():
        if p["country"]:
            c = countries.setdefault(p["country"], {"country": p["country"], "places": 0, "photos": 0, "nights": 0})
            c["places"] += 1
            c["photos"] += p["photos"]
            c["nights"] += p["nights"]
    visible = {m["id"] for m in photo_service.markers(db, user)} if marks or in_flight else set()
    flights = []
    for f in flight_data.get("flights", []):
        ids = [i for i in f["photo_ids"] if i in visible]  # only flights with photos this user may see
        if ids:
            flights.append(
                {
                    **{
                        k: f[k]
                        for k in (
                            "start",
                            "end",
                            "max_altitude_m",
                            "origin",
                            "destination",
                            "origin_name",
                            "destination_name",
                            "path",
                        )
                    },
                    "photo_ids": ids,
                    "cover_asset": ids[len(ids) // 2],
                }
            )
    return {
        "pins": list(pins.values()),
        "countries": sorted(countries.values(), key=lambda c: -c["places"]),
        "flights": flights,
    }
