"""Process-level configuration from environment variables (prefix TRIPATLAS_). Everything a household configures
(home location, Traccar, Immich, ...) lives in the database and is set through the setup wizard — see
services/settings.py."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIPATLAS_", env_file=".env", extra="ignore")

    data_dir: Path = Path("/data")
    database_url: str = ""
    # Set to true behind HTTPS so session cookies are only sent over TLS.
    secure_cookies: bool = False
    session_days: int = 30
    sync_interval_minutes: int = 5
    # Directory with the built web UI (served at /). Empty: API only.
    web_dir: Path | None = Path(__file__).resolve().parent.parent.parent / "web" / "build"  # Docker: /app/web
    log_level: str = "INFO"
    # Daily consistent SQLite snapshots in <data_dir>/backups (services/backup.py); 0 = off.
    backup_keep: int = 7
    # Contact for the User-Agent sent to Wikipedia/Nominatim (their policies require one).
    contact: str = "https://github.com/supremedk1985/tripatlas"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'tripatlas.db'}"


@lru_cache
def get_config() -> Config:
    cfg = Config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(cfg.data_dir, os.W_OK):
        # The usual cause: Docker created the bind-mounted folder as root before TripAtlas (uid 1000) first ran.
        raise SystemExit(
            f"TripAtlas cannot write to {cfg.data_dir} (running as uid {os.getuid()}). On the host, give the data "
            f"folder to that user, e.g.  sudo chown -R {os.getuid()}:{os.getgid()} ./data  — then start again."
        )
    return cfg
