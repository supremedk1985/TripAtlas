"""Minimal Immich API client (tested against Immich v3.x). Read-only.

Immich changes its API between major versions; everything version-specific is kept in this file so a change there
means one place to fix. Endpoints used:
  GET  /api/server/version, /api/users/me
  GET  /api/map/markers                  all geotagged assets (id, lat, lon, city, country) — the photo layer
  POST /api/search/metadata               assets taken in a period, with EXIF
  POST /api/search/smart                  CLIP search ("beautiful landscape") for cover images
  GET  /api/assets/{id}/thumbnail         image bytes
"""

from __future__ import annotations

import httpx

from ..core.geo import iso_to_ts
from ..core.photos import RAW_EXTENSIONS, Photo


class ImmichError(Exception):
    pass


class ImmichClient:
    def __init__(self, url: str, api_key: str, timeout: float = 60):
        if not url or not api_key:
            raise ImmichError("Immich is not configured")
        self._http = httpx.Client(
            base_url=url.rstrip("/"), timeout=timeout, headers={"x-api-key": api_key, "Accept": "application/json"}
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _call(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            r = self._http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise ImmichError(f"Immich not reachable: {e}") from e
        if r.status_code == 401:
            raise ImmichError("Immich rejected the API key")
        if r.status_code >= 400:
            raise ImmichError(f"Immich answered {r.status_code}")
        return r

    def version(self) -> str:
        v = self._call("GET", "/api/server/version").json()
        return f"{v['major']}.{v['minor']}.{v['patch']}"

    def me(self) -> dict:
        return self._call("GET", "/api/users/me").json()

    def map_markers(self) -> list[dict]:
        """All geotagged assets the key can see, including partner-shared ones."""
        return self._call("GET", "/api/map/markers", params={"withPartners": "true", "isArchived": "false"}).json()

    def photos_between(self, start_iso: str, end_iso: str) -> list[Photo]:
        out, page = [], 1
        while page:
            d = self._call(
                "POST",
                "/api/search/metadata",
                json={"takenAfter": start_iso, "takenBefore": end_iso, "withExif": True, "size": 1000, "page": page},
            ).json()
            items = d.get("assets", {})
            out += [p for p in (asset_to_photo(a) for a in items.get("items", [])) if p]
            nxt = items.get("nextPage")
            page = int(nxt) if nxt else 0
        out.sort(key=lambda p: p.t)
        return out

    def smart_search(self, query: str, start_iso: str, end_iso: str, size: int = 20) -> list[Photo]:
        d = self._call(
            "POST",
            "/api/search/smart",
            json={
                "query": query,
                "takenAfter": start_iso,
                "takenBefore": end_iso,
                "type": "IMAGE",
                "withExif": True,
                "size": size,
            },
        ).json()
        return [p for p in (asset_to_photo(a) for a in d.get("assets", {}).get("items", [])) if p]

    def thumbnail(self, asset_id: str, size: str = "thumbnail") -> tuple[bytes, str]:
        r = self._call("GET", f"/api/assets/{asset_id}/thumbnail", params={"size": size}, headers={"Accept": "*/*"})
        return r.content, r.headers.get("content-type", "image/jpeg")


def asset_to_photo(a: dict) -> Photo | None:
    """Immich asset → Photo. Skips trashed/hidden assets and RAW files (they duplicate the JPEG next to them)."""
    name = (a.get("originalFileName") or "").lower()
    if a.get("isTrashed") or a.get("visibility", "timeline") != "timeline" or name.endswith(RAW_EXTENSIONS):
        return None
    try:
        t = iso_to_ts(a.get("fileCreatedAt") or a.get("localDateTime"))
    except (TypeError, ValueError):
        return None
    e = a.get("exifInfo") or {}
    w, h = e.get("exifImageWidth"), e.get("exifImageHeight")
    if str(e.get("orientation")) in ("5", "6", "7", "8"):  # stored rotated: swap
        w, h = h, w
    return Photo(
        id=a["id"],
        t=t,
        lat=e.get("latitude"),
        lon=e.get("longitude"),
        is_video=a.get("type") == "VIDEO",
        is_favorite=bool(a.get("isFavorite")),
        city=e.get("city"),
        country=e.get("country"),
        width=w,
        height=h,
    )
