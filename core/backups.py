"""Local dataset backup helpers.

Backups are file-based, grouped by dataset stem, and pruned per dataset.
No UI or Streamlit behavior belongs here.
"""
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from core.preferences import load_preferences
from core.storage import get_backups_dir

_BACKUP_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{6})_")
_DEFAULT_KEEP_COUNT = 25
_MAX_KEEP_COUNT = 500


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "dataset"


def auto_backups_enabled(prefs: dict | None = None) -> bool:
    """Return whether protected mutations should create pre-write backups."""
    prefs = prefs or load_preferences()
    return bool(prefs.get("auto_backups_enabled", True))


def get_backup_root(prefs: dict | None = None) -> Path:
    """Return the configured backup root, creating it if needed."""
    prefs = prefs or load_preferences()
    configured = prefs.get("backup_directory") or str(get_backups_dir())
    backup_root = Path(configured).expanduser().resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    return backup_root


def get_backups_per_dataset(prefs: dict | None = None) -> int:
    """Return the configured retention count with a conservative clamp."""
    prefs = prefs or load_preferences()
    try:
        keep_count = int(prefs.get("backups_per_dataset", _DEFAULT_KEEP_COUNT))
    except (TypeError, ValueError):
        keep_count = _DEFAULT_KEEP_COUNT
    return max(1, min(keep_count, _MAX_KEEP_COUNT))


def _backup_sort_key(path: Path) -> tuple[datetime, int, str]:
    try:
        created_ns = path.stat().st_ctime_ns
    except OSError:
        created_ns = 0
    match = _BACKUP_TIMESTAMP_RE.match(path.name)
    if not match:
        return datetime.min, created_ns, path.name
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S"), created_ns, path.name
    except ValueError:
        return datetime.min, created_ns, path.name


def prune_dataset_backups(dataset_backup_dir: Path, keep_count: int) -> None:
    """Keep the newest keep_count JSONL backups and delete older ones."""
    keep_count = max(1, keep_count)
    backups = sorted(
        (
            path for path in dataset_backup_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".jsonl"
        ),
        key=_backup_sort_key,
        reverse=True,
    )
    for old_backup in backups[keep_count:]:
        try:
            old_backup.unlink()
        except OSError as exc:
            print(f"Warning: could not prune backup `{old_backup}`: {exc}")


def create_dataset_backup(dataset_path: str | Path, reason: str) -> Path | None:
    """Copy an existing dataset into the configured backup folder."""
    source = Path(dataset_path)
    if not source.exists() or not source.is_file():
        return None

    prefs = load_preferences()
    backup_dir = get_backup_root(prefs) / "datasets" / _safe_name(source.stem)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp_dt = datetime.now()
    timestamp = timestamp_dt.strftime("%Y-%m-%d_%H%M%S")
    reason_name = _safe_name(reason)
    backup_path = backup_dir / f"{timestamp}_{reason_name}.jsonl"
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / f"{timestamp}_{reason_name}_{counter:03d}.jsonl"
        counter += 1

    # Preserve bytes exactly, but timestamp the backup as the backup event.
    shutil.copyfile(source, backup_path)
    backup_time = timestamp_dt.timestamp()
    os.utime(backup_path, (backup_time, backup_time))
    try:
        prune_dataset_backups(backup_dir, get_backups_per_dataset(prefs))
    except Exception as exc:
        print(f"Warning: failed to prune dataset backups in {backup_dir}: {exc}")
    return backup_path
