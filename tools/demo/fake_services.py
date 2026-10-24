#!/usr/bin/env python3
"""Stand-ins for Traccar and Immich that serve the demo data (tools/demo/data, tools/demo/photos).

They answer exactly the requests TripAtlas makes (see server/tripatlas/integrations/), nothing more — enough to try
TripAtlas, to develop the web UI without a real installation, and to record the documentation videos.

    pip install fastapi uvicorn pillow
    python3 tools/demo/fake_services.py traccar --port 8082
    python3 tools/demo/fake_services.py immich  --port 2283

Any credentials are accepted. Or run everything with docker compose: tools/demo/compose.yaml."""

from __future__ import annotations

import argparse
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image

HERE = Path(__file__).resolve().parent
# Names in the language of the recording (DEMO_LANG=de|en)
EN = os.environ.get("DEMO_LANG", "de") == "en"
NAMES = {"van": "Camper van" if EN else "Wohnmobil", "car": "Car" if EN else "Auto",
         "user": "Anna Smith" if EN else "Anna Beispiel"}
DATA = HERE / "data"
PHOTOS = HERE / "photos"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def to_ts(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


# --- Traccar ------------------------------------------------------------------------------------------------------

def traccar_app() -> FastAPI:
    app = FastAPI(title="Demo Traccar")
    positions = json.loads((DATA / "positions.json").read_text())
    devices = [{"id": 1, "name": NAMES["van"], "uniqueId": "demo-van", "status": "online", "key": "van"},
               {"id": 2, "name": NAMES["car"], "uniqueId": "demo-car", "status": "offline", "key": "car"}]

    def as_position(dev: dict, i: int, p: list) -> dict:
        return {"id": dev["id"] * 1_000_000 + i, "deviceId": dev["id"], "protocol": "osmand", "valid": True,
                "fixTime": iso(p[0]), "deviceTime": iso(p[0]), "serverTime": iso(p[0]),
                "latitude": p[1], "longitude": p[2], "speed": round(p[3] / 1.852, 1), "altitude": 0, "course": 0}

    @app.get("/api/server")
    def server():
        return {"version": "6.16.0", "registration": False}

    @app.get("/api/devices")
    def list_devices():
        return [{k: v for k, v in d.items() if k != "key"} for d in devices]

    @app.get("/api/positions")
    def list_positions(request: Request, deviceId: int | None = None):
        q = request.query_params
        if deviceId is None:   # latest position of every device
            return [as_position(d, len(positions[d["key"]]) - 1, positions[d["key"]][-1]) for d in devices]
        dev = next((d for d in devices if d["id"] == deviceId), None)
        if dev is None:
            raise HTTPException(404)
        start, end = to_ts(q["from"]), to_ts(q["to"])
        return [as_position(dev, i, p) for i, p in enumerate(positions[dev["key"]]) if start <= p[0] <= end]

    return app


# --- Immich -------------------------------------------------------------------------------------------------------

def immich_app() -> FastAPI:
    app = FastAPI(title="Demo Immich")
    photos = json.loads((DATA / "photos.json").read_text())
    by_id = {p["id"]: p for p in photos}

    def check(request: Request) -> None:
        if not request.headers.get("x-api-key"):
            raise HTTPException(401, "Missing API key")

    def asset(p: dict) -> dict:
        taken = to_ts(p["taken"])
        return {"id": p["id"], "type": "IMAGE", "originalFileName": p["file"], "fileCreatedAt": iso(taken),
                "localDateTime": iso(taken), "isFavorite": p.get("favorite", False), "isTrashed": False,
                "visibility": "timeline",
                "exifInfo": {"latitude": p["lat"], "longitude": p["lon"], "city": p["city"], "country": p["country"],
                             "state": None, "exifImageWidth": p["width"], "exifImageHeight": p["height"],
                             "orientation": "1", "make": "Demo", "model": "Phone"}}

    def page_of(items: list[dict], body: dict) -> dict:
        size, page = int(body.get("size", 250)), int(body.get("page", 1))
        chunk = items[(page - 1) * size: page * size]
        nxt = str(page + 1) if page * size < len(items) else None
        return {"assets": {"total": len(chunk), "count": len(chunk), "items": chunk, "nextPage": nxt}}

    def in_range(body: dict) -> list[dict]:
        after = to_ts(body["takenAfter"]) if body.get("takenAfter") else float("-inf")
        before = to_ts(body["takenBefore"]) if body.get("takenBefore") else float("inf")
        out = [asset(p) for p in photos if after <= to_ts(p["taken"]) <= before]
        if body.get("isFavorite"):
            out = [a for a in out if a["isFavorite"]]
        return sorted(out, key=lambda a: a["fileCreatedAt"])

    @app.get("/api/server/version")
    def version(request: Request):
        check(request)
        return {"major": 3, "minor": 3, "patch": 5}

    @app.get("/api/users/me")
    def me(request: Request):
        check(request)
        return {"id": "demo", "name": NAMES["user"], "email": "anna@example.org"}

    @app.get("/api/map/markers")
    def markers(request: Request):
        check(request)
        return [{"id": p["id"], "lat": p["lat"], "lon": p["lon"], "city": p["city"], "state": None,
                 "country": p["country"]} for p in photos]

    @app.post("/api/search/metadata")
    async def metadata(request: Request):
        check(request)
        return page_of(in_range(await request.json()), await request.json())

    @app.post("/api/search/smart")
    async def smart(request: Request):
        check(request)
        body = await request.json()
        return page_of(in_range(body), body)

    @app.get("/api/assets/{asset_id}")
    def one(asset_id: str, request: Request):
        check(request)
        if asset_id not in by_id:
            raise HTTPException(404)
        return asset(by_id[asset_id])

    @app.get("/api/assets/{asset_id}/thumbnail")
    def thumbnail(asset_id: str, request: Request, size: str = "thumbnail"):
        check(request)
        if asset_id not in by_id:
            raise HTTPException(404)
        img = Image.open(PHOTOS / by_id[asset_id]["file"])
        img.thumbnail((250, 250) if size == "thumbnail" else (1440, 1440))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/assets/{asset_id}/original")
    def original(asset_id: str, request: Request):
        check(request)
        if asset_id not in by_id:
            raise HTTPException(404)
        data = (PHOTOS / by_id[asset_id]["file"]).read_bytes()
        rng = request.headers.get("range", "")
        if rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start, end = int(a or 0), min(int(b) if b else len(data) - 1, len(data) - 1)
            return Response(data[start:end + 1], status_code=206, media_type="image/jpeg",
                            headers={"Content-Range": f"bytes {start}-{end}/{len(data)}", "Accept-Ranges": "bytes"})
        return Response(data, media_type="image/jpeg")

    @app.get("/api/assets/{asset_id}/video/playback")
    def video(asset_id: str):
        return JSONResponse({"message": "The demo has no videos"}, status_code=404)

    return app


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("service", choices=["traccar", "immich"])
    ap.add_argument("--port", type=int)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    app = traccar_app() if a.service == "traccar" else immich_app()
    uvicorn.run(app, host=a.host, port=a.port or (8082 if a.service == "traccar" else 2283), log_level="warning")
