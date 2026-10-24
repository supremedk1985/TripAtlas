"""Tests for the pure detection rules. Each case comes from a real situation; the comment says which."""

import itertools
from datetime import datetime

import pytest

from tripatlas.core.detection import DetectionSettings, detect_drives, detect_stays, detect_trips
from tripatlas.core.geo import Point, position_at, thin_out
from tripatlas.core.photos import Photo, claimed_by, matches_tracker, most_common_city, pick_cover, place_photos
from tripatlas.core.timeline import build_timeline

HOME = (51.95, 8.0)  # any place; the scenarios are relative to it
FAR = (51.75, 10.0)  # ~120 km away
S = DetectionSettings(home_lat=HOME[0], home_lon=HOME[1], timezone="Europe/Berlin")


def ts(day, hour, minute=0, month=7):
    return datetime(2026, month, day, hour, minute, tzinfo=S.tz).timestamp()


def at(place, start, end, step=900, speed=0):
    return [Point(t, place[0], place[1], speed) for t in range(int(start), int(end), step)]


# --- trips ---------------------------------------------------------------------------------------------------------


def test_simple_trip():
    t0 = 1_760_000_000
    pts = [Point(t0 + i * 600, *HOME) for i in range(60)]
    pts += [Point(t0 + 36000 + i * 600, HOME[0] - 0.004 * i, HOME[1] + 0.05 * i, 60) for i in range(36)]
    pts += [Point(t0 + 57600 + i * 120, 51.75, 10.0) for i in range(1440)]
    pts += [Point(t0 + 230400 + i * 600, 51.75 + 0.004 * i, 10.0 - 0.05 * i, 60) for i in range(36)]
    pts += [Point(t0 + 252000 + i * 600, *HOME) for i in range(20)]
    trips = detect_trips(pts, S)
    assert len(trips) == 1
    assert 200 < trips[0].distance_km < 300
    assert trips[0].farthest_km > 100
    assert trips[0].nights >= 2 and abs(trips[0].destination[1] - 10.0) < 0.2


def test_shopping_is_not_a_trip():
    pts = [Point(1_760_000_000 + i * 600, HOME[0] + (0.06 if 3 <= i <= 12 else 0), HOME[1]) for i in range(20)]
    assert detect_trips(pts, S) == []


def test_day_trip_is_not_a_trip():
    pts = at(HOME, ts(1, 0), ts(1, 8)) + at(FAR, ts(1, 8), ts(1, 20)) + at(HOME, ts(1, 20), ts(2, 8))
    assert detect_trips(pts, S) == []


def test_night_at_home_splits_trips():
    pts = (
        at(FAR, ts(1, 9), ts(3, 12))
        + at(HOME, ts(3, 12), ts(5, 9))
        + at(FAR, ts(5, 9), ts(8, 12))
        + at(HOME, ts(8, 12), ts(8, 20))
    )
    assert [t.nights for t in detect_trips(pts, S)] == [2, 3]


def test_short_visit_home_during_the_day_keeps_one_trip():
    pts = (
        at(FAR, ts(1, 9), ts(3, 11))
        + at(HOME, ts(3, 11), ts(3, 14))
        + at(FAR, ts(3, 14), ts(5, 12))
        + at(HOME, ts(5, 12), ts(5, 20))
    )
    assert len(detect_trips(pts, S)) == 1


def test_silent_tracker_away_still_counts_the_night():
    pts = at(FAR, ts(10, 18), ts(10, 22)) + at(FAR, ts(11, 9), ts(11, 12)) + at(HOME, ts(11, 14), ts(11, 16))
    assert [t.nights for t in detect_trips(pts, S)] == [1]


# --- stays and timeline ------------------------------------------------------------------------------------------

A, B, EXCURSION = (51.75, 10.0), (50.4, 1.6), (51.80, 10.15)
JOURNEY = (
    at(HOME, ts(1, 6), ts(1, 9))
    + at((51.8, 9.0), ts(1, 10), ts(1, 11))
    + at(A, ts(1, 13), ts(2, 10))
    + at(EXCURSION, ts(2, 10), ts(2, 16))
    + at(A, ts(2, 16), ts(3, 9))
    + at((51.0, 6.0), ts(3, 11), ts(3, 13))
    + at(B, ts(3, 16), ts(4, 10))
    + at((51.0, 6.0), ts(4, 13), ts(4, 14))
    + at(HOME, ts(4, 18), ts(4, 22))
)


def test_stays_with_excursion():
    stays = detect_stays(JOURNEY, S)
    assert len(stays) == 2
    assert stays[0].nights == 2 and stays[0].arrival == ts(1, 13) and stays[0].departure >= ts(3, 8)
    assert stays[1].nights == 1 and abs(stays[1].lat - B[0]) < 0.01


def test_timeline():
    stays = detect_stays(JOURNEY, S)
    photos = [Photo("x", ts(2, 12), *EXCURSION, city="Riverton"), Photo("y", ts(3, 12), 51.0, 6.0, city="Aachen")]
    tl = build_timeline(JOURNEY, stays, photos, S)
    assert [e.kind for e in tl] == ["drive", "stay", "drive", "stay", "drive"]
    assert tl[1].photo_count == 1 and tl[1].place == "Riverton" and tl[1].cover_photo == "x"
    assert tl[2].photo_count == 1 and tl[2].place == "Aachen"
    assert all(a.end == b.start for a, b in itertools.pairwise(tl)), "timeline has no gaps"
    assert build_timeline(JOURNEY[:-16], stays, [], S)[-1].kind == "ongoing"


def test_dashcam_gap_at_same_place_counts_as_nights():
    # Dashcams only record while driving: three days without points at the same place are three nights there.
    pts = (
        at(HOME, ts(20, 8), ts(20, 9))
        + at(A, ts(20, 18), ts(20, 19))
        + at(A, ts(23, 10), ts(23, 11))
        + at(HOME, ts(23, 20), ts(23, 21))
    )
    stays = detect_stays(pts, S)
    assert len(stays) == 1 and stays[0].nights == 3


# --- drives ----------------------------------------------------------------------------------------------------


def test_drives_without_overnight():
    pts = (
        at(HOME, ts(12, 6), ts(12, 8))
        + [Point(ts(12, 8) + i * 60, HOME[0] + 0.01 * i, HOME[1], 60) for i in range(1, 21)]
        + at((HOME[0] + 0.2, HOME[1]), ts(12, 8, 21), ts(12, 11))
        + [Point(ts(12, 11) + i * 60, HOME[0] + 0.2 - 0.01 * i, HOME[1], 60) for i in range(1, 21)]
        + [Point(ts(12, 15), HOME[0], HOME[1] + 0.0003, 3)]
    )
    drives = detect_drives(pts, S)
    assert len(drives) == 2
    assert drives[0].origin_is_home and not drives[0].destination_is_home and drives[1].destination_is_home
    assert all(20 < d.distance_km < 24 for d in drives)


def test_gap_without_points_splits_drives():
    pts = [
        Point(0, 50.0, 8.0, 60),
        Point(60, 50.01, 8.0, 60),
        Point(3600, 50.01, 8.0, 0),
        Point(3660, 50.02, 8.0, 60),
        Point(3720, 50.03, 8.0, 60),
    ]
    assert len(detect_drives(pts, S)) == 2


# --- geometry -------------------------------------------------------------------------------------------------


def test_thin_out():
    pts = [Point(i * 120, 51.75, 10.0) for i in range(1440)] + [
        Point(172800 + i * 60, 51.75 + 0.01 * i, 10.0, 50) for i in range(10)
    ]
    thinned = thin_out(pts)
    assert len([p for p in thinned if p.lat == 51.75]) <= 200
    assert thinned[0] == pts[0] and thinned[-1] == pts[-1]


def test_position_at():
    a = [Point(0, 50.0, 8.0), Point(600, 50.0, 9.0)]
    assert position_at(a, 300)[1] == pytest.approx(8.5)
    assert position_at(a, 600 + 4000) is None
    gap = [Point(0, 50.0, 8.0), Point(20000, 50.0, 9.0)]
    assert position_at(gap, 10000) is None
    assert position_at(gap, 600) is not None


# --- photos -------------------------------------------------------------------------------------------------------


def test_photo_must_be_near_the_tracker():
    # A second car parked at home got every holiday photo before this rule existed.
    parked = [Point(0, 51.67, 8.6), Point(86400, 51.67, 8.6)]
    assert not matches_tracker(parked, Photo("p", 40000, 50.4, 1.6))
    assert matches_tracker(parked, Photo("p", 40000, 51.70, 8.65))
    assert matches_tracker([], Photo("p", 40000, 50.4, 1.6)), "unknown location: accept"
    moved = [Point(0, 51.67, 8.6), Point(86400, 50.4, 1.6)]
    assert matches_tracker(moved, Photo("p", 40000, 50.4, 1.6)), "gap with a change of place: unknown, accept"


def test_priority_tracker_claims_photos():
    away, t0 = (51.73, 3.86), ts(10, 12)
    van_away = [Point(t0 - 3600, *away), Point(t0 + 3600, *away)]
    van_home = [Point(t0 - 3600, *HOME), Point(t0 + 3600, *HOME)]
    assert claimed_by(van_away, Photo("p", t0, away[0] + 0.01, away[1]), S)
    assert not claimed_by(van_away, Photo("p", t0, 48.0, -4.6), S)
    assert claimed_by(van_away, Photo("p", t0), S), "no GPS, van travelling: the van's"
    assert not claimed_by(van_home, Photo("p", t0), S), "no GPS, van at home: not the van's"
    assert not claimed_by([], Photo("p", t0, *away), S)


def test_place_photos_estimates_location_and_respects_priority():
    track = [Point(0, 50.0, 8.0), Point(600, 50.0, 9.0)]
    photos = [Photo("gps", 100, 50.0, 8.1), Photo("nogps", 300), Photo("far", 300, 40.0, 0.0), Photo("lost", 99999)]
    placed, unplaced = place_photos(track, photos, S)
    assert [p.id for p in placed] == ["gps", "nogps"]
    assert placed[1].estimated and placed[1].lon == pytest.approx(8.5)
    assert unplaced == 1
    other = [Point(0, 50.0, 8.1), Point(600, 50.0, 8.1)]
    placed, _ = place_photos(track, photos, S, higher_priority=[other])
    assert "gps" not in [p.id for p in placed]


def test_cover_and_city():
    photos = [
        Photo("home", 1, *HOME, city="Hometown"),
        Photo("a", 2, 51.75, 10.0, city="Hillside", width=3, height=2),
        Photo("b", 3, 51.74, 10.01, city="Hillside"),
        Photo("v", 4, 51.75, 10.0, is_video=True, city="Lakeside"),
    ]
    assert most_common_city(photos, exclude_home=S) == "Hillside"
    assert pick_cover(photos) == "a", "landscape images first"
    assert pick_cover([Photo("f", 1, 1, 1, is_favorite=True), *photos]) == "f", "favourites win"
    assert pick_cover([]) is None


def test_suggest_home_is_where_most_nights_are_spent():
    from tripatlas.core.detection import suggest_home

    # 20 nights at home (tracker silent while parked: one point a day), 5 nights on a campsite
    van = [Point(ts(d, 18), *HOME) for d in range(1, 21)] + [Point(ts(d, 18), *FAR) for d in range(21, 26)]
    s = suggest_home([van], "Europe/Berlin")
    assert abs(s["lat"] - HOME[0]) < 0.01 and abs(s["lon"] - HOME[1]) < 0.01
    assert s["nights"] >= 19 and s["total"] >= s["nights"]
    assert suggest_home([[]], "Europe/Berlin") is None


def test_wikipedia_text_without_pronunciation_remnants():
    from tripatlas.integrations.places import clean_text

    assert clean_text("Innsbruck (German: [ˈɪnsbʁʊk] (); Bavarian: Innschbruck, [ˈɪnʃbrʊk]) is the capital.") == (
        "Innsbruck is the capital."
    )
    assert clean_text("Innsbruck (Southern Austro-Bavarian: Innschbrugg; Tyrolean: Schprugg) is a city.") == (
        "Innsbruck is a city."
    )
    assert clean_text("Paris ([paʁi] ) ist die Hauptstadt.") == "Paris ist die Hauptstadt."
    kept = "Lazise ist eine Gemeinde (am Lago di Garda: Venetien) am See."
    assert clean_text(kept) == kept


def test_path_length_counts_sparse_points_but_not_jumps():
    from tripatlas.core.geo import Point, path_length_km

    # a point every 15 minutes at 100 km/h along a meridian: ~25 km steps, all real driving
    sparse = [Point(i * 900, 50 + i * 0.2248, 8.0) for i in range(5)]
    assert 95 < path_length_km(sparse) < 105
    # a GPS jump of 300 km within one minute is not distance travelled
    jump = [Point(0, 50.0, 8.0), Point(60, 52.7, 8.0), Point(120, 50.0, 8.001)]
    assert path_length_km(jump) < 1
