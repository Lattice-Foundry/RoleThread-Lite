"""Dataset working-copy helpers."""
from dataclasses import dataclass, replace
from pathlib import Path
import re
import shutil

from core.registry_sidecar import read_sidecar, sidecar_path_for_dataset, write_sidecar
from core.storage import get_default_training_data_dir

_DATASET_STEM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class DatasetWorkingCopyResult:
    """Result of preparing a protected working copy for a foreign dataset."""

    original_path: str
    working_path: str
    created: bool
    sidecar_copied: bool = False
    sidecar_path: str | None = None


@dataclass(frozen=True)
class DatasetRenameResult:
    """Result of renaming a trusted working-copy dataset."""

    old_path: str
    new_path: str
    old_sidecar_path: str | None = None
    new_sidecar_path: str | None = None
    sidecar_renamed: bool = False


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

    target_path = _unique_dataset_target_path(
        target_dir,
        source_path.stem,
        source_path.suffix,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
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


def rename_working_dataset(
    dataset_path: str | Path,
    new_stem: str,
    *,
    working_dir: str | Path | None = None,
) -> DatasetRenameResult:
    """Rename a canonical training_data dataset folder, JSONL, and sidecar."""

    source_path = Path(dataset_path).resolve()
    target_dir = Path(working_dir).resolve() if working_dir else get_default_training_data_dir().resolve()
    safe_stem = _validate_dataset_stem(new_stem)
    _validate_rename_source(source_path, target_dir)

    old_folder = source_path.parent
    old_sidecar = sidecar_path_for_dataset(source_path)
    sidecar_exists = old_sidecar.exists()
    target_folder = target_dir / safe_stem
    target_path = target_folder / f"{safe_stem}{source_path.suffix}"
    target_sidecar = sidecar_path_for_dataset(target_path)

    if safe_stem == source_path.stem:
        return DatasetRenameResult(
            old_path=str(source_path),
            new_path=str(source_path),
            old_sidecar_path=str(old_sidecar) if sidecar_exists else None,
            new_sidecar_path=str(old_sidecar) if sidecar_exists else None,
            sidecar_renamed=False,
        )
    if target_folder.exists():
        raise FileExistsError(f"Dataset folder already exists: {target_folder}")

    updated_registry = None
    if sidecar_exists:
        registry = read_sidecar(old_sidecar)
        updated_registry = replace(
            registry,
            dataset_info=replace(
                registry.dataset_info,
                filename=target_path.name,
            ),
        )

    folder_renamed = False
    dataset_renamed = False
    sidecar_renamed = False
    try:
        old_folder.rename(target_folder)
        folder_renamed = True

        moved_dataset = target_folder / source_path.name
        moved_dataset.rename(target_path)
        dataset_renamed = True

        if sidecar_exists:
            moved_sidecar = target_folder / old_sidecar.name
            moved_sidecar.rename(target_sidecar)
            sidecar_renamed = True
            if updated_registry is not None:
                _write_sidecar_atomically(updated_registry, target_sidecar)

        return DatasetRenameResult(
            old_path=str(source_path),
            new_path=str(target_path),
            old_sidecar_path=str(old_sidecar) if sidecar_renamed else None,
            new_sidecar_path=str(target_sidecar) if sidecar_renamed else None,
            sidecar_renamed=sidecar_renamed,
        )
    except Exception:
        _rollback_rename(
            source_path=source_path,
            old_sidecar=old_sidecar,
            target_folder=target_folder,
            target_path=target_path,
            target_sidecar=target_sidecar,
            folder_renamed=folder_renamed,
            dataset_renamed=dataset_renamed,
            sidecar_renamed=sidecar_renamed,
        )
        raise


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
    return _unique_dataset_target_path(
        target_dir,
        source_path.stem,
        source_path.suffix,
    )


def _validate_dataset_stem(value: str) -> str:
    stem = str(value or "").strip()
    if not stem:
        raise ValueError("Dataset name cannot be empty.")
    if not _DATASET_STEM_RE.fullmatch(stem):
        raise ValueError(
            "Dataset name may only contain letters, numbers, dashes, and underscores."
        )
    return stem


def _validate_rename_source(source_path: Path, target_dir: Path) -> None:
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Dataset file does not exist: {source_path}")
    if source_path.suffix.lower() != ".jsonl":
        raise ValueError("Only JSONL datasets can be renamed.")
    if not _is_relative_to(source_path, target_dir):
        raise ValueError("Only trusted working-copy datasets can be renamed.")
    if source_path.parent.parent != target_dir or source_path.parent.name != source_path.stem:
        raise ValueError(
            "Only canonical training_data/<name>/<name>.jsonl datasets can be renamed."
        )


def _write_sidecar_atomically(registry, path: Path) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        write_sidecar(registry, temp_path)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _rollback_rename(
    *,
    source_path: Path,
    old_sidecar: Path,
    target_folder: Path,
    target_path: Path,
    target_sidecar: Path,
    folder_renamed: bool,
    dataset_renamed: bool,
    sidecar_renamed: bool,
) -> None:
    if sidecar_renamed and target_sidecar.exists():
        target_sidecar.rename(target_folder / old_sidecar.name)
    if dataset_renamed and target_path.exists():
        target_path.rename(target_folder / source_path.name)
    if folder_renamed and target_folder.exists():
        target_folder.rename(source_path.parent)


def _unique_dataset_target_path(target_dir: Path, source_stem: str, source_suffix: str) -> Path:
    counter = 1
    while True:
        dataset_stem = source_stem if counter == 1 else f"{source_stem}_copy-{counter}"
        target = target_dir / dataset_stem / f"{dataset_stem}{source_suffix}"
        if (
            not target.parent.exists()
            and not target.exists()
            and not sidecar_path_for_dataset(target).exists()
        ):
            return target
        counter += 1


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
