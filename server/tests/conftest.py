import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A fresh app with an empty database in a temp directory; background jobs are not started."""
    monkeypatch.setenv("TRIPATLAS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRIPATLAS_WEB_DIR", "")
    from tripatlas import config
    from tripatlas.auth.security import login_throttle
    from tripatlas.db import session
    from tripatlas.services import secrets

    for f in (config.get_config, session.get_engine, session._factory, secrets._fernet):
        f.cache_clear()
    login_throttle._fails.clear()
    session.migrate()
    from tripatlas.main import create_app

    with TestClient(create_app(start_jobs=False)) as c:
        yield c
