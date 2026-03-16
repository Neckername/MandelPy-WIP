import json
import math
import pathlib
import re

import numpy as np
from PySide6 import QtCore, QtGui

ASSETS_DIR = pathlib.Path(__file__).parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

MAX_PRESET_FILE_BYTES = 1_048_576
MAX_PRESET_STOPS = 256
_PRESET_NAME_RE = re.compile(r"^[A-Za-z0-9 _.-]{1,64}$")
_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


class PresetValidationError(ValueError):
    """Raised when a gradient preset is malformed or unsafe."""


def _assets_dir_resolved() -> pathlib.Path:
    return ASSETS_DIR.resolve()


def validate_preset_name(name: str) -> str:
    candidate = (name or "").strip()
    if not candidate:
        raise PresetValidationError("Preset name cannot be empty.")
    if candidate in {".", ".."}:
        raise PresetValidationError("Preset name cannot be '.' or '..'.")
    if candidate != candidate.rstrip(" ."):
        raise PresetValidationError("Preset name cannot end in a dot or space.")
    if not _PRESET_NAME_RE.fullmatch(candidate):
        raise PresetValidationError(
            "Preset name may only contain letters, digits, spaces, '.', '-' and '_'."
        )
    if candidate.lower() in _WINDOWS_RESERVED_NAMES:
        raise PresetValidationError("Preset name is reserved by Windows.")
    return candidate


def _assert_within_assets(path: pathlib.Path) -> pathlib.Path:
    resolved = path.resolve(strict=False)
    assets_root = _assets_dir_resolved()
    try:
        resolved.relative_to(assets_root)
    except ValueError as exc:
        raise PresetValidationError("Preset path is outside the managed assets folder.") from exc
    return resolved


def preset_path_for_name(name: str) -> pathlib.Path:
    safe_name = validate_preset_name(name)
    return _assert_within_assets(ASSETS_DIR / f"{safe_name}.grd")


def _normalize_color(value: object) -> str:
    color = QtGui.QColor(str(value))
    if not color.isValid():
        raise PresetValidationError("Preset contains an invalid color value.")
    return color.name()


def normalize_gradient_stops(stops: object) -> list[tuple[float, str]]:
    if not isinstance(stops, (list, tuple)):
        raise PresetValidationError("Preset stops must be a list.")
    if len(stops) < 2:
        raise PresetValidationError("Preset must contain at least two color stops.")
    if len(stops) > MAX_PRESET_STOPS:
        raise PresetValidationError(f"Preset has too many stops (max {MAX_PRESET_STOPS}).")

    normalized: list[tuple[float, str]] = []
    for stop in stops:
        if not isinstance(stop, (list, tuple)) or len(stop) != 2:
            raise PresetValidationError("Each stop must be a [position, color] pair.")
        try:
            pos = float(stop[0])
        except (TypeError, ValueError) as exc:
            raise PresetValidationError("Stop position must be numeric.") from exc
        if not math.isfinite(pos) or pos < 0.0 or pos > 1.0:
            raise PresetValidationError("Stop position must be between 0 and 1.")
        normalized.append((pos, _normalize_color(stop[1])))

    normalized.sort(key=lambda item: item[0])
    return normalized


def _validate_preset_payload(payload: object, fallback_name: str) -> tuple[str, list[tuple[float, str]]]:
    if not isinstance(payload, dict):
        raise PresetValidationError("Preset file must contain a JSON object.")
    raw_name = payload.get("name", fallback_name)
    if not isinstance(raw_name, str):
        raise PresetValidationError("Preset name must be a string.")
    safe_name = validate_preset_name(raw_name)
    stops = normalize_gradient_stops(payload.get("stops"))
    return safe_name, stops


def _unique_default_name() -> str:
    """Return an unused preset name like 'Preset 1'."""
    n = 1
    while preset_path_for_name(f"Preset {n}").exists():
        n += 1
    return f"Preset {n}"


def gradient_to_lut(gradient: list, lut_size: int = 2048) -> np.ndarray:
    # Must have >=2 stops.
    if len(gradient) < 2:
        # Solid fill: repeat first stop's color.
        c = gradient[0][1] if gradient else "#000000"
        rgb = QtGui.QColor(c).getRgb()[:3]
        lut = np.tile(np.array(rgb, np.uint8)[None, :], (lut_size, 1))
        return lut

    gradient = sorted(gradient, key=lambda x: x[0])
    xs = [int(p * (lut_size - 1)) for p, _ in gradient]
    cols = [QtGui.QColor(c).getRgb()[:3] for _, c in gradient]
    lut = np.zeros((lut_size, 3), np.uint8)
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        c0, c1 = np.array(cols[i]), np.array(cols[i + 1])
        for x in range(x0, x1 + 1):
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0
            lut[x] = (1 - t) * c0 + t * c1
    lut[: xs[0]] = cols[0]
    lut[xs[-1] :] = cols[-1]
    return lut


def save_preset_file(gradient: object, name: str) -> pathlib.Path:
    safe_name = validate_preset_name(name)
    safe_stops = normalize_gradient_stops(gradient)
    path = preset_path_for_name(safe_name)
    with open(path, "w", encoding="utf8") as fp:
        json.dump({"name": safe_name, "stops": safe_stops}, fp, indent=4)
    return path


def load_preset_file(path: pathlib.Path) -> tuple[str, list[tuple[float, str]]]:
    path = _assert_within_assets(pathlib.Path(path))
    if path.suffix.lower() != ".grd":
        raise PresetValidationError("Preset file must use the .grd extension.")
    if not path.is_file():
        raise PresetValidationError("Preset file does not exist.")
    if path.stat().st_size > MAX_PRESET_FILE_BYTES:
        raise PresetValidationError(
            f"Preset file is too large (max {MAX_PRESET_FILE_BYTES} bytes)."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresetValidationError("Preset file is not valid JSON.") from exc
    return _validate_preset_payload(payload, path.stem)


def list_presets() -> list[pathlib.Path]:
    return sorted(p for p in ASSETS_DIR.glob("*.grd") if p.is_file())


def gradient_preview_pixmap(gradient, w=120, h=20):
    pm = QtGui.QPixmap(w, h)
    pm.fill(QtCore.Qt.transparent)
    lg = QtGui.QLinearGradient(0, 0, w, 0)
    for p, c in gradient:
        lg.setColorAt(p, QtGui.QColor(c))
    painter = QtGui.QPainter(pm)
    painter.fillRect(0, 0, w, h, lg)
    painter.end()
    return pm
