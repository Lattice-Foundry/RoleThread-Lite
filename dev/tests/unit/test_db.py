import sqlite3

from sqlalchemy import event

from core import db


def test_sqlite_foreign_key_listener_is_registered():
    assert event.contains(db.engine, "connect", db._enable_foreign_keys)


def test_enable_foreign_keys_sets_sqlite_pragma():
    connection = sqlite3.connect(":memory:")
    try:
        db._enable_foreign_keys(connection, None)
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert enabled == 1
