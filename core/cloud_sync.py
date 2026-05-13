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
    export_settings,
    get_all_settings,
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
            return Path(configured).expanduser()
        return default_onedrive_backup_path()
    if destination_type != BACKUP_DESTINATION_LOCAL and configured:
        return Path(configured).expanduser()
    return None


def resolve_cloud_backup_destination_from_config(config: dict | None = None) -> Path | None:
    """Resolve a cloud backup destination from backup_config.json data."""

    config = config or load_backup_config()
    destination_type = config.get("backup_destination_type")
    configured = str(config.get("backup_destination_custom_path") or "").strip()
    if destination_type == BACKUP_DESTINATION_ONEDRIVE:
        if configured:
            return Path(configured).expanduser()
        return default_onedrive_backup_path()
    if destination_type != BACKUP_DESTINATION_LOCAL and configured:
        return Path(configured).expanduser()
    return None


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
    destination.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    db_backup_copied: str | None = None
    latest_db_backup = _latest_db_backup()
    if latest_db_backup is None:
        warnings.append("No database backup was available to sync.")
    else:
        db_target_dir = destination / "database"
        db_target_dir.mkdir(parents=True, exist_ok=True)
        db_target = db_target_dir / latest_db_backup.name
        shutil.copy2(latest_db_backup, db_target)
        db_backup_copied = str(db_target)

    sidecars_copied = _copy_training_sidecars(destination / "sidecars")

    synced_at = datetime.now(timezone.utc).isoformat()
    set_setting("cloud_backup_last_sync_at", synced_at)

    settings_path = destination / "settings.json"
    export_settings(settings_path)
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
        settings_exported=str(settings_path),
        synced_at=synced_at,
        warnings=tuple(warnings),
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
            for table in (
                "tag_categories",
                "tags",
                "tag_lifecycle_metadata",
                "characters",
                "entry_character_turns",
                "system_prompt_templates",
            ):
                if table in table_names:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
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
