"""RoleThread-specific diagnostics data for support surfaces.

This module intentionally stays independent from Streamlit and generated
diagnostics UI code. It observes existing local state without creating runtime
directories, running sync, or dumping environment/config data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
import json
from pathlib import Path
import sqlite3
import sys
from typing import Mapping

from core.platform import (
    PATH_SOURCE_PLATFORM_DEFAULT,
    PlatformPathResolution,
    detect_platform,
    get_platform_path_resolutions,
)
from core.product_log import PRODUCT_LOG_FILE_NAME, PRODUCT_LOG_PATH_ENV
from core.runtime import PythonRuntimeStatus, get_python_runtime_status
from core.storage import APP_DATA_DIR, APP_ROOT
from core.version import ROLETHREAD_VERSION


BACKUP_DESTINATION_LOCAL = "local"
BACKUP_DESTINATION_ONEDRIVE = "onedrive"
BACKUP_DESTINATION_GOOGLE_DRIVE = "google_drive"
BACKUP_DESTINATION_DROPBOX = "dropbox"
BACKUP_DESTINATION_ICLOUD_DRIVE = "icloud_drive"
BACKUP_DESTINATION_BOX = "box"
BACKUP_DESTINATION_CUSTOM = "custom"
BACKUP_CONFIG_FILE_NAME = "backup_config.json"
LITLAUNCH_REPORT_DIR = ".litlaunch/reports"
LITLAUNCH_RUNTIME_EVENT_LOG = ".litlaunch/runtime-events.log"

_CLOUD_PROVIDER_LABELS = {
    BACKUP_DESTINATION_LOCAL: "Local only",
    BACKUP_DESTINATION_ONEDRIVE: "OneDrive",
    BACKUP_DESTINATION_GOOGLE_DRIVE: "Google Drive",
    BACKUP_DESTINATION_DROPBOX: "Dropbox",
    BACKUP_DESTINATION_ICLOUD_DRIVE: "iCloud Drive",
    BACKUP_DESTINATION_BOX: "Box",
    BACKUP_DESTINATION_CUSTOM: "Custom",
}

_SENSITIVE_FIELD_MARKERS = (
    "secret",
    "token",
    "password",
    "credential",
    "apikey",
    "api_key",
)


@dataclass(frozen=True)
class ProductOverviewDiagnostics:
    rolethread_version: str
    python_version: str
    python_status: str
    python_message: str
    platform: str
    platform_support: str
    runtime_context: str
    streamlit_version: str
    litlaunch_version: str


@dataclass(frozen=True)
class ProductPathDiagnostics:
    label: str
    path: str
    exists: bool
    kind: str
    source: str = PATH_SOURCE_PLATFORM_DEFAULT
    platform_default: str | None = None


@dataclass(frozen=True)
class CloudBackupDiagnostics:
    status: str
    provider: str
    destination_path: str | None = None
    destination_exists: bool | None = None
    last_sync_at: str | None = None
    config_path: str | None = None
    config_exists: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupportArtifactDiagnostics:
    product_log_path: str
    product_log_env_var: str
    runtime_event_log_path: str
    reports_dir: str
    reports_dir_exists: bool


@dataclass(frozen=True)
class DataHealthDiagnostics:
    database_path: str
    database_exists: bool
    database_readable: bool
    preferences_path: str
    preferences_exists: bool
    preferences_readable: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductDiagnostics:
    overview: ProductOverviewDiagnostics
    paths: tuple[ProductPathDiagnostics, ...]
    cloud_backup: CloudBackupDiagnostics
    support_artifacts: SupportArtifactDiagnostics
    data_health: DataHealthDiagnostics
    privacy_notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "Product diagnostics include local filesystem paths for support.",
            "Raw environment variables, tokens, and cloud credentials are not collected.",
        )
    )


def collect_product_diagnostics(
    *,
    env: Mapping[str, str] | None = None,
    app_root: Path | None = None,
    app_data_dir: Path | None = None,
    frozen: bool | None = None,
    runtime_status: PythonRuntimeStatus | None = None,
) -> ProductDiagnostics:
    """Collect cheap RoleThread product diagnostics without mutating local state."""

    root = Path(app_root or APP_ROOT).resolve()
    data_dir = Path(app_data_dir or APP_DATA_DIR).expanduser()
    env_map = {} if env is None else dict(env)
    platform_info = detect_platform()
    python_status = runtime_status or get_python_runtime_status()
    path_resolutions = get_platform_path_resolutions(preferences=_read_preferences(data_dir))

    overview = ProductOverviewDiagnostics(
        rolethread_version=ROLETHREAD_VERSION,
        python_version=python_status.current_version,
        python_status=python_status.status_label,
        python_message=python_status.message,
        platform=platform_info.display_name,
        platform_support=platform_info.support_level,
        runtime_context=_runtime_context(frozen=frozen),
        streamlit_version=_package_version("streamlit"),
        litlaunch_version=_package_version("litlaunch"),
    )

    paths = _collect_path_diagnostics(path_resolutions)
    backup_config = _read_backup_config(data_dir)
    cloud_backup = _collect_cloud_backup_diagnostics(data_dir, backup_config)
    support_artifacts = _collect_support_artifacts(
        root=root,
        data_dir=data_dir,
        env=env_map,
    )
    data_health = _collect_data_health(
        database_path=data_dir / "rolethread.db",
        preferences_path=data_dir / "preferences.json",
    )

    return ProductDiagnostics(
        overview=overview,
        paths=paths,
        cloud_backup=cloud_backup,
        support_artifacts=support_artifacts,
        data_health=data_health,
    )


def _collect_path_diagnostics(path_resolutions) -> tuple[ProductPathDiagnostics, ...]:
    rows = (
        ("App data", path_resolutions.app_data_root, "directory"),
        ("Workspace", path_resolutions.workspace_root, "directory"),
        ("Training data", path_resolutions.training_data_dir, "directory"),
        ("Imports", path_resolutions.imports_dir, "directory"),
        ("Exports", path_resolutions.exports_dir, "directory"),
        ("Backups", path_resolutions.backups_dir, "directory"),
        ("Logs", path_resolutions.logs_dir, "directory"),
        ("Cache", path_resolutions.cache_dir, "directory"),
        ("Database", path_resolutions.database_path, "file"),
        ("Preferences", path_resolutions.preferences_path, "file"),
    )
    return tuple(
        _path_diagnostics(label, resolution, kind)
        for label, resolution, kind in rows
    )


def _path_diagnostics(
    label: str,
    resolution: PlatformPathResolution,
    kind: str,
) -> ProductPathDiagnostics:
    return ProductPathDiagnostics(
        label=label,
        path=str(resolution.path),
        exists=resolution.path.exists(),
        kind=kind,
        source=resolution.source,
        platform_default=(
            str(resolution.platform_default)
            if resolution.source != PATH_SOURCE_PLATFORM_DEFAULT
            else None
        ),
    )


def _collect_cloud_backup_diagnostics(
    data_dir: Path,
    config: dict[str, object],
) -> CloudBackupDiagnostics:
    config_path = data_dir / BACKUP_CONFIG_FILE_NAME
    destination_type = str(
        config.get("backup_destination_type") or BACKUP_DESTINATION_LOCAL
    )
    configured_path = str(config.get("backup_destination_custom_path") or "").strip()
    last_sync = str(config.get("cloud_backup_last_sync_at") or "").strip() or None
    provider = _CLOUD_PROVIDER_LABELS.get(destination_type, "Unknown")
    warnings: list[str] = []

    destination_path = configured_path or None
    destination_exists = None
    if destination_path:
        destination = Path(destination_path).expanduser()
        destination_exists = destination.exists()
    elif destination_type != BACKUP_DESTINATION_LOCAL:
        warnings.append("Cloud backup is configured but no destination path is stored.")

    status = "local_only"
    if destination_type != BACKUP_DESTINATION_LOCAL:
        status = "configured" if destination_path else "needs_attention"

    return CloudBackupDiagnostics(
        status=status,
        provider=provider,
        destination_path=destination_path,
        destination_exists=destination_exists,
        last_sync_at=last_sync,
        config_path=str(config_path),
        config_exists=config_path.exists(),
        warnings=tuple(warnings),
    )


def _collect_support_artifacts(
    *,
    root: Path,
    data_dir: Path,
    env: Mapping[str, str],
) -> SupportArtifactDiagnostics:
    product_log_path = _safe_path_from_env(env, PRODUCT_LOG_PATH_ENV)
    if product_log_path is None:
        product_log_path = data_dir / "logs" / PRODUCT_LOG_FILE_NAME

    reports_dir = root / LITLAUNCH_REPORT_DIR
    return SupportArtifactDiagnostics(
        product_log_path=str(product_log_path),
        product_log_env_var=PRODUCT_LOG_PATH_ENV,
        runtime_event_log_path=str(root / LITLAUNCH_RUNTIME_EVENT_LOG),
        reports_dir=str(reports_dir),
        reports_dir_exists=reports_dir.exists(),
    )


def _collect_data_health(
    *,
    database_path: Path,
    preferences_path: Path,
) -> DataHealthDiagnostics:
    warnings: list[str] = []
    database_readable = False
    if database_path.exists():
        try:
            with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
                connection.execute("PRAGMA schema_version").fetchone()
            database_readable = True
        except sqlite3.Error:
            warnings.append("Database exists but could not be opened read-only.")

    preferences_readable = False
    if preferences_path.exists():
        try:
            json.loads(preferences_path.read_text(encoding="utf-8"))
            preferences_readable = True
        except Exception:
            warnings.append("Preferences file exists but could not be read as JSON.")

    return DataHealthDiagnostics(
        database_path=str(database_path),
        database_exists=database_path.exists(),
        database_readable=database_readable,
        preferences_path=str(preferences_path),
        preferences_exists=preferences_path.exists(),
        preferences_readable=preferences_readable,
        warnings=tuple(warnings),
    )


def _read_backup_config(data_dir: Path) -> dict[str, object]:
    config_path = data_dir / BACKUP_CONFIG_FILE_NAME
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return _safe_public_config(data)


def _read_preferences(data_dir: Path) -> dict[str, object]:
    database_path = data_dir / "rolethread.db"
    if database_path.is_file():
        try:
            return _read_preferences_from_db(database_path)
        except sqlite3.Error:
            return {}

    preferences_path = data_dir / "preferences.json"
    if not preferences_path.is_file():
        return {}
    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return _safe_public_config(data)


def _read_preferences_from_db(database_path: Path) -> dict[str, object]:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT key, value FROM app_settings").fetchall()

    preferences: dict[str, object] = {}
    for key, raw_value in rows:
        if not isinstance(key, str) or _is_sensitive_key(key):
            continue
        try:
            preferences[key] = json.loads(raw_value)
        except Exception:
            preferences[key] = raw_value
    return preferences


def _safe_public_config(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        return {}
    return {
        str(key): value
        for key, value in data.items()
        if isinstance(key, str) and not _is_sensitive_key(key)
    }


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").casefold()
    return any(marker in normalized for marker in _SENSITIVE_FIELD_MARKERS)


def _safe_path_from_env(env: Mapping[str, str], key: str) -> Path | None:
    value = str(env.get(key) or "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def _runtime_context(*, frozen: bool | None = None) -> str:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    return "packaged" if is_frozen else "source"


def _package_version(distribution_name: str) -> str:
    try:
        return metadata.version(distribution_name)
    except metadata.PackageNotFoundError:
        return "not installed"
