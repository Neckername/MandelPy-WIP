import pathlib, json
from PySide6 import QtCore

APP_NAME    = "MandelPy"
CONFIG_DIR  = pathlib.Path(QtCore.QStandardPaths
               .writableLocation(QtCore.QStandardPaths.AppDataLocation))
CONFIG_FILE = CONFIG_DIR / "prefs.json"

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

def load_prefs() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE,"r") as fp:
            p = json.load(fp)
            if not p.get("gradient") or len(p["gradient"])<2:
                p["gradient"] = DEFAULT_PREFS["gradient"]
            return p
    except Exception:
        save_prefs(DEFAULT_PREFS)
        return DEFAULT_PREFS.copy()

def save_prefs(prefs:dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE,"w") as fp:
        json.dump(prefs, fp, indent=4)

PREFS = load_prefs()
