import json

from core.registry_sidecar import sidecar_path_for_dataset
from core.working_copy import (
    canonical_training_dataset_path,
    create_dataset_working_copy,
    migrate_training_dataset_to_subfolder,
)


def test_create_dataset_working_copy_copies_foreign_file_and_sidecar(tmp_path):
    source_dir = tmp_path / "source"
    working_dir = tmp_path / "working"
    source_dir.mkdir()
    source_path = source_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")
    source_sidecar = sidecar_path_for_dataset(source_path)
    source_sidecar.write_text('{"metadata": {}}', encoding="utf-8")

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is True
    assert result.original_path == str(source_path.resolve())
    assert result.working_path == str((working_dir / "dataset" / "dataset.jsonl").resolve())
    assert result.sidecar_copied is True
    assert result.sidecar_path == str((working_dir / "dataset" / "dataset.registry.json").resolve())
    assert (working_dir / "dataset" / "dataset.jsonl").read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")
    assert (working_dir / "dataset" / "dataset.registry.json").read_text(encoding="utf-8") == '{"metadata": {}}'
    assert source_path.exists()
    assert source_sidecar.exists()


def test_create_dataset_working_copy_copies_noncanonical_files_inside_working_dir(tmp_path):
    working_dir = tmp_path / "working"
    source_dir = working_dir / "dirty"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is True
    assert result.working_path == str((working_dir / "dataset" / "dataset.jsonl").resolve())
    assert source_path.exists()


def test_create_dataset_working_copy_does_not_copy_canonical_working_file(tmp_path):
    working_dir = tmp_path / "working"
    source_dir = working_dir / "dataset"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is False
    assert result.working_path == str(source_path.resolve())


def test_create_dataset_working_copy_uses_unique_folder_for_repeated_loads(tmp_path):
    source_dir = tmp_path / "source"
    working_dir = tmp_path / "working"
    source_dir.mkdir()
    working_dir.mkdir()
    source_path = source_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")
    dataset_dir = working_dir / "dataset"
    dataset_dir.mkdir()
    existing = dataset_dir / "dataset.jsonl"
    existing.write_text("existing\n", encoding="utf-8")

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is True
    assert result.working_path == str((working_dir / "dataset_copy-2" / "dataset_copy-2.jsonl").resolve())
    assert existing.read_text(encoding="utf-8") == "existing\n"
    assert (working_dir / "dataset_copy-2" / "dataset_copy-2.jsonl").read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")


def test_create_dataset_working_copy_increments_unique_folder_suffix(tmp_path):
    source_dir = tmp_path / "source"
    working_dir = tmp_path / "working"
    source_dir.mkdir()
    working_dir.mkdir()
    source_path = source_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")
    (working_dir / "dataset").mkdir()
    (working_dir / "dataset_copy-2").mkdir()

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is True
    assert result.working_path == str((working_dir / "dataset_copy-3" / "dataset_copy-3.jsonl").resolve())


def test_create_dataset_working_copy_repeated_loads_populate_matching_files(tmp_path):
    source_dir = tmp_path / "source"
    working_dir = tmp_path / "working"
    source_dir.mkdir()
    source_path = source_dir / "dirty_roles.jsonl"
    source_content = json.dumps({"messages": [], "tags": []}) + "\n"
    source_path.write_text(source_content, encoding="utf-8")
    source_sidecar = sidecar_path_for_dataset(source_path)
    source_sidecar.write_text('{"metadata": {"kind": "test"}}', encoding="utf-8")

    first = create_dataset_working_copy(source_path, working_dir=working_dir)
    second = create_dataset_working_copy(source_path, working_dir=working_dir)
    third = create_dataset_working_copy(source_path, working_dir=working_dir)

    expected_paths = [
        working_dir / "dirty_roles" / "dirty_roles.jsonl",
        working_dir / "dirty_roles_copy-2" / "dirty_roles_copy-2.jsonl",
        working_dir / "dirty_roles_copy-3" / "dirty_roles_copy-3.jsonl",
    ]
    assert [first.working_path, second.working_path, third.working_path] == [
        str(path.resolve()) for path in expected_paths
    ]
    for path in expected_paths:
        assert path.read_text(encoding="utf-8") == source_content
        assert sidecar_path_for_dataset(path).read_text(encoding="utf-8") == '{"metadata": {"kind": "test"}}'


def test_migrate_training_dataset_to_subfolder_moves_flat_file_and_sidecar(tmp_path):
    working_dir = tmp_path / "training_data"
    working_dir.mkdir()
    source_path = working_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")
    source_sidecar = sidecar_path_for_dataset(source_path)
    source_sidecar.write_text('{"metadata": {}}', encoding="utf-8")

    result = migrate_training_dataset_to_subfolder(source_path, working_dir=working_dir)

    target_path = working_dir / "dataset" / "dataset.jsonl"
    target_sidecar = working_dir / "dataset" / "dataset.registry.json"
    assert result.created is True
    assert result.working_path == str(target_path.resolve())
    assert result.sidecar_copied is True
    assert result.sidecar_path == str(target_sidecar.resolve())
    assert target_path.exists()
    assert target_sidecar.exists()
    assert not source_path.exists()
    assert not source_sidecar.exists()


def test_canonical_training_dataset_path_leaves_external_paths_unchanged(tmp_path):
    external_path = tmp_path / "external" / "dataset.jsonl"

    result = canonical_training_dataset_path(
        external_path,
        working_dir=tmp_path / "training_data",
    )

    assert result == external_path.resolve()
