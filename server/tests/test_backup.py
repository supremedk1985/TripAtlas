import sqlite3


def test_snapshot_is_a_consistent_copy_and_old_ones_are_pruned(client, monkeypatch):
    from tripatlas.config import get_config
    from tripatlas.services import backup

    cfg = get_config()
    folder = cfg.data_dir / "backups"
    folder.mkdir(exist_ok=True)
    for day in range(1, 10):  # nine old snapshots
        (folder / f"tripatlas-2026-01-0{day}.db").write_bytes(b"old")
    target = backup.make_snapshot(force=True)
    assert target is not None and target.exists()
    tables = {r[0] for r in sqlite3.connect(target).execute("select name from sqlite_master where type='table'")}
    assert {"users", "positions", "trips"} <= tables
    assert len(list(folder.glob("tripatlas-*.db"))) == cfg.backup_keep
    assert backup.make_snapshot() is None, "not due again right away"
