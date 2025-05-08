import json, pathlib, shutil
import numpy as np
from PySide6 import QtGui, QtCore

ASSETS_DIR = pathlib.Path(__file__).parent.parent/"assets"
ASSETS_DIR.mkdir(exist_ok=True)

def _unique_default_name() -> str:
    """Return 'Preset 1', 'Preset 2', … that is still unused in ASSETS_DIR."""
    n = 1
    while (ASSETS_DIR / f"Preset {n}.grd").exists():
        n += 1
    return f"Preset {n}"

def gradient_to_lut(gradient:list, lut_size:int=2048) -> np.ndarray:
    # must have ≥2 stops
    if len(gradient) < 2:
        # solid fill: repeat first stop's colour
        c = gradient[0][1] if gradient else "#000000"
        rgb = QtGui.QColor(c).getRgb()[:3]
        lut = np.tile(np.array(rgb, np.uint8)[None,:], (lut_size,1))
        return lut

    gradient = sorted(gradient, key=lambda x: x[0])
    xs   = [int(p*(lut_size-1)) for p,_ in gradient]
    cols = [QtGui.QColor(c).getRgb()[:3] for _,c in gradient]
    lut  = np.zeros((lut_size,3),np.uint8)
    for i in range(len(xs)-1):
        x0,x1 = xs[i], xs[i+1]
        c0,c1 = np.array(cols[i]), np.array(cols[i+1])
        for x in range(x0,x1+1):
            t = (x-x0)/(x1-x0) if x1!=x0 else 0
            lut[x] = (1-t)*c0 + t*c1
    lut[:xs[0]] = cols[0]
    lut[xs[-1]:] = cols[-1]
    return lut

def save_preset_file(gradient,name):
    p = ASSETS_DIR/f"{name}.grd"
    with open(p,"w",encoding="utf8") as fp:
        json.dump({"name":name,"stops":gradient}, fp, indent=4)

def load_preset_file(path: pathlib.Path):
    data = json.loads(path.read_text(encoding="utf8"))
    return data.get("name", path.stem), data["stops"]

def list_presets()->list[pathlib.Path]:
    return sorted(ASSETS_DIR.glob("*.grd"))

def gradient_preview_pixmap(gradient, w=120,h=20):
    pm = QtGui.QPixmap(w,h); pm.fill(QtCore.Qt.transparent)
    lg = QtGui.QLinearGradient(0,0,w,0)
    for p,c in gradient: lg.setColorAt(p,QtGui.QColor(c))
    painter=QtGui.QPainter(pm); painter.fillRect(0,0,w,h,lg); painter.end()
    return pm
