import inspect
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.preferences as preferences
from core.models import AppSetting, Base


EXPECTED_DEFAULT_KEYS = {
    "last_loaded_dataset_path",
    "last_open_directory",
    "last_system_prompt",
    "preview_user_name",
    "preview_assistant_name",
    "confirm_delete_entries",
    "default_dataset_directory",
    "auto_backups_enabled",
    "backup_directory",
    "backups_per_dataset",
    "backup_destination_type",
    "backup_destination_custom_path",
    "cloud_backup_last_sync_at",
    "auto_correct_validation_errors",
}


@pytest.fixture
def settings_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(preferences, "SessionLocal", session_factory)
    monkeypatch.setattr(
        preferences,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    monkeypatch.setattr(preferences, "PREFS_FILE", tmp_path / "preferences.json")
    Base.metadata.create_all(bind=engine)
    return session_factory


def test_preferences_module_has_no_streamlit_import_or_session_state_usage():
    source = inspect.getsource(preferences)

    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "st.session_state" not in source


def test_defaults_contain_expected_core_keys():
    assert EXPECTED_DEFAULT_KEYS.issubset(preferences.DEFAULTS)


def test_get_setting_returns_default_when_missing(settings_db):
    assert preferences.get_setting("missing", default="fallback") == "fallback"


def test_set_and_get_setting_roundtrip_json_values(settings_db):
    preferences.set_setting("preview_user_name", "Zoë")
    preferences.set_setting("backups_per_dataset", 7)
    preferences.set_setting("auto_backups_enabled", False)

    assert preferences.get_setting("preview_user_name") == "Zoë"
    assert preferences.get_setting("backups_per_dataset") == 7
    assert preferences.get_setting("auto_backups_enabled") is False


def test_get_all_settings_returns_stored_values_without_defaults(settings_db):
    preferences.set_setting("preview_user_name", "Player")

    assert preferences.get_all_settings() == {"preview_user_name": "Player"}


def test_load_preferences_returns_defaults_when_db_empty_and_file_missing(settings_db):
    loaded = preferences.load_preferences()

    assert loaded == preferences.DEFAULTS
    assert loaded is not preferences.DEFAULTS


def test_load_preferences_merges_db_settings_over_defaults(settings_db):
    preferences.set_all_settings({
        "preview_user_name": "Player",
        "custom_future_key": "kept",
    })

    loaded = preferences.load_preferences()

    assert loaded["preview_user_name"] == "Player"
    assert loaded["custom_future_key"] == "kept"
    assert loaded["backup_directory"] == preferences.DEFAULTS["backup_directory"]


def test_migrate_preferences_json_if_needed_imports_file_when_table_empty(
    settings_db,
):
    preferences.PREFS_FILE.write_text(
        json.dumps(
            {
                "preview_user_name": "Player",
                "custom_future_key": "kept",
            }
        ),
        encoding="utf-8",
    )

    assert preferences.migrate_preferences_json_if_needed() is True

    loaded = preferences.load_preferences()
    assert loaded["preview_user_name"] == "Player"
    assert loaded["custom_future_key"] == "kept"
    assert preferences.PREFS_FILE.exists()


def test_migrate_preferences_json_if_needed_does_not_read_file_when_db_has_rows(
    settings_db,
):
    preferences.set_setting("preview_user_name", "DB Value")
    preferences.PREFS_FILE.write_text(
        json.dumps({"preview_user_name": "JSON Value"}),
        encoding="utf-8",
    )

    assert preferences.migrate_preferences_json_if_needed() is False
    assert preferences.load_preferences()["preview_user_name"] == "DB Value"


def test_load_preferences_migrates_old_auto_normalize_key(settings_db):
    preferences.PREFS_FILE.write_text(
        json.dumps({"auto_normalize_on_load": False}),
        encoding="utf-8",
    )

    loaded = preferences.load_preferences()

    assert loaded["auto_correct_validation_errors"] is False
    assert preferences.get_setting("auto_correct_validation_errors") is False


def test_load_preferences_ignores_invalid_json_migration_file(
    settings_db,
):
    preferences.PREFS_FILE.write_text("{not valid json", encoding="utf-8")

    assert preferences.load_preferences() == preferences.DEFAULTS


def test_load_preferences_ignores_non_dict_json_migration_file(
    settings_db,
):
    preferences.PREFS_FILE.write_text("[1, 2, 3]", encoding="utf-8")

    assert preferences.load_preferences() == preferences.DEFAULTS


def test_save_preferences_writes_db_not_preferences_json(settings_db):
    prefs = {"preview_user_name": "Zoë", "custom_future_key": "kept"}

    preferences.save_preferences(prefs)

    assert not preferences.PREFS_FILE.exists()
    assert preferences.get_setting("preview_user_name") == "Zoë"
    assert preferences.get_setting("custom_future_key") == "kept"


def test_export_settings_writes_utf8_json_with_trailing_newline(
    settings_db,
    tmp_path,
):
    preferences.set_all_settings({"preview_user_name": "Zoë", "custom_future_key": "kept"})
    export_path = tmp_path / "exports" / "settings.json"

    preferences.export_settings(export_path)

    raw = export_path.read_bytes()
    assert raw.endswith(b"\n")
    data = json.loads(raw.decode("utf-8"))
    assert data["custom_future_key"] == "kept"
    assert data["preview_user_name"] == "Zoë"
    assert EXPECTED_DEFAULT_KEYS.issubset(data)


def test_import_settings_bulk_upserts_and_returns_merged_preferences(
    settings_db,
    tmp_path,
):
    import_path = tmp_path / "settings.json"
    import_path.write_text(
        json.dumps({"last_system_prompt": "Stay vivid."}),
        encoding="utf-8",
    )

    loaded = preferences.import_settings(import_path)

    assert loaded["last_system_prompt"] == "Stay vivid."
    assert preferences.get_setting("last_system_prompt") == "Stay vivid."


def test_import_settings_rejects_non_object_json(settings_db, tmp_path):
    import_path = tmp_path / "settings.json"
    import_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError):
        preferences.import_settings(import_path)


def test_app_setting_table_uses_key_primary_key(settings_db):
    mapper = AppSetting.__mapper__

    assert [column.key for column in mapper.primary_key] == ["key"]


def test_get_initial_dir_prefers_parent_of_existing_path_key(tmp_path):
    dataset = tmp_path / "datasets" / "active.jsonl"
    dataset.parent.mkdir()
    dataset.write_text("", encoding="utf-8")
    fallback = tmp_path / "fallback"
    fallback.mkdir()

    result = preferences.get_initial_dir(
        {
            "last_loaded_dataset_path": str(dataset),
            "last_open_directory": str(fallback),
            "default_dataset_directory": str(fallback),
        },
        path_key="last_loaded_dataset_path",
    )

    assert result == str(dataset.parent)


def test_get_initial_dir_falls_back_to_valid_dir_key(tmp_path):
    directory = tmp_path / "last-open"
    directory.mkdir()

    result = preferences.get_initial_dir(
        {
            "last_loaded_dataset_path": str(tmp_path / "missing" / "file.jsonl"),
            "last_open_directory": str(directory),
            "default_dataset_directory": "",
        },
        path_key="last_loaded_dataset_path",
    )

    assert result == str(directory)


def test_get_initial_dir_falls_back_to_valid_default_dataset_directory(tmp_path):
    default_dir = tmp_path / "training"
    default_dir.mkdir()

    result = preferences.get_initial_dir(
        {
            "last_open_directory": str(tmp_path / "missing"),
            "default_dataset_directory": str(default_dir),
        }
    )

    assert result == str(default_dir)


def test_get_initial_dir_returns_none_when_no_valid_directory_exists(tmp_path):
    result = preferences.get_initial_dir(
        {
            "last_loaded_dataset_path": str(tmp_path / "missing" / "file.jsonl"),
            "last_open_directory": str(tmp_path / "missing-open"),
            "default_dataset_directory": str(tmp_path / "missing-default"),
        },
        path_key="last_loaded_dataset_path",
    )

    assert result is None
