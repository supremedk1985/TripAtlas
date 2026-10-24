"""Minimal Immich API client (tested against Immich v3.x). Read-only.

Immich changes its API between major versions; everything version-specific is kept in this file so a change there
means one place to fix. Endpoints used:
  GET  /api/server/version, /api/users/me
  GET  /api/map/markers                  all geotagged assets (id, lat, lon, city, country) — the photo layer
  POST /api/search/metadata               assets taken in a period, with EXIF
  POST /api/search/smart                  CLIP search ("beautiful landscape") for cover images
  GET  /api/assets/{id}/thumbnail         image bytes
  GET  /api/assets/{id}                   type, date, duration of one asset
  GET  /api/assets/{id}/video/playback    video stream (supports Range)
  GET  /api/assets/{id}/original          first bytes only (Range), for the EXIF GPS altitude
"""

from __future__ import annotations

import io

import exifread
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

    def all_assets(self, page_size: int = 1000):
        """Every asset with EXIF, page by page (generator)."""
        page = 1
        while page:
            d = self._call(
                "POST", "/api/search/metadata", json={"withExif": True, "size": page_size, "page": page}
            ).json()
            items = d.get("assets", {})
            yield from items.get("items", [])
            nxt = items.get("nextPage")
            page = int(nxt) if nxt else 0

    def gps_altitude(self, asset_id: str, head_bytes: int = 131072) -> float | None:
        """GPS altitude in metres from the original's EXIF, reading only the first bytes. None if absent."""
        r = self._call(
            "GET", f"/api/assets/{asset_id}/original", headers={"Accept": "*/*", "Range": f"bytes=0-{head_bytes - 1}"}
        )
        try:
            tags = exifread.process_file(io.BytesIO(r.content), details=False, stop_tag="GPS GPSAltitude")
        except Exception:  # unreadable / unsupported container: treat as "no altitude"
            return None
        alt = tags.get("GPS GPSAltitude")
        if not alt or not alt.values:
            return None
        v = alt.values[0]
        value = float(v.num) / float(v.den) if getattr(v, "den", 1) else 0.0
        ref = tags.get("GPS GPSAltitudeRef")
        if ref and ref.values and ref.values[0] == 1:  # below sea level
            value = -value
        return round(value, 1)

    def exif_tags(self, asset_id: str, head_bytes: int = 262144) -> dict[str, str]:
        """Every EXIF tag of the original as text, read from the first bytes only (EXIF sits at the start of the
        file). Binary blobs — embedded thumbnails, maker notes — are left out. Empty for formats without EXIF."""
        r = self._call(
            "GET", f"/api/assets/{asset_id}/original", headers={"Accept": "*/*", "Range": f"bytes=0-{head_bytes - 1}"}
        )
        try:
            tags = exifread.process_file(io.BytesIO(r.content), details=False)
        except Exception:  # unreadable / unsupported container
            return {}
        out = {}
        for name, tag in sorted(tags.items()):
            if name in ("JPEGThumbnail", "TIFFThumbnail") or "MakerNote" in name or name.startswith("Thumbnail"):
                continue
            text = str(tag.printable if hasattr(tag, "printable") else tag).strip()
            if (text and len(text) <= 300 and not text.startswith("[")) or (text.startswith("[") and len(text) <= 120):
                out[name] = text
        return out

    def asset(self, asset_id: str) -> dict:
        return self._call("GET", f"/api/assets/{asset_id}").json()

    def open_video(self, asset_id: str, byte_range: str | None = None) -> httpx.Response:
        """Start streaming a video. The caller must close the response. Range requests are passed through so
        players can seek."""
        headers = {"Accept": "*/*"}
        if byte_range:
            headers["Range"] = byte_range
        req = self._http.build_request(
            "GET", f"/api/assets/{asset_id}/video/playback", headers=headers, timeout=httpx.Timeout(30, read=300)
        )
        try:
            r = self._http.send(req, stream=True)
        except httpx.HTTPError as e:
            raise ImmichError(f"Immich not reachable: {e}") from e
        if r.status_code >= 400:
            r.close()
            raise ImmichError(f"Immich answered {r.status_code}")
        return r

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
