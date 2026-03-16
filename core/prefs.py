import copy
import json
import math
import pathlib
import sys

from PySide6 import QtCore, QtGui

APP_NAME = "MandelPy"
_base_config_dir = pathlib.Path(
    QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
)
_fallback_config_dir = pathlib.Path.home() / f".{APP_NAME.lower()}"
_workspace_config_dir = pathlib.Path.cwd() / f".{APP_NAME.lower()}"

DEFAULT_PREFS = dict(
    max_iter=512,
    escape_radius=4.0,
    quality="High",
    default_save=str(pathlib.Path.home() / "Pictures"),
    gradient=[
        (0.0, "#000764"),
        (0.16, "#2068CB"),
        (0.42, "#EDFFFF"),
        (0.6425, "#FFAA00"),
        (0.8575, "#000200"),
    ],
)

_VALID_QUALITY = {"Low", "Medium", "High", "Ultra", "Custom"}
_MIN_ITER = 64
_MAX_ITER = 20000
_MIN_ESCAPE_RADIUS = 2.0
_MAX_ESCAPE_RADIUS = 16.0
_MIN_CUSTOM_MIN_ITER = 10
_MAX_CUSTOM_MIN_ITER = 20000
_MIN_CUSTOM_MULTIPLIER = 1.0
_MAX_CUSTOM_MULTIPLIER = 500.0
_MAX_GRADIENT_STOPS = 256


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
    return _workspace_config_dir


CONFIG_DIR = _resolve_config_dir()
CONFIG_FILE = CONFIG_DIR / "prefs.json"


def _clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _clamp_float(value, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        number = default
    return max(minimum, min(number, maximum))


def _sanitize_quality(value) -> str:
    if isinstance(value, str) and value in _VALID_QUALITY:
        return value
    return DEFAULT_PREFS["quality"]


def _sanitize_default_save(value) -> str:
    default_path = pathlib.Path(DEFAULT_PREFS["default_save"]).expanduser()
    if not isinstance(value, str):
        return str(default_path)

    raw = value.strip()
    if not raw or "\x00" in raw:
        return str(default_path)

    candidate = pathlib.Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = pathlib.Path.home() / candidate

    try:
        candidate = candidate.resolve(strict=False)
    except OSError:
        return str(default_path)
    return str(candidate)


def _sanitize_gradient(gradient_value) -> list[tuple[float, str]]:
    default_gradient = _default_prefs_copy()["gradient"]
    if not isinstance(gradient_value, (list, tuple)):
        return default_gradient
    if len(gradient_value) < 2 or len(gradient_value) > _MAX_GRADIENT_STOPS:
        return default_gradient

    sanitized: list[tuple[float, str]] = []
    for stop in gradient_value:
        if not isinstance(stop, (list, tuple)) or len(stop) != 2:
            continue
        try:
            pos = float(stop[0])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(pos):
            continue
        color = QtGui.QColor(str(stop[1]))
        if not color.isValid():
            continue
        sanitized.append((max(0.0, min(pos, 1.0)), color.name()))

    if len(sanitized) < 2:
        return default_gradient

    sanitized.sort(key=lambda item: item[0])
    return sanitized[:_MAX_GRADIENT_STOPS]


def _sanitize_prefs(raw_prefs: object) -> dict:
    defaults = _default_prefs_copy()
    if not isinstance(raw_prefs, dict):
        raw_prefs = {}

    prefs = {
        "max_iter": _clamp_int(raw_prefs.get("max_iter"), defaults["max_iter"], _MIN_ITER, _MAX_ITER),
        "escape_radius": _clamp_float(
            raw_prefs.get("escape_radius"),
            defaults["escape_radius"],
            _MIN_ESCAPE_RADIUS,
            _MAX_ESCAPE_RADIUS,
        ),
        "quality": _sanitize_quality(raw_prefs.get("quality")),
        "default_save": _sanitize_default_save(raw_prefs.get("default_save")),
        "gradient": _sanitize_gradient(raw_prefs.get("gradient")),
        "custom_min_iter": _clamp_int(
            raw_prefs.get("custom_min_iter"),
            64,
            _MIN_CUSTOM_MIN_ITER,
            _MAX_CUSTOM_MIN_ITER,
        ),
        "custom_multiplier": _clamp_float(
            raw_prefs.get("custom_multiplier"),
            50.0,
            _MIN_CUSTOM_MULTIPLIER,
            _MAX_CUSTOM_MULTIPLIER,
        ),
    }
    return prefs


def load_prefs() -> dict:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf8") as fp:
                return _sanitize_prefs(json.load(fp))

        defaults = _sanitize_prefs(_default_prefs_copy())
        save_prefs(defaults)
        return defaults
    except Exception as exc:
        _warn(f"Could not load preferences ({exc}); using defaults.")
        return _sanitize_prefs(_default_prefs_copy())


def save_prefs(prefs: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        sanitized = _sanitize_prefs(prefs)
        with open(CONFIG_FILE, "w", encoding="utf8") as fp:
            json.dump(sanitized, fp, indent=4)
    except OSError as exc:
        _warn(f"Could not save preferences ({exc}).")


PREFS = load_prefs()
