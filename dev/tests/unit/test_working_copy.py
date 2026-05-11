import json

from core.registry_sidecar import sidecar_path_for_dataset
from core.working_copy import create_dataset_working_copy


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
    assert result.working_path == str((working_dir / "dataset.jsonl").resolve())
    assert result.sidecar_copied is True
    assert result.sidecar_path == str((working_dir / "dataset.registry.json").resolve())
    assert (working_dir / "dataset.jsonl").read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")
    assert (working_dir / "dataset.registry.json").read_text(encoding="utf-8") == '{"metadata": {}}'


def test_create_dataset_working_copy_does_not_copy_files_already_in_working_dir(tmp_path):
    working_dir = tmp_path / "working"
    working_dir.mkdir()
    source_path = working_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is False
    assert result.working_path == str(source_path.resolve())


def test_create_dataset_working_copy_avoids_overwriting_existing_file(tmp_path):
    source_dir = tmp_path / "source"
    working_dir = tmp_path / "working"
    source_dir.mkdir()
    working_dir.mkdir()
    source_path = source_dir / "dataset.jsonl"
    source_path.write_text(json.dumps({"messages": [], "tags": []}) + "\n", encoding="utf-8")
    existing = working_dir / "dataset.jsonl"
    existing.write_text("existing\n", encoding="utf-8")

    result = create_dataset_working_copy(source_path, working_dir=working_dir)

    assert result.created is True
    assert result.working_path != str(existing.resolve())
    assert existing.read_text(encoding="utf-8") == "existing\n"
