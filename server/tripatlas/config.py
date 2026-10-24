"""Process-level configuration from environment variables (prefix TRIPATLAS_). Everything a household configures
(home location, Traccar, Immich, ...) lives in the database and is set through the setup wizard — see
services/settings.py."""
from __future__ import annotations

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
    web_dir: Path | None = Path(__file__).resolve().parent.parent.parent / "web" / "build"
    log_level: str = "INFO"
    # Contact for the User-Agent sent to Wikipedia/Nominatim (their policies require one).
    contact: str = "https://github.com/tripatlas/tripatlas"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'tripatlas.db'}"


@lru_cache
def get_config() -> Config:
    cfg = Config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg
