"""SQLite database backup helpers.

DB backups protect registry and history mutations. They use SQLite's backup
API and keep a tiny rolling set separate from dataset JSONL backups.
"""
from datetime import datetime
from pathlib import Path
import sqlite3

from sqlalchemy.engine import Engine

from core.backups import get_backup_root
from core.db import engine as default_engine

DB_BACKUP_KEEP_COUNT = 3
DB_BACKUP_PREFIX = "rolethread_db_"
DB_BACKUP_SUFFIX = ".sqlite"


def _db_path_from_engine(engine: Engine) -> Path:
    """Return the filesystem path for a SQLite SQLAlchemy engine."""
    database = engine.url.database
    if not database or database == ":memory:":
        raise ValueError("SQLite database backup requires a file-backed database.")
    return Path(database).expanduser().resolve()


def get_db_backup_dir(backup_root: Path | None = None) -> Path:
    """Return the DB backup directory, creating it if needed."""
    root = backup_root or get_backup_root()
    backup_dir = Path(root) / "database"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _next_backup_path(backup_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{DB_BACKUP_PREFIX}{timestamp}{DB_BACKUP_SUFFIX}"
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / (
            f"{DB_BACKUP_PREFIX}{timestamp}_{counter:03d}{DB_BACKUP_SUFFIX}"
        )
        counter += 1
    return backup_path


def prune_db_backups(backup_dir: Path, keep_count: int = DB_BACKUP_KEEP_COUNT) -> None:
    """Keep the newest DB backups and delete older DB backup files."""
    keep_count = max(1, keep_count)
    backups = sorted(
        (
            path
            for path in Path(backup_dir).iterdir()
            if path.is_file()
            and path.name.startswith(DB_BACKUP_PREFIX)
            and path.suffix.lower() == DB_BACKUP_SUFFIX
        ),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    for old_backup in backups[keep_count:]:
        old_backup.unlink()


def create_db_backup(
    *,
    engine: Engine | None = None,
    db_path: str | Path | None = None,
    backup_root: Path | None = None,
) -> Path:
    """Create a SQLite backup and prune old DB backups."""
    source_path = (
        Path(db_path).expanduser().resolve()
        if db_path is not None
        else _db_path_from_engine(engine or default_engine)
    )
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    backup_dir = get_db_backup_dir(backup_root)
    backup_path = _next_backup_path(backup_dir)

    source_conn = sqlite3.connect(str(source_path))
    try:
        dest_conn = sqlite3.connect(str(backup_path))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    prune_db_backups(backup_dir, DB_BACKUP_KEEP_COUNT)
    return backup_path

