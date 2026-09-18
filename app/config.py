import json
import os
import sys

APP_NAME = "InsomniaLauncher"

GITHUB_OWNER = "xyzmsl"
GITHUB_REPO = "Insomnia-Launcher"


def _data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_NAME)


DATA_DIR = _data_dir()
CACHE_DIR = os.path.join(DATA_DIR, "covers")
DB_PATH = os.path.join(DATA_DIR, "library.db")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "local_folders": [],
    "auto_update": False,
    "hidden_sources": [],
    "last_rescan": None,
    "mode": "all",
    "source_filter": None,
    "genre_filter": None,
    "search_text": "",
    "sort_key": "name",
}


def ensure_dirs():
    os.makedirs(CACHE_DIR, exist_ok=True)


def load_settings():
    ensure_dirs()
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings):
    ensure_dirs()
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
    os.replace(tmp, SETTINGS_PATH)


def icon_path():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ui", "assets", "icon.png")