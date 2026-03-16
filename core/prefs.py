import copy
import json
import pathlib
import sys
from PySide6 import QtCore

APP_NAME    = "MandelPy"
_base_config_dir = pathlib.Path(
    QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.AppDataLocation
    )
)
_fallback_config_dir = pathlib.Path.home() / f".{APP_NAME.lower()}"
_workspace_config_dir = pathlib.Path.cwd() / f".{APP_NAME.lower()}"

DEFAULT_PREFS = dict(
    max_iter=512,
    escape_radius=4.0,
    quality="High",
    default_save=str(pathlib.Path.home()/"Pictures"),
    gradient=[
        (0.0, "#000764"),
        (0.16,"#2068CB"),
        (0.42,"#EDFFFF"),
        (0.6425,"#FFAA00"),
        (0.8575,"#000200"),
    ]
)

def _default_prefs_copy() -> dict:
    return copy.deepcopy(DEFAULT_PREFS)

def _warn(msg: str):
    print(f"[{APP_NAME} prefs] {msg}", file=sys.stderr)

def _resolve_config_dir() -> pathlib.Path:
    for candidate in (
        _base_config_dir / APP_NAME,
        _fallback_config_dir,
        _workspace_config_dir,
    ):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".prefs_write_probe"
            with open(probe, "w", encoding="utf8") as fp:
                fp.write("")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    # Last-resort in-memory behavior if all writes fail.
    return _workspace_config_dir

CONFIG_DIR = _resolve_config_dir()
CONFIG_FILE = CONFIG_DIR / "prefs.json"

def load_prefs() -> dict:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf8") as fp:
                p = json.load(fp)
                if not p.get("gradient") or len(p["gradient"]) < 2:
                    p["gradient"] = _default_prefs_copy()["gradient"]
                return p
        defaults = _default_prefs_copy()
        save_prefs(defaults)
        return defaults
    except Exception as exc:
        _warn(f"Could not load preferences ({exc}); using defaults.")
        return _default_prefs_copy()

def save_prefs(prefs: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf8") as fp:
            json.dump(prefs, fp, indent=4)
    except OSError as exc:
        _warn(f"Could not save preferences ({exc}).")

PREFS = load_prefs()
