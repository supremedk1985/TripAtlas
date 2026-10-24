"""Minimal Traccar REST client (tested against Traccar 6.x). Read-only: TripAtlas never writes to Traccar."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ..core.geo import Point, iso_to_ts

KNOTS_TO_KMH = 1.852


class TraccarError(Exception):
    pass


class TraccarClient:
    def __init__(self, url: str, token: str = "", email: str = "", password: str = "", timeout: float = 120):
        if not url:
            raise TraccarError("Traccar URL is not configured")
        headers = {"Accept": "application/json"}
        auth = None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif email:
            auth = (email, password)
        self._http = httpx.Client(base_url=url.rstrip("/"), headers=headers, auth=auth, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _get(self, path: str, **params):
        try:
            r = self._http.get(path, params=params)
        except httpx.HTTPError as e:
            raise TraccarError(f"Traccar not reachable: {e}") from e
        if r.status_code == 401:
            raise TraccarError("Traccar rejected the credentials")
        if r.status_code >= 400:
            raise TraccarError(f"Traccar answered {r.status_code}")
        return r.json()

    def server_info(self) -> dict:
        return self._get("/api/server")

    def devices(self) -> list[dict]:
        return self._get("/api/devices")

    def latest_positions(self) -> list[dict]:
        return self._get("/api/positions")

    def positions(self, device_id: int, start: float, end: float) -> list[Point]:
        return points_from_traccar(
            self._get("/api/positions", deviceId=device_id, **{"from": _iso(start), "to": _iso(end)})
        )


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def points_from_traccar(raw: list[dict]) -> list[Point]:
    """Traccar positions → sorted Points; invalid fixes dropped, speed converted from knots to km/h."""
    out = []
    for p in raw:
        if p.get("valid") is False:
            continue
        try:
            out.append(
                Point(
                    iso_to_ts(p["fixTime"]),
                    p["latitude"],
                    p["longitude"],
                    round((p.get("speed") or 0) * KNOTS_TO_KMH, 1),
                    round(p.get("altitude") or 0),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x.t)
    return out
