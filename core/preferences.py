import json
from pathlib import Path

APP_DATA_DIR = Path(__file__).resolve().parent.parent / "app_data"
APP_DATA_DIR.mkdir(exist_ok=True)

PREFS_FILE = APP_DATA_DIR / "preferences.json"

DEFAULTS: dict = {
    "last_loaded_dataset_path": "",
    "last_open_directory": "",
    "last_system_prompt": "",
    "preview_user_name": "User",
    "preview_assistant_name": "Assistant",
    "dataset_format": "ChatML",
    "confirm_delete_entries": True,
}


def load_preferences() -> dict:
    try:
        if PREFS_FILE.exists():
            data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULTS, **data}
    except Exception:
        pass
    return dict(DEFAULTS)


def save_preferences(prefs: dict) -> None:
    APP_DATA_DIR.mkdir(exist_ok=True)
    PREFS_FILE.write_text(
        json.dumps(prefs, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_initial_dir(prefs: dict, path_key: str = "", dir_key: str = "last_open_directory") -> str | None:
    """Return the best initialdir for a file dialog, or None to let the OS decide."""
    if path_key:
        p = prefs.get(path_key, "")
        if p:
            parent = Path(p).parent
            if parent.exists():
                return str(parent)
    d = prefs.get(dir_key, "")
    if d and Path(d).exists():
        return d
    return None
