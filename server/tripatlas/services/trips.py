"""(Re)compute the trip cache of a tracker from its positions."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import time
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.countries import country_code
from ..core.detection import DetectionSettings, detect_stays, detect_trips
from ..core.geo import iso_to_ts, slice_by_time
from ..core.photos import most_common_city, pick_cover
from ..db.models import Stay, Tracker, TrackerKind, Trip
from ..integrations.immich import ImmichError
from . import photos as photo_service
from . import settings
from .places import cached as cached_place
from .positions import load_points

log = logging.getLogger(__name__)


def day_key(ts: float, s: DetectionSettings) -> str:
    return datetime.fromtimestamp(ts, s.tz).strftime("%Y-%m-%d")


# Bikes: the home area is smaller (a ride starts at the front door) and a short ride is a ride.
BIKE_HOME_RADIUS_KM = 1.0
BIKE_MIN_DISTANCE_KM = 3.0


def recompute(db: Session, tracker: Tracker, now: float | None = None) -> int:
    """Replace the tracker's detected trips and stays. Returns the number of trips. Titles and notes live in
    `annotations` and survive this."""
    hh = settings.household(db)
    s = hh.detection()
    if s is None:
        return 0
    if tracker.kind == TrackerKind.bike:
        # A bike ride rarely includes a night away, and a ride round the village is already worth keeping: every
        # ride leaving the home area counts (a holiday with daily rides from the campsite stays ONE trip, because
        # the bike never comes home at night in between).
        s = dataclasses.replace(s, min_nights=0, home_radius_km=min(s.home_radius_km, BIKE_HOME_RADIUS_KM),
                                min_distance_km=BIKE_MIN_DISTANCE_KM)
    now = now or time.time()
    start = iso_to_ts(hh.history_start) if hh.history_start else None
    points = load_points(db, tracker.id, start=start)
    found = detect_trips(points, s)

    immich = None
    with contextlib.suppress(ImmichError):  # no Immich: trips without photos
        immich = photo_service.client_for(db, None)

    rows: list[Trip] = []
    for i, tr in enumerate(found):
        ongoing = (
            i == len(found) - 1 and tr.end > now - 2 * 3600 and points and not s.is_home(points[-1].lat, points[-1].lon)
        )
        end = now if ongoing else tr.end
        part = slice_by_time(points, tr.start, end)
        stays = detect_stays(part, s)
        placed = []
        if immich is not None:
            try:
                placed, _ = photo_service.tracker_photos(db, None, tracker, part, tr.start, end, s)
            except ImmichError as e:
                log.warning("Photos for %s unavailable: %s", tracker.name, e)
        trip = Trip(
            tracker_id=tracker.id,
            day_key=day_key(tr.start, s),
            start=tr.start,
            end=end,
            ongoing=ongoing,
            distance_km=tr.distance_km,
            farthest_km=tr.farthest_km,
            nights=tr.nights,
            dest_lat=tr.destination[0],
            dest_lon=tr.destination[1],
            photo_count=len(placed),
        )
        if immich is not None and placed:
            trip.cover_asset = photo_service.choose_cover(immich, placed, tr.start, end)
        countries: list[str] = []
        for st in stays:
            near = [p for p in placed if st.arrival <= p.t <= st.departure]
            name = most_common_city(near, near=(st.lat, st.lon))
            place = cached_place(db, st.lat, st.lon, hh.default_locale)
            if not name and place:
                name = place.name
            stay = Stay(
                tracker_id=tracker.id,
                day_key=day_key(st.arrival, s),
                arrival=st.arrival,
                departure=st.departure,
                lat=st.lat,
                lon=st.lon,
                nights=st.nights,
                place_name=name,
                country_code=place.country_code if place else None,
                photo_count=len(near),
                cover_asset=pick_cover(near, (st.lat, st.lon)),
            )
            trip.stays.append(stay)
            if place and place.country_code and place.country_code not in countries:
                countries.append(place.country_code)
        for p in placed:
            code = None if p.estimated else country_code(p.country)
            if code and code not in countries:
                countries.append(code)
        names = [x.place_name for x in trip.stays if x.place_name]
        trip.places = [n for j, n in enumerate(names) if j == 0 or n != names[j - 1]]
        trip.countries = countries
        # Title: the place where the most nights were spent is what people call the trip ("Brittany", not the town
        # with the most photos, which was a day trip); without named stays the most photographed city.
        named = [x for x in trip.stays if x.place_name]
        main = max(named, key=lambda x: (x.nights, -x.arrival)) if named else None
        trip.auto_title = (main.place_name if main else None) or most_common_city(placed, exclude_home=s)
        rows.append(trip)
    if immich is not None:
        immich.close()

    # Keep each trip's id when it starts on the same day as before: links (/?trip=<id>) and bookmarks must survive
    # the recomputation that runs whenever new positions arrive.
    old_ids = dict(db.execute(select(Trip.day_key, Trip.id).where(Trip.tracker_id == tracker.id)).all())
    db.execute(delete(Trip).where(Trip.tracker_id == tracker.id))
    db.flush()
    for trip in rows:
        trip.id = old_ids.get(trip.day_key)
    db.add_all(rows)
    tracker.dirty = False
    db.commit()
    return len(rows)


def recompute_dirty(db: Session) -> dict[str, int]:
    out = {}
    for t in db.scalars(select(Tracker).where(Tracker.dirty.is_(True))):
        out[t.name] = recompute(db, t)
    return out
