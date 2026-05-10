import inspect
import json

import core.preferences as preferences


EXPECTED_DEFAULT_KEYS = {
    "last_loaded_dataset_path",
    "last_open_directory",
    "last_system_prompt",
    "preview_user_name",
    "preview_assistant_name",
    "dataset_format",
    "confirm_delete_entries",
    "default_dataset_directory",
    "auto_backups_enabled",
    "backup_directory",
    "backups_per_dataset",
    "auto_normalize_on_load",
}


def test_preferences_module_has_no_streamlit_import_or_session_state_usage():
    source = inspect.getsource(preferences)

    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "st.session_state" not in source


def test_defaults_contain_expected_core_keys():
    assert EXPECTED_DEFAULT_KEYS.issubset(preferences.DEFAULTS)


def test_load_preferences_returns_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "PREFS_FILE", tmp_path / "missing.json")

    loaded = preferences.load_preferences()

    assert loaded == preferences.DEFAULTS
    assert loaded is not preferences.DEFAULTS


def test_load_preferences_merges_saved_preferences_over_defaults(tmp_path, monkeypatch):
    prefs_file = tmp_path / "preferences.json"
    prefs_file.write_text(
        json.dumps(
            {
                "dataset_format": "ShareGPT",
                "preview_user_name": "Player",
                "custom_future_key": "kept",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(preferences, "PREFS_FILE", prefs_file)

    loaded = preferences.load_preferences()

    assert loaded["dataset_format"] == "ShareGPT"
    assert loaded["preview_user_name"] == "Player"
    assert loaded["custom_future_key"] == "kept"
    assert loaded["backup_directory"] == preferences.DEFAULTS["backup_directory"]


def test_load_preferences_falls_back_to_defaults_for_invalid_json(tmp_path, monkeypatch):
    prefs_file = tmp_path / "preferences.json"
    prefs_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(preferences, "PREFS_FILE", prefs_file)

    assert preferences.load_preferences() == preferences.DEFAULTS


def test_load_preferences_falls_back_to_defaults_for_non_dict_json(tmp_path, monkeypatch):
    prefs_file = tmp_path / "preferences.json"
    prefs_file.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr(preferences, "PREFS_FILE", prefs_file)

    assert preferences.load_preferences() == preferences.DEFAULTS


def test_save_preferences_writes_utf8_json_with_trailing_newline(tmp_path, monkeypatch):
    prefs_file = tmp_path / "prefs" / "preferences.json"
    monkeypatch.setattr(preferences, "PREFS_FILE", prefs_file)
    monkeypatch.setattr(preferences, "ensure_app_directories", lambda: prefs_file.parent.mkdir(parents=True))
    prefs = {"preview_user_name": "Zoë", "dataset_format": "ChatML"}

    preferences.save_preferences(prefs)

    raw = prefs_file.read_bytes()
    assert raw.endswith(b"\n")
    assert json.loads(raw.decode("utf-8")) == prefs


def test_save_preferences_roundtrips_through_load_preferences(tmp_path, monkeypatch):
    prefs_file = tmp_path / "prefs" / "preferences.json"
    monkeypatch.setattr(preferences, "PREFS_FILE", prefs_file)
    monkeypatch.setattr(preferences, "ensure_app_directories", lambda: prefs_file.parent.mkdir(parents=True))
    prefs = {**preferences.DEFAULTS, "last_system_prompt": "Stay vivid."}

    preferences.save_preferences(prefs)

    assert preferences.load_preferences()["last_system_prompt"] == "Stay vivid."


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
