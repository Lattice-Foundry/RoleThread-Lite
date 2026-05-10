import os
import sqlite3

import pytest

from core import db_backups


def _create_sqlite_db(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, slug TEXT NOT NULL)")
        conn.execute("INSERT INTO tags (slug) VALUES ('slow_burn')")
        conn.commit()
    finally:
        conn.close()


def test_create_db_backup_creates_valid_sqlite_backup(tmp_path):
    db_path = tmp_path / "loreforge.db"
    backup_root = tmp_path / "backups"
    _create_sqlite_db(db_path)

    backup_path = db_backups.create_db_backup(
        db_path=db_path,
        backup_root=backup_root,
    )

    assert backup_path.exists()
    assert backup_path.parent == backup_root / "database"
    assert backup_path.name.startswith("loreforge_db_")
    assert backup_path.suffix == ".sqlite"

    conn = sqlite3.connect(backup_path)
    try:
        rows = conn.execute("SELECT slug FROM tags").fetchall()
    finally:
        conn.close()
    assert rows == [("slow_burn",)]


def test_create_db_backup_retains_latest_three_and_ignores_unrelated_files(tmp_path):
    db_path = tmp_path / "loreforge.db"
    backup_root = tmp_path / "backups"
    backup_dir = backup_root / "database"
    _create_sqlite_db(db_path)

    unrelated = backup_dir / "notes.txt"
    backup_dir.mkdir(parents=True)
    unrelated.write_text("keep me", encoding="utf-8")

    for index in range(5):
        backup_path = db_backups.create_db_backup(
            db_path=db_path,
            backup_root=backup_root,
        )
        timestamp = 1_700_000_000 + index
        os.utime(backup_path, (timestamp, timestamp))

    backups = sorted(backup_dir.glob("loreforge_db_*.sqlite"))

    assert len(backups) == 3
    assert unrelated.exists()


def test_prune_db_backups_deletes_only_db_backup_files(tmp_path):
    backup_dir = tmp_path / "db"
    backup_dir.mkdir()
    old = backup_dir / "loreforge_db_20260101_120000.sqlite"
    new = backup_dir / "loreforge_db_20260101_120001.sqlite"
    unrelated = backup_dir / "other.sqlite"
    old.write_text("old", encoding="utf-8")
    new.write_text("new", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))

    db_backups.prune_db_backups(backup_dir, keep_count=1)

    assert not old.exists()
    assert new.exists()
    assert unrelated.exists()


def test_create_db_backup_fails_for_missing_database(tmp_path):
    with pytest.raises(FileNotFoundError):
        db_backups.create_db_backup(
            db_path=tmp_path / "missing.db",
            backup_root=tmp_path / "backups",
        )
