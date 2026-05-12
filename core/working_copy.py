"""Dataset working-copy helpers."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil

from core.registry_sidecar import sidecar_path_for_dataset
from core.storage import get_default_training_data_dir


@dataclass(frozen=True)
class DatasetWorkingCopyResult:
    """Result of preparing a protected working copy for a foreign dataset."""

    original_path: str
    working_path: str
    created: bool
    sidecar_copied: bool = False
    sidecar_path: str | None = None


def create_dataset_working_copy(
    dataset_path: str | Path,
    *,
    working_dir: str | Path | None = None,
) -> DatasetWorkingCopyResult:
    """Copy a foreign dataset and sibling sidecar into the working data folder."""

    source_path = Path(dataset_path).resolve()
    target_dir = Path(working_dir).resolve() if working_dir else get_default_training_data_dir().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    canonical_path = canonical_training_dataset_path(source_path, working_dir=target_dir)
    if _is_relative_to(source_path, target_dir) and source_path == canonical_path:
        return DatasetWorkingCopyResult(
            original_path=str(source_path),
            working_path=str(source_path),
            created=False,
        )

    dataset_dir = target_dir / source_path.stem
    dataset_dir.mkdir(parents=True, exist_ok=True)
    target_path = _unique_dataset_target_path(dataset_dir / source_path.name)
    shutil.copy2(source_path, target_path)

    source_sidecar = sidecar_path_for_dataset(source_path)
    sidecar_copied = False
    target_sidecar_path: Path | None = None
    if source_sidecar.exists():
        target_sidecar_path = sidecar_path_for_dataset(target_path)
        shutil.copy2(source_sidecar, target_sidecar_path)
        sidecar_copied = True

    return DatasetWorkingCopyResult(
        original_path=str(source_path),
        working_path=str(target_path),
        created=True,
        sidecar_copied=sidecar_copied,
        sidecar_path=str(target_sidecar_path) if target_sidecar_path else None,
    )


def migrate_training_dataset_to_subfolder(
    dataset_path: str | Path,
    *,
    working_dir: str | Path | None = None,
) -> DatasetWorkingCopyResult:
    """Move a flat training_data dataset into its canonical per-dataset folder."""

    source_path = Path(dataset_path).resolve()
    target_dir = Path(working_dir).resolve() if working_dir else get_default_training_data_dir().resolve()
    if not _is_relative_to(source_path, target_dir):
        return DatasetWorkingCopyResult(
            original_path=str(source_path),
            working_path=str(source_path),
            created=False,
        )

    canonical_path = canonical_training_dataset_path(source_path, working_dir=target_dir)
    if canonical_path == source_path:
        return DatasetWorkingCopyResult(
            original_path=str(source_path),
            working_path=str(source_path),
            created=False,
        )

    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(canonical_path))

    source_sidecar = sidecar_path_for_dataset(source_path)
    sidecar_moved = False
    target_sidecar_path: Path | None = None
    if source_sidecar.exists():
        target_sidecar_path = sidecar_path_for_dataset(canonical_path)
        shutil.move(str(source_sidecar), str(target_sidecar_path))
        sidecar_moved = True

    return DatasetWorkingCopyResult(
        original_path=str(source_path),
        working_path=str(canonical_path),
        created=True,
        sidecar_copied=sidecar_moved,
        sidecar_path=str(target_sidecar_path) if target_sidecar_path else None,
    )


def canonical_training_dataset_path(
    dataset_path: str | Path,
    *,
    working_dir: str | Path | None = None,
) -> Path:
    """Return the canonical per-dataset path for files inside training_data."""

    source_path = Path(dataset_path).resolve()
    target_dir = Path(working_dir).resolve() if working_dir else get_default_training_data_dir().resolve()
    if not _is_relative_to(source_path, target_dir):
        return source_path
    if source_path.parent == target_dir / source_path.stem:
        return source_path
    return _unique_dataset_target_path(target_dir / source_path.stem / source_path.name)


def _unique_target_path(candidate: Path) -> Path:
    if not candidate.exists():
        return candidate

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{candidate.stem}_{timestamp}"
    target = candidate.with_name(f"{stem}{candidate.suffix}")
    counter = 1
    while target.exists():
        target = candidate.with_name(f"{stem}_{counter:03d}{candidate.suffix}")
        counter += 1
    return target


def _unique_dataset_target_path(candidate: Path) -> Path:
    if not candidate.exists() and not sidecar_path_for_dataset(candidate).exists():
        return candidate

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{candidate.stem}_{timestamp}"
    target = candidate.with_name(f"{stem}{candidate.suffix}")
    counter = 1
    while target.exists() or sidecar_path_for_dataset(target).exists():
        target = candidate.with_name(f"{stem}_{counter:03d}{candidate.suffix}")
        counter += 1
    return target


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
