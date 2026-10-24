"""Encryption for stored credentials (Traccar password/token, Immich API keys).

The key comes from TRIPATLAS_SECRET_KEY or is generated once into <data_dir>/secret.key. It protects the database
file on its own (e.g. a copied backup) — anyone with access to both the key and the database can decrypt. Back up
secret.key together with the database, otherwise stored credentials must be re-entered."""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_config


@lru_cache
def _fernet() -> Fernet:
    key = os.environ.get("TRIPATLAS_SECRET_KEY")
    if not key:
        path = get_config().data_dir / "secret.key"
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        key = path.read_bytes().strip()
    return Fernet(key if isinstance(key, bytes) else key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Wrong or lost key: behave as "not configured" so the admin is asked to enter it again.
        return ""
