"""API tests for setup, roles and the protections that matter most: children are read-only and never see live
positions; nobody sees trackers they were not given."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

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


def test_changing_only_the_traccar_url_keeps_credentials(client):
    setup_household(client)
    client.put("/api/settings/traccar", json={"url": "http://a:8082", "email": "me@x", "password": "pw-1234567"})
    client.put("/api/settings/traccar", json={"url": "http://b:8082"})
    assert client.get("/api/settings/traccar").json() == {
        "url": "http://b:8082",
        "email": "me@x",
        "has_token": False,
        "has_password": True,
    }
    client.put("/api/settings/traccar", json={"url": "http://b:8082", "token": "tok"})
    assert client.get("/api/settings/traccar").json()["has_token"] is True


def test_sessions_slide_while_used(client):
    from datetime import timedelta

    from tripatlas.db.models import Session as DbSession
    from tripatlas.db.models import utcnow

    setup_household(client)
    with db_session() as db:
        s = db.query(DbSession).one()
        s.expires_at = utcnow() + timedelta(days=1)  # about to expire …
        s.last_seen_at = utcnow() - timedelta(hours=1)
    assert client.get("/api/auth/me").status_code == 200
    with db_session() as db:
        s = db.query(DbSession).one()
        expires = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=utcnow().tzinfo)
        assert expires - utcnow() > timedelta(days=20), "… but using it extends the sign-in"


def test_admin_status_and_home_suggestion_without_data(client):
    setup_household(client)
    st = client.get("/api/admin/jobs").json()
    assert st["trips"] == 0 and st["trackers"] == [] and "last_run_at" in st
    assert client.get("/api/setup/home-suggestion", params={"tz": "Europe/Berlin"}).json() is None
    assert "busy" in client.get("/api/setup/status").json()


def test_photo_kinds_marks_videos_and_skips_unknown(client, monkeypatch):
    from tripatlas.api import photos as photos_api
    from tripatlas.integrations.immich import ImmichError

    vid, img, gone = ("a" * 8 + "-0000-0000-0000-" + "0" * 12, "b" * 8 + "-0000-0000-0000-" + "0" * 12,
                      "c" * 8 + "-0000-0000-0000-" + "0" * 12)
    calls = []

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def asset(self, asset_id):
            calls.append(asset_id)
            if asset_id == gone:
                raise ImmichError("not found")
            return {"type": "VIDEO" if asset_id == vid else "IMAGE"}

    monkeypatch.setattr(photos_api.photo_service, "client_for", lambda db, user: Fake())
    monkeypatch.setattr(photos_api, "_IS_VIDEO", {})
    setup_household(client)
    r = client.post("/api/photos/kinds", json={"ids": [vid, img, gone, "not-an-id", vid]})
    assert r.status_code == 200 and r.json() == {"videos": [vid]}
    assert sorted(calls) == sorted([vid, img, gone])
    # known kinds are not asked again; the missing one is
    client.post("/api/photos/kinds", json={"ids": [vid, img, gone]})
    assert calls.count(vid) == 1 and calls.count(gone) == 2


def test_avatar_own_admin_and_child(client):
    setup_household(client)
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    assert client.put("/api/auth/me/avatar", content=b"GIF89a").status_code == 400
    assert client.put("/api/auth/me/avatar", content=b"\xff\xd8\xff" + b"0" * 400_000).status_code == 413
    me = client.put("/api/auth/me/avatar", content=jpeg).json()
    assert me["avatar_version"]
    assert client.get(f"/api/users/{me['id']}/avatar").content == jpeg
    kid = client.post("/api/users", json={"username": "kid", "display_name": "Kid", "password": "kid-password",
                                          "role": "child"}).json()
    assert client.put(f"/api/users/{kid['id']}/avatar", content=jpeg).json()["avatar_version"]
    login(client, "kid", "kid-password")
    assert client.put("/api/auth/me/avatar", content=jpeg).status_code == 403   # children change nothing
    assert client.get(f"/api/users/{me['id']}/avatar").status_code == 200    # but see the family's pictures
    login(client, "admin", ADMIN["password"])
    assert client.delete("/api/auth/me/avatar").json()["avatar_version"] is None
    assert client.get(f"/api/users/{me['id']}/avatar").status_code == 404


def test_trip_ids_survive_recompute(client):
    """Links like /?trip=<id> must keep working when new positions arrive and the trips are detected again."""
    from tripatlas.services.trips import recompute

    setup_household(client)   # home in Paris
    tid = client.post("/api/trackers", json={"name": "Van"}).json()["id"]
    t0 = 1_780_000_000.0      # a Tuesday in 2026, 00:00 UTC-ish

    def stay(lat, lon, start_h, hours):
        return [Point(t0 + (start_h + h) * 3600, lat, lon) for h in range(hours)]

    with db_session() as db:
        t = db.get(Tracker, tid)
        add_points(db, t, stay(48.85, 2.35, 0, 10) + stay(45.76, 4.83, 12, 60) + stay(48.85, 2.35, 74, 30), "test")
        recompute(db, t, now=t0 + 200 * 3600)
        first = [(tr.id, tr.day_key) for tr in db.scalars(select(Trip).where(Trip.tracker_id == tid))]
        assert len(first) == 1
        # another vehicle's trip now holds the highest id, as in any real household
        other = Tracker(name="Car")
        db.add(other)
        db.flush()
        db.add(Trip(tracker_id=other.id, day_key="2026-01-01", start=t0, end=t0 + 1, distance_km=1, farthest_km=1,
                    nights=1, dest_lat=0, dest_lon=0))
        db.commit()
        # more positions later: a second trip; the first keeps its id
        add_points(db, t, stay(43.30, 5.37, 110, 60) + stay(48.85, 2.35, 172, 20), "test")
        recompute(db, t, now=t0 + 300 * 3600)
        after = {tr.day_key: tr.id for tr in db.scalars(select(Trip).where(Trip.tracker_id == tid))}
    assert len(after) == 2
    assert after[first[0][1]] == first[0][0]


def test_bike_gpx_import_thinned_deduplicated_and_rides_recognised(client):
    """A CurruBike export: every ride as a track, a point per second. Thinned on import, a second import adds
    nothing, and each day ride becomes an entry of its own for a bike tracker."""
    from datetime import UTC, datetime

    from tripatlas.services.trips import recompute

    setup_household(client)   # home in Paris (48.85, 2.35)
    bike = client.post("/api/trackers", json={"name": "Fahrrad", "kind": "bike"}).json()
    assert bike["kind"] == "bike"

    def ride(day: int) -> str:
        t0 = datetime(2026, 6, day, 10, tzinfo=UTC).timestamp()
        pts = []
        for s in range(0, 3600):                       # one hour out and back, 1 Hz
            frac = s / 1800 if s < 1800 else (3600 - s) / 1800
            lat = 48.85 + 0.06 * frac                    # up to ~6.7 km north and back
            ts = datetime.fromtimestamp(t0 + s, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            pts.append(f'<trkpt lat="{lat:.6f}" lon="2.35"><ele>40</ele><time>{ts}</time></trkpt>')
        return "<trk><name>ride</name><trkseg>" + "".join(pts) + "</trkseg></trk>"

    gpx = ('<?xml version="1.0"?><gpx version="1.1" creator="CurruBike" xmlns="http://www.topografix.com/GPX/1/1">'
           + ride(5) + ride(3) + "</gpx>").encode()   # newest ride first, as an app may export
    up = lambda: client.post("/api/imports", data={"tracker_id": str(bike["id"])},  # noqa: E731
                             files={"file": ("currubike.gpx", gpx, "application/gpx+xml")}).json()
    first = up()
    assert first["points"] == 7200 and first["kept"] == 720 and first["added"] == 720
    again = up()
    assert again["added"] == 0 and again["skipped"] == 720

    with db_session() as db:
        recompute(db, db.get(Tracker, bike["id"]), now=datetime(2026, 7, 1, tzinfo=UTC).timestamp())
        trips = list(db.scalars(select(Trip).where(Trip.tracker_id == bike["id"]).order_by(Trip.start)))
    assert [t.nights for t in trips] == [0, 0]
    assert [t.day_key for t in trips] == ["2026-06-03", "2026-06-05"]


def test_map_notes_editors_write_children_read(client):
    setup_household(client)
    photo = "a" * 8 + "-0000-0000-0000-" + "0" * 12
    body = {"lat": 51.3, "lon": 9.5, "text": "  Erster Campingplatz ", "photo_id": photo}
    n = client.post("/api/notes", json=body).json()
    assert n["text"] == "Erster Campingplatz" and n["author"] == "Admin" and n["photo_id"] == photo
    changed = client.patch(f"/api/notes/{n['id']}", json={"text": "Erster Campingplatz 🚐"}).json()
    assert changed["text"] == "Erster Campingplatz 🚐"
    assert client.post("/api/notes", json={"lat": 51, "lon": 9, "text": ""}).status_code == 422
    kid = {"username": "kid", "display_name": "Kid", "password": "kid-password", "role": "child"}
    client.post("/api/users", json=kid)
    login(client, "kid", "kid-password")
    assert [x["text"] for x in client.get("/api/notes").json()] == ["Erster Campingplatz 🚐"]
    assert client.post("/api/notes", json={"lat": 51, "lon": 9, "text": "x"}).status_code == 403
    assert client.delete(f"/api/notes/{n['id']}").status_code == 403
    login(client, "admin", ADMIN["password"])
    assert client.delete(f"/api/notes/{n['id']}").status_code == 204
    assert client.get("/api/notes").json() == []


def test_login_throttle_is_per_account(client):
    """A child mistyping five times does not lock the parent out of the same computer."""
    setup_household(client)
    client.post("/api/users", json={"username": "kid", "display_name": "Kid", "password": "kid-password",
                                    "role": "child"})
    client.cookies.clear()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "kid", "password": "wrong!!"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "kid", "password": "kid-password"}).status_code == 429
    assert client.post("/api/auth/login", json={"username": "admin", "password": ADMIN["password"]}).status_code == 200


def test_role_change_to_child_takes_live_access(client):
    setup_household(client)
    u = client.post("/api/users", json={"username": "tim", "display_name": "Tim", "password": "tim-password",
                                        "role": "member"}).json()
    assert u["can_see_live"] is True
    assert client.patch(f"/api/users/{u['id']}", json={"role": "child"}).json()["can_see_live"] is False


def test_failed_import_leaves_nothing(client):
    setup_household(client)
    tid = client.post("/api/trackers", json={"name": "Van"}).json()["id"]
    from datetime import UTC, datetime

    t0 = datetime(2026, 6, 1, 10, tzinfo=UTC).timestamp()
    # 10 s apart (nothing thinned away), more than one write batch before the file breaks off
    pts = "".join(f'<trkpt lat="50.{i:04d}" lon="8.0"><time>'
                  f'{datetime.fromtimestamp(t0 + 10 * i, UTC):%Y-%m-%dT%H:%M:%SZ}</time></trkpt>' for i in range(3000))
    broken = ('<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
              + pts + "<trkpt lat=").encode()   # cut off mid-way
    files = {"file": ("x.gpx", broken, "application/gpx+xml")}
    r = client.post("/api/imports", data={"tracker_id": str(tid)}, files=files)
    assert r.status_code == 400
    with db_session() as db:
        from tripatlas.db.models import Position
        assert db.scalar(select(func.count()).select_from(Position).where(Position.tracker_id == tid)) == 0


def _jpeg(w, h):
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (w, h), (200, 120, 40)).save(out, "JPEG")
    return out.getvalue()


def test_medium_photo_is_scaled_cached_and_kept_apart_per_immich_key(client, monkeypatch):
    import io

    from PIL import Image

    from tripatlas.api import photos as photos_api

    aid = "d" * 8 + "-0000-0000-0000-" + "0" * 12
    calls = []
    key = {"id": "key-a"}

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def thumbnail(self, asset_id, size):
            calls.append(size)
            return _jpeg(1440, 1080), "image/jpeg"

    monkeypatch.setattr(photos_api.photo_service, "client_for", lambda db, user: Fake())
    monkeypatch.setattr(photos_api.photo_service, "key_id", lambda db, user: key["id"])
    setup_household(client)
    r = client.get(f"/api/photos/{aid}/thumbnail", params={"size": "medium"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert max(Image.open(io.BytesIO(r.content)).size) == 640
    assert calls == ["preview"]
    # the second time it comes from disk
    assert client.get(f"/api/photos/{aid}/thumbnail", params={"size": "medium"}).content == r.content
    assert calls == ["preview"]
    # an account with another Immich key never gets the cached copy: it asks Immich with its own key
    key["id"] = "key-b"
    client.get(f"/api/photos/{aid}/thumbnail", params={"size": "medium"})
    assert calls == ["preview", "preview"]


def test_medium_cache_drops_the_least_recently_used_files(client):
    import os
    import time

    from tripatlas.services import medium

    ids = [f"{i:08x}-0000-0000-0000-000000000000" for i in range(4)]
    for n, aid in enumerate(ids):
        medium.put("k", aid, b"x" * 400_000)
        p = medium.cache_dir() / "k" / aid[:2] / f"{aid}.webp"
        t = time.time() - 1000 + n * 10
        os.utime(p, (t, t))
    medium.get("k", ids[0])  # used just now: stays although it was written first
    medium.prune(limit_mb=1)
    left = sorted(p.stem for p in medium.cache_dir().rglob("*.webp"))
    assert left == sorted([ids[0], ids[3]])


def test_photo_markers_answer_304_when_unchanged(client, monkeypatch):
    from tripatlas.api import photos as photos_api

    marks = [{"id": "e" * 8 + "-0000-0000-0000-" + "0" * 12, "lat": 52.1, "lon": 8.5}]
    monkeypatch.setattr(photos_api.photo_service, "markers", lambda db, user: marks)
    setup_household(client)
    r = client.get("/api/photos/markers")
    assert r.status_code == 200 and len(r.json()["markers"]) == 1
    tag = r.headers["etag"]
    assert client.get("/api/photos/markers", headers={"If-None-Match": tag}).status_code == 304
    marks.append({"id": "f" * 8 + "-0000-0000-0000-" + "0" * 12, "lat": 52.2, "lon": 8.6})
    r2 = client.get("/api/photos/markers", headers={"If-None-Match": tag})
    assert r2.status_code == 200 and len(r2.json()["markers"]) == 2 and r2.headers["etag"] != tag


def test_photo_requests_hold_no_database_connection_while_waiting_for_immich(client, monkeypatch):
    from tripatlas.api import photos as photos_api
    from tripatlas.db.session import get_engine

    aid = "a1" * 4 + "-0000-0000-0000-" + "0" * 12
    held = []

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def close(self):
            pass

        def thumbnail(self, asset_id, size):
            held.append(get_engine().pool.checkedout())
            return _jpeg(1440, 1080), "image/jpeg"

    monkeypatch.setattr(photos_api.photo_service, "client_for", lambda db, user: Fake())
    monkeypatch.setattr(photos_api.photo_service, "key_id", lambda db, user: "k")
    setup_household(client)
    for size in ("thumbnail", "medium"):
        assert client.get(f"/api/photos/{aid}/thumbnail", params={"size": size}).status_code == 200
    assert held == [0, 0]


def test_sign_in_check_hands_back_its_database_connection(client, monkeypatch):
    from tripatlas.api import photos as photos_api
    from tripatlas.db.session import get_engine

    seen = []

    def key_id(db, user):
        seen.append(get_engine().pool.checkedout())
        raise RuntimeError("stop here")

    monkeypatch.setattr(photos_api.photo_service, "key_id", key_id)
    setup_household(client)
    aid = "b2" * 4 + "-0000-0000-0000-" + "0" * 12
    with pytest.raises(RuntimeError):
        client.get(f"/api/photos/{aid}/thumbnail", params={"size": "medium"})
    assert seen == [0]


def test_video_check_reports_immich_transcoding(client, monkeypatch):
    from tripatlas.api import photos as photos_api
    from tripatlas.services import photos as photo_service

    ff = {"value": {"transcode": "required", "targetResolution": "720"}}

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def video_transcoding(self):
            return ff["value"]

    monkeypatch.setattr(photos_api.photo_service, "client_for", lambda db, user: Fake())
    setup_household(client)
    for value, ok in [
        ({"transcode": "required", "targetResolution": "720"}, False),
        ({"transcode": "optimal", "targetResolution": "720"}, True),
        ({"transcode": "optimal", "targetResolution": "original"}, False),
        (None, None),  # key without Immich admin rights: cannot be told
    ]:
        ff["value"] = value
        photo_service._video_check["at"] = 0
        assert client.get("/api/photos/video-check").json()["ok"] is ok


def test_visited_can_be_limited_to_one_year(client):
    """'Where were we in year X': stays (and photos) of that year only, plus the list of years there are."""
    from datetime import UTC, datetime

    from tripatlas.services.trips import recompute

    setup_household(client)   # home in Paris
    tid = client.post("/api/trackers", json={"name": "Van"}).json()["id"]

    def stay(t0, lat, lon, start_h, hours):
        return [Point(t0 + (start_h + h) * 3600, lat, lon) for h in range(hours)]

    a = datetime(2025, 6, 1, tzinfo=UTC).timestamp()
    b = datetime(2026, 6, 1, tzinfo=UTC).timestamp()
    with db_session() as db:
        t = db.get(Tracker, tid)
        pts = stay(a, 48.85, 2.35, 0, 10) + stay(a, 45.76, 4.83, 12, 60) + stay(a, 48.85, 2.35, 74, 30)
        pts += stay(b, 48.85, 2.35, 0, 10) + stay(b, 43.30, 5.37, 12, 60) + stay(b, 48.85, 2.35, 74, 30)
        add_points(db, t, pts, "test")
        recompute(db, t, now=b + 300 * 3600)

    def lats(r):
        return sorted(round(p["lat"]) for p in r["pins"])

    every = client.get("/api/visited").json()
    assert lats(every) == [43, 46] and every["years"] == [2026, 2025]
    assert lats(client.get("/api/visited", params={"year": 2025}).json()) == [46]
    assert lats(client.get("/api/visited", params={"year": 2026}).json()) == [43]
    assert client.get("/api/visited", params={"year": 2019}).json()["pins"] == []
