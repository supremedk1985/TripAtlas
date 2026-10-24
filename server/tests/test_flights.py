"""Flight detection, modelled on a real return flight from the Canary Islands (altitudes as the phone recorded them,
places changed)."""

from tripatlas.core.flights import GeoPhoto, candidates, group_flights, is_airborne, neighbour_speeds, plausible

H = 3600.0
ISLAND = (28.68, -17.76)
HOME = (51.30, 6.70)


def flight_day():
    """Phone A: photos on the island, take-off climb, two cruise photos over France, approach, home.
    Phone B: someone else at home the whole time, photographing now and then."""
    a = [
        GeoPhoto("a-island", 0, *ISLAND, "A"),
        GeoPhoto("a-airport", 0.3 * H, 28.63, -17.75, "A"),  # waiting at the gate
        GeoPhoto("a-climb", 0.35 * H, 28.70, -17.70, "A"),  # 3,000 m, a few minutes after take-off
        GeoPhoto("a-cruise1", 2.8 * H, 44.20, -1.30, "A"),  # 11,350 m over France
        GeoPhoto("a-cruise2", 3.0 * H, 46.40, 0.10, "A"),
        GeoPhoto("a-descent", 3.75 * H, 50.40, 6.20, "A"),  # 8,400 m
        GeoPhoto("a-approach", 3.9 * H, 51.20, 6.95, "A"),  # 1,000 m
        GeoPhoto("a-home", 4.2 * H, *HOME, "A"),
    ]
    b = [GeoPhoto(f"b{i}", i * 0.5 * H, 52.10, 9.40, "B") for i in range(9)]
    return a + b


ALTITUDES = {
    "a-island": 80,
    "a-airport": 60,
    "a-climb": 3000,
    "a-cruise1": 11350,
    "a-cruise2": 11340,
    "a-descent": 8400,
    "a-approach": 1020,
    "a-home": 40,
}


def test_only_fast_photos_of_the_same_camera_are_candidates():
    c = set(candidates(flight_day()))
    assert "a-cruise1" in c and "a-climb" in c
    assert not any(x.startswith("b") for x in c), "the other phone at home never jumps"


def test_two_phones_in_two_cities_are_not_a_flight():
    # Partner sharing: two people photograph alternately in cities 240 km apart — combined it looks like 5,000 km/h.
    photos = [GeoPhoto(f"x{i}", i * 300, *(HOME if i % 2 else (52.0, 10.0)), "A" if i % 2 else "B") for i in range(10)]
    assert candidates(photos) == []


def test_airborne_rules():
    assert is_airborne(11350, 0, 0), "cruise altitude alone is enough"
    assert is_airborne(3000, 900, 0)
    assert not is_airborne(2400, 0, 0), "a mountain top without a speed jump is not a flight"
    assert not is_airborne(2400, 120, 120), "driving down a mountain road"
    assert is_airborne(1020, 400, 400), "low approach with a fast neighbour"
    assert not is_airborne(None, 900, 900), "no altitude, no decision"


def test_group_into_one_flight_with_origin_and_destination():
    photos = flight_day()
    speeds = neighbour_speeds(photos)
    airborne = {
        pid: ALTITUDES[pid]
        for pid in candidates(photos)
        if pid in ALTITUDES and is_airborne(ALTITUDES[pid], *speeds[pid])
    }
    assert set(airborne) == {"a-climb", "a-cruise1", "a-cruise2", "a-descent", "a-approach"}
    flights = group_flights(photos, airborne)
    assert len(flights) == 1
    f = flights[0]
    assert f.photo_ids[0] == "a-climb" and f.photo_ids[-1] == "a-approach"
    assert f.origin == (28.63, -17.75) and f.destination == HOME
    assert f.max_altitude_m == 11350


def test_gps_glitch_in_a_mountain_village_is_not_a_flight():
    # Real case: a village at ~900 m; one position jumped 30 km and back within minutes.
    village = (28.65, -17.85)
    photos = [
        GeoPhoto("v1", 0, *village, "A"),
        GeoPhoto("v2", 300, 28.90, -17.85, "A"),  # the glitch, 900 m altitude
        GeoPhoto("v3", 600, *village, "A"),
    ]
    speeds = neighbour_speeds(photos)
    airborne = {"v2": 920.0} if is_airborne(920.0, *speeds["v2"]) else {}
    assert airborne, "on its own the photo looks airborne …"
    assert not any(plausible(f) for f in group_flights(photos, airborne)), "… but it went nowhere"


def test_real_flight_is_plausible():
    photos = flight_day()
    speeds = neighbour_speeds(photos)
    airborne = {pid: ALTITUDES[pid] for pid in candidates(photos) if is_airborne(ALTITUDES[pid], *speeds[pid])}
    assert all(plausible(f) for f in group_flights(photos, airborne))
