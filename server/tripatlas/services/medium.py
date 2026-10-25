"""Medium-sized photos for the overview grid with one or two columns.

Immich offers a small thumbnail (about 250 px) and a large preview (about 1440 px, around 500 KB). Two columns on a
phone need roughly 500 px: the thumbnail looks blurred, the preview costs ten times the data and makes the phone
decode huge images while scrolling. TripAtlas scales the preview down once and keeps the result on disk.

The files are kept apart per Immich key (services.photos.key_id): a cached image is only ever handed to accounts that
use the same key, so the cache never shows a photo that the account's own key could not fetch from Immich.
"""

from __future__ import annotations

import contextlib
import io
import os
import threading
from pathlib import Path

from PIL import Image, ImageOps

from ..config import get_config

EDGE = 640
QUALITY = 78
# check the total size after this many new files, not on every one
_PRUNE_EVERY = 50
_written = 0
_lock = threading.Lock()


def cache_dir() -> Path:
    return get_config().data_dir / "cache" / "medium"


def _path(key: str, asset_id: str) -> Path:
    return cache_dir() / key / asset_id[:2] / f"{asset_id}.webp"


def get(key: str, asset_id: str) -> bytes | None:
    p = _path(key, asset_id)
    try:
        data = p.read_bytes()
    except OSError:
        return None
    # recently used files survive pruning
    with contextlib.suppress(OSError):
        os.utime(p)
    return data


# An overview asks for dozens of photos at once. Each scaling decodes a full preview into memory: 60 at a time took
# the container past its memory limit (25.10.2026, killed by the kernel). A few at a time is as fast on a small CPU.
_scaling = threading.BoundedSemaphore(3)


def scale(preview: bytes) -> bytes:
    with _scaling, Image.open(io.BytesIO(preview)) as im:
        # JPEG decodes straight at a reduced size (1/2, 1/4 …) — less memory and much less work
        im.draft("RGB", (EDGE, EDGE))
        im = ImageOps.exif_transpose(im)
        im.thumbnail((EDGE, EDGE), Image.Resampling.LANCZOS)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, "WEBP", quality=QUALITY, method=4)
        return out.getvalue()


def put(key: str, asset_id: str, data: bytes) -> None:
    global _written
    p = _path(key, asset_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_bytes(data)
        tmp.replace(p)
    except OSError:
        return  # a full or read-only disk only costs the cache, never the picture
    with _lock:
        _written += 1
        due = _written % _PRUNE_EVERY == 0
    if due:
        prune()


def prune(limit_mb: int | None = None) -> None:
    """Deletes the least recently used files until the cache is below 90 % of its limit."""
    limit = (get_config().medium_cache_mb if limit_mb is None else limit_mb) * 1024 * 1024
    files = []
    total = 0
    for f in cache_dir().rglob("*.webp"):
        with contextlib.suppress(OSError):
            st = f.stat()
            files.append((st.st_mtime, st.st_size, f))
            total += st.st_size
    if total <= limit:
        return
    files.sort()
    target = limit * 0.9
    for _, size, f in files:
        if total <= target:
            break
        with contextlib.suppress(OSError):
            f.unlink()
            total -= size

