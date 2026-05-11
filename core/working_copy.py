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

    if _is_relative_to(source_path, target_dir):
        return DatasetWorkingCopyResult(
            original_path=str(source_path),
            working_path=str(source_path),
            created=False,
        )

    target_path = _unique_target_path(target_dir / source_path.name)
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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
