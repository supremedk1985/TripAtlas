"""API tests for setup, roles and the protections that matter most: children are read-only and never see live
positions; nobody sees trackers they were not given."""

import time

from fastapi.testclient import TestClient

from tripatlas.core.geo import Point
from tripatlas.db.models import Tracker, Trip
from tripatlas.db.session import db_session
from tripatlas.services.positions import add_points

ADMIN = {"username": "admin", "display_name": "Admin", "password": "correct-horse", "locale": "en"}


def setup_household(c: TestClient) -> None:
    assert c.post("/api/setup/admin", json=ADMIN).status_code == 200
    r = c.put("/api/settings/household", json={"home_lat": 48.85, "home_lon": 2.35, "timezone": "Europe/Berlin"})
    assert r.status_code == 200, r.text


def login(c: TestClient, username: str, password: str) -> TestClient:
    c.cookies.clear()
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


def test_first_admin_only_once(client):
    assert client.get("/api/setup/status").json()["has_admin"] is False
    setup_household(client)
    assert client.get("/api/setup/status").json()["has_admin"] is True
    assert client.post("/api/setup/admin", json=ADMIN | {"username": "intruder"}).status_code == 409


def test_requires_login(client):
    setup_household(client)
    client.cookies.clear()
    for path in ("/api/trackers", "/api/trips", "/api/photos/markers", "/api/visited", "/api/users"):
        assert client.get(path).status_code == 401, path


def _tracker_with_trip(c: TestClient, name: str, ongoing: bool) -> int:
    r = c.post("/api/trackers", json={"name": name})
    assert r.status_code == 201
    tid = r.json()["id"]
    now = time.time()
    with db_session() as db:
        t = db.get(Tracker, tid)
        add_points(db, t, [Point(now - 600, 50.0, 8.0), Point(now - 60, 50.1, 8.1)], "test")
        db.add(
            Trip(
                tracker_id=tid,
                day_key="2026-10-01",
                start=now - 86400,
                end=now,
                ongoing=ongoing,
                distance_km=10,
                farthest_km=100,
                nights=1,
                dest_lat=50,
                dest_lon=8,
            )
        )
    return tid


def test_child_is_read_only_and_never_sees_live_data(client):
    setup_household(client)
    van = _tracker_with_trip(client, "Van", ongoing=True)
    _tracker_with_trip(client, "Other", ongoing=False)
    r = client.post(
        "/api/users",
        json={
            "username": "kid",
            "display_name": "Kid",
            "password": "kid-password",
            "role": "child",
            "tracker_ids": [van],
        },
    )
    assert r.status_code == 201 and r.json()["can_see_live"] is False

    login(client, "kid", "kid-password")
    trackers = client.get("/api/trackers").json()
    assert [t["name"] for t in trackers] == ["Van"], "only assigned trackers"
    assert trackers[0]["latest"] is None, "no live position"
    assert client.get("/api/trips").json() == [], "the ongoing trip reveals where the van is now"
    track = client.get(f"/api/trackers/{van}/track", params={"start": 0, "end": time.time()}).json()
    assert track["points"] == [], "recent positions are hidden"
    note = {"tracker_id": van, "kind": "trip", "day_key": "2026-10-01", "title": "Hacked"}
    assert client.put("/api/annotations", json=note).status_code == 403
    assert client.post("/api/trackers", json={"name": "x"}).status_code == 403
    assert client.get("/api/users").status_code == 403
    assert (
        client.put(
            "/api/auth/me", json={"current_password": "kid-password", "new_password": "new-password-1"}
        ).status_code
        == 403
    )


def test_member_sees_only_assigned_trackers(client):
    setup_household(client)
    van = _tracker_with_trip(client, "Van", ongoing=False)
    car = _tracker_with_trip(client, "Car", ongoing=False)
    client.post(
        "/api/users", json={"username": "mia", "display_name": "Mia", "password": "mia-password", "tracker_ids": [van]}
    )
    login(client, "mia", "mia-password")
    assert client.get(f"/api/trackers/{car}/track", params={"start": 0, "end": time.time()}).status_code == 404
    assert len(client.get("/api/trips").json()) == 1
    note = {"tracker_id": van, "kind": "trip", "day_key": "2026-10-01", "title": "Holiday", "note_html": "<p>Nice</p>"}
    assert client.put("/api/annotations", json=note).status_code == 200
    assert client.get("/api/trips").json()[0]["title"] == "Holiday"
    bad = note | {
        "note_html": '<p>Hi<img src=x onerror="alert(1)"><a href="javascript:alert(1)">x</a><script>x</script></p>'
    }
    stored = client.put("/api/annotations", json=bad).json()["note_html"]
    assert "onerror" not in stored and "javascript" not in stored and "script" not in stored and "Hi" in stored
    assert client.put("/api/annotations", json=note | {"tracker_id": car}).status_code == 404


def test_login_throttle(client):
    setup_household(client)
    client.cookies.clear()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": ADMIN["password"]}).status_code == 429


def test_cross_site_requests_are_refused(client):
    setup_household(client)
    r = client.post("/api/trackers", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.post("/api/trackers", json={"name": "x"}, headers={"Origin": "http://testserver"}).status_code == 201


def test_app_token(client):
    setup_household(client)
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"username": "admin", "password": ADMIN["password"], "client": "app"})
    token = r.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["username"] == "admin"
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_last_admin_cannot_be_demoted(client):
    setup_household(client)
    me = client.get("/api/auth/me").json()
    assert client.patch(f"/api/users/{me['id']}", json={"role": "member"}).status_code == 400


def test_secrets_are_encrypted_at_rest(client):
    setup_household(client)
    client.put("/api/settings/immich", json={"url": "http://immich:2283", "api_key": "super-secret-key"})
    with db_session() as db:
        from tripatlas.db.models import Setting

        assert "super-secret-key" not in str(db.get(Setting, "immich").value)
    assert client.get("/api/settings/immich").json() == {"url": "http://immich:2283", "has_api_key": True}


def test_import_gpx_twice_and_children_cannot_import(client):
    setup_household(client)
    tid = client.post("/api/trackers", json={"name": "Bike"}).json()["id"]
    gpx = b"""<?xml version="1.0"?><gpx version="1.1" creator="t" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
      <trkpt lat="48.80" lon="2.30"><time>2024-05-01T10:00:00Z</time></trkpt>
      <trkpt lat="48.81" lon="2.31"><time>2024-05-01T10:01:00Z</time></trkpt></trkseg></trk></gpx>"""
    files = {"file": ("ride.gpx", gpx, "application/gpx+xml")}
    r = client.post("/api/imports", data={"tracker_id": tid}, files=files)
    assert r.status_code == 200 and r.json()["added"] == 2
    again = client.post("/api/imports", data={"tracker_id": tid}, files=files).json()
    assert again["added"] == 0 and again["skipped"] == 2, "importing the same file twice is harmless"
    bad = client.post("/api/imports", data={"tracker_id": tid}, files={"file": ("x.gpx", b"not xml", "text/plain")})
    assert bad.status_code == 400
    client.post(
        "/api/users",
        json={
            "username": "kid",
            "display_name": "Kid",
            "password": "kid-password",
            "role": "child",
            "tracker_ids": [tid],
        },
    )
    login(client, "kid", "kid-password")
    assert client.post("/api/imports", data={"tracker_id": tid}, files=files).status_code == 403
