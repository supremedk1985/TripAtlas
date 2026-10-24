"""Daily consistent snapshot of the SQLite database into <data_dir>/backups/.

Copying a live SQLite file (e.g. a nightly rsync of the data directory) can catch it mid-write. SQLite's online
backup API produces a consistent copy while TripAtlas keeps running; back up the backups/ folder (plus secret.key)
and you are safe. Keeps TRIPATLAS_BACKUP_KEEP snapshots (0 = off). Other databases: use their own dump tools."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from ..config import get_config

log = logging.getLogger(__name__)

INTERVAL_S = 20 * 3600


def snapshot_due(folder: Path, now: float | None = None) -> bool:
    snaps = sorted(folder.glob("tripatlas-*.db"))
    return not snaps or (now or time.time()) - snaps[-1].stat().st_mtime >= INTERVAL_S


def make_snapshot(force: bool = False) -> Path | None:
    cfg = get_config()
    if cfg.backup_keep <= 0 or not cfg.db_url.startswith("sqlite:///"):
        return None
    source = Path(cfg.db_url.removeprefix("sqlite:///"))
    folder = cfg.data_dir / "backups"
    folder.mkdir(exist_ok=True)
    if not force and not snapshot_due(folder):
        return None
    target = folder / f"tripatlas-{datetime.now():%Y-%m-%d}.db"
    tmp = target.with_suffix(".db.part")
    src = sqlite3.connect(source)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    tmp.replace(target)
    for old in sorted(folder.glob("tripatlas-*.db"))[: -cfg.backup_keep]:
        old.unlink()
    log.info("Database snapshot written: %s", target.name)
    return target
