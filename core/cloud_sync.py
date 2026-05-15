"""Cloud backup sync helpers.

Cloud sync is intentionally batch-oriented: LoreForge keeps working data local
during a session, then mirrors backups and portable metadata on demand or at
process shutdown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3

from core.db import get_db_path
from core.db_backups import (
    DB_BACKUP_PREFIX,
    DB_BACKUP_SUFFIX,
    get_db_backup_dir,
)
from core.platform import default_onedrive_backup_path, detect_onedrive_path
from core.preferences import (
    import_settings,
    load_preferences,
    set_setting,
)
from core.storage import APP_ROOT, TRAINING_DATA_DIR


BACKUP_DESTINATION_LOCAL = "local"
BACKUP_DESTINATION_ONEDRIVE = "onedrive"
BACKUP_DESTINATION_GOOGLE_DRIVE = "google_drive"
BACKUP_DESTINATION_DROPBOX = "dropbox"
BACKUP_DESTINATION_ICLOUD_DRIVE = "icloud_drive"
BACKUP_DESTINATION_BOX = "box"
BACKUP_DESTINATION_CUSTOM = "custom"
BACKUP_DESTINATION_TYPES = {
    BACKUP_DESTINATION_LOCAL,
    BACKUP_DESTINATION_ONEDRIVE,
    BACKUP_DESTINATION_GOOGLE_DRIVE,
    BACKUP_DESTINATION_DROPBOX,
    BACKUP_DESTINATION_ICLOUD_DRIVE,
    BACKUP_DESTINATION_BOX,
    BACKUP_DESTINATION_CUSTOM,
}

BACKUP_CONFIG_FILE = APP_ROOT / "backup_config.json"
BACKUP_CONFIG_KEYS = {
    "backup_destination_type",
    "backup_destination_custom_path",
    "cloud_backup_last_sync_at",
}
LOREFORGE_CLOUD_BACKUP_SUBDIR = Path("LoreForge Lite") / "backups"
_USER_METADATA_COUNT_QUERIES = {
    "tag_categories": "SELECT COUNT(*) FROM tag_categories",
    "tags": "SELECT COUNT(*) FROM tags",
    "tag_lifecycle_metadata": "SELECT COUNT(*) FROM tag_lifecycle_metadata",
    "characters": "SELECT COUNT(*) FROM characters",
    "entry_character_turns": "SELECT COUNT(*) FROM entry_character_turns",
    "system_prompt_templates": "SELECT COUNT(*) FROM system_prompt_templates",
}


@dataclass(frozen=True)
class CloudSyncResult:
    ok: bool
    message: str
    destination_path: str | None = None
    db_backup_copied: str | None = None
    sidecars_copied: int = 0
    settings_exported: str | None = None
    synced_at: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CloudRestoreResult:
    ok: bool
    message: str
    settings_imported: bool = False
    db_restored: bool = False
    restored_db_path: str | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)


def save_backup_config_from_settings(settings: dict | None = None) -> None:
    """Persist only cloud-destination settings outside the DB."""

    settings = settings or load_preferences()
    data = {
        key: settings.get(key, "")
        for key in BACKUP_CONFIG_KEYS
        if key in settings
    }
    BACKUP_CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_backup_config() -> dict:
    """Return the app-root backup config, or an empty dict if unavailable."""

    try:
        data = json.loads(BACKUP_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_cloud_backup_destination(settings: dict | None = None) -> Path | None:
    """Resolve the configured cloud backup folder, if cloud sync is enabled."""

    settings = settings or load_preferences()
    destination_type = settings.get(
        "backup_destination_type",
        BACKUP_DESTINATION_LOCAL,
    )
    configured = str(settings.get("backup_destination_custom_path") or "").strip()
    if destination_type == BACKUP_DESTINATION_ONEDRIVE:
        if configured:
            return cloud_backup_destination_path(Path(configured).expanduser())
        return default_onedrive_backup_path()
    if destination_type != BACKUP_DESTINATION_LOCAL and configured:
        return cloud_backup_destination_path(Path(configured).expanduser())
    return None


def resolve_cloud_backup_destination_from_config(config: dict | None = None) -> Path | None:
    """Resolve a cloud backup destination from backup_config.json data."""

    config = config or load_backup_config()
    destination_type = config.get("backup_destination_type")
    configured = str(config.get("backup_destination_custom_path") or "").strip()
    if destination_type == BACKUP_DESTINATION_ONEDRIVE:
        if configured:
            return cloud_backup_destination_path(Path(configured).expanduser())
        return default_onedrive_backup_path()
    if destination_type != BACKUP_DESTINATION_LOCAL and configured:
        return cloud_backup_destination_path(Path(configured).expanduser())
    return None


def cloud_backup_destination_path(sync_root: str | Path) -> Path:
    """Return LoreForge Lite's backup subfolder inside a provider sync root."""

    root = Path(sync_root).expanduser()
    root_tail = tuple(part.casefold() for part in root.parts[-2:])
    expected_tail = tuple(
        part.casefold()
        for part in LOREFORGE_CLOUD_BACKUP_SUBDIR.parts
    )
    if root_tail == expected_tail:
        return root
    return root / LOREFORGE_CLOUD_BACKUP_SUBDIR


def detect_cloud_sync_provider_for_path(path: str | Path) -> str | None:
    """Detect common cloud sync folders from a filesystem path."""

    raw_path = str(path or "").strip()
    if not raw_path:
        return None
    candidate = Path(raw_path).expanduser()
    onedrive_env = os.environ.get("ONEDRIVE")
    if onedrive_env and _path_is_inside(candidate, Path(onedrive_env).expanduser()):
        return "OneDrive"
    onedrive_path = detect_onedrive_path()
    if onedrive_path and _path_is_inside(candidate, onedrive_path):
        return "OneDrive"

    lowered = str(candidate).lower()
    for marker, provider in (
        ("google drive", "Google Drive"),
        ("dropbox", "Dropbox"),
        ("icloud", "iCloud Drive"),
        ("box sync", "Box"),
    ):
        if marker in lowered:
            return provider
    return None


def sync_configured_backups_to_cloud() -> CloudSyncResult:
    """Sync backups to the configured cloud destination, returning a status."""

    try:
        settings = load_preferences()
        destination = resolve_cloud_backup_destination(settings)
        if destination is None:
            if settings.get("backup_destination_type") == BACKUP_DESTINATION_LOCAL:
                return CloudSyncResult(
                    ok=True,
                    message="Cloud backup sync is not configured.",
                )
            return CloudSyncResult(
                ok=False,
                message="Cloud backup destination is not available.",
            )
        return sync_backups_to_cloud(destination)
    except Exception as exc:
        return CloudSyncResult(
            ok=False,
            message=f"Cloud backup sync failed: {exc}",
            errors=(str(exc),),
        )


def sync_backups_to_cloud(destination_path: str | Path) -> CloudSyncResult:
    """Mirror latest local backups and portable metadata to destination_path."""

    destination = Path(destination_path).expanduser().resolve()
    warnings: list[str] = []
    warnings.extend(_cleanup_stale_staging_dirs(destination))
    staging = _new_staging_destination(destination)

    try:
        staging.mkdir(parents=True)

        db_backup_copied: str | None = None
        latest_db_backup = _latest_db_backup()
        if latest_db_backup is None:
            warnings.append("No database backup was available to sync.")
        else:
            db_target_dir = staging / "database"
            db_target_dir.mkdir(parents=True, exist_ok=True)
            db_target = db_target_dir / latest_db_backup.name
            shutil.copy2(latest_db_backup, db_target)
            db_backup_copied = str(destination / "database" / latest_db_backup.name)

        sidecars_copied = _copy_training_sidecars(staging / "sidecars")

        synced_at = datetime.now(timezone.utc).isoformat()
        settings_path = staging / "settings.json"
        _write_settings_snapshot(settings_path, synced_at)

        warnings.extend(_publish_staged_cloud_sync(staging, destination))
        set_setting("cloud_backup_last_sync_at", synced_at)
        save_backup_config_from_settings(load_preferences())

        return CloudSyncResult(
            ok=True,
            message=(
                f"Cloud backup sync complete. Copied {sidecars_copied} sidecar"
                f"{'' if sidecars_copied == 1 else 's'}."
            ),
            destination_path=str(destination),
            db_backup_copied=db_backup_copied,
            sidecars_copied=sidecars_copied,
            settings_exported=str(destination / "settings.json"),
            synced_at=synced_at,
            warnings=tuple(warnings),
        )
    except Exception as exc:
        cleanup_warning = _remove_path(staging)
        errors = [str(exc)]
        if cleanup_warning:
            errors.append(cleanup_warning)
        return CloudSyncResult(
            ok=False,
            message=f"Cloud backup sync failed: {exc}",
            destination_path=str(destination),
            warnings=tuple(warnings),
            errors=tuple(errors),
        )


def cloud_backup_has_restore_data(destination_path: str | Path) -> bool:
    """Return whether a cloud destination contains restorable LoreForge data."""

    destination = Path(destination_path).expanduser()
    if (destination / "settings.json").exists():
        return True
    return _latest_cloud_db_backup(destination) is not None


def local_database_is_fresh(db_path: str | Path | None = None) -> bool:
    """Return True when local DB is absent or has no user metadata yet."""

    path = Path(db_path).expanduser() if db_path is not None else get_db_path()
    if not path.exists() or path.stat().st_size == 0:
        return True

    try:
        conn = sqlite3.connect(str(path))
        try:
            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not table_names:
                return True
            for table in _USER_METADATA_COUNT_QUERIES:
                if table in table_names:
                    count = _table_row_count(conn, table)
                    if count:
                        return False
            return True
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def get_cloud_restore_candidate() -> Path | None:
    """Return a configured restorable cloud folder for a fresh local DB."""

    if not local_database_is_fresh():
        return None
    destination = resolve_cloud_backup_destination_from_config()
    if destination is None or not cloud_backup_has_restore_data(destination):
        return None
    return destination


def restore_cloud_backup(destination_path: str | Path) -> CloudRestoreResult:
    """Restore settings and the latest DB backup from a cloud destination."""

    destination = Path(destination_path).expanduser()
    errors: list[str] = []
    settings_imported = False
    db_restored = False
    restored_db_path: str | None = None

    latest_db_backup = _latest_cloud_db_backup(destination)
    if latest_db_backup is not None:
        try:
            db_path = get_db_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(latest_db_backup, db_path)
            db_restored = True
            restored_db_path = str(db_path)
        except Exception as exc:
            errors.append(f"Database restore failed: {exc}")

    settings_path = destination / "settings.json"
    if settings_path.exists():
        try:
            import_settings(settings_path)
            save_backup_config_from_settings(load_preferences())
            settings_imported = True
        except Exception as exc:
            errors.append(f"Settings restore failed: {exc}")

    if errors:
        return CloudRestoreResult(
            ok=False,
            message="Cloud restore did not complete.",
            settings_imported=settings_imported,
            db_restored=db_restored,
            restored_db_path=restored_db_path,
            errors=tuple(errors),
        )
    if not settings_imported and not db_restored:
        return CloudRestoreResult(
            ok=False,
            message="No restorable cloud backup data was found.",
        )
    return CloudRestoreResult(
        ok=True,
        message="Cloud backup restored.",
        settings_imported=settings_imported,
        db_restored=db_restored,
        restored_db_path=restored_db_path,
    )


def _latest_db_backup() -> Path | None:
    backup_dir = get_db_backup_dir()
    return _latest_backup_file(backup_dir)


def _table_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Return a row count for one whitelisted user-metadata table."""

    try:
        query = _USER_METADATA_COUNT_QUERIES[table]
    except KeyError as exc:
        raise ValueError(f"Unsupported metadata table: {table}") from exc
    row = conn.execute(query).fetchone()
    return int(row[0]) if row is not None else 0


def _write_settings_snapshot(path: Path, synced_at: str) -> None:
    """Write a settings export that includes the sync timestamp being published."""

    settings = load_preferences()
    settings["cloud_backup_last_sync_at"] = synced_at
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _new_staging_destination(destination: Path) -> Path:
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    base = parent / f".{destination.name}.staging-{os.getpid()}-{stamp}"
    if not base.exists():
        return base
    index = 1
    while True:
        candidate = parent / f"{base.name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _cleanup_stale_staging_dirs(destination: Path) -> list[str]:
    parent = destination.parent
    if not parent.exists():
        return []
    warnings: list[str] = []
    for path in parent.glob(f".{destination.name}.staging-*"):
        warning = _remove_path(path)
        if warning:
            warnings.append(warning)
    return warnings


def _publish_staged_cloud_sync(staging: Path, destination: Path) -> list[str]:
    """Publish a completed staging directory without losing the prior sync."""

    warnings: list[str] = []
    previous = _previous_destination_path(destination)
    if previous.exists():
        warning = _remove_path(previous)
        if warning:
            warnings.append(warning)

    had_previous = destination.exists()
    if had_previous:
        destination.rename(previous)

    try:
        staging.rename(destination)
    except Exception as exc:
        if had_previous and previous.exists() and not destination.exists():
            try:
                previous.rename(destination)
            except Exception as restore_exc:
                raise RuntimeError(
                    f"Cloud sync publish failed: {exc}; restoring previous sync "
                    f"also failed: {restore_exc}"
                ) from exc
        raise

    if had_previous and previous.exists():
        warning = _remove_path(previous)
        if warning:
            warnings.append(warning)
    return warnings


def _previous_destination_path(destination: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return destination.parent / f".{destination.name}.previous-{os.getpid()}-{stamp}"


def _remove_path(path: Path) -> str | None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    except Exception as exc:
        return f"Could not remove {path}: {exc}"
    return None


def _path_is_inside(path: Path, possible_parent: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(possible_parent.expanduser().resolve())
        return True
    except (OSError, ValueError):
        return False


def _latest_cloud_db_backup(destination: Path) -> Path | None:
    return _latest_backup_file(destination / "database")


def _latest_backup_file(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    backups = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.startswith(DB_BACKUP_PREFIX)
            and path.suffix.lower() == DB_BACKUP_SUFFIX
        ),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    return backups[0] if backups else None


def _copy_training_sidecars(target_root: Path) -> int:
    target_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    if not TRAINING_DATA_DIR.exists():
        return copied

    for sidecar in TRAINING_DATA_DIR.rglob("*.registry.json"):
        if not sidecar.is_file():
            continue
        relative = sidecar.relative_to(TRAINING_DATA_DIR)
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sidecar, target)
        copied += 1
    return copied
