from PySide6 import QtWidgets, QtGui, QtCore
import numpy as np
from core.render   import cuda_render
from core.gradient import gradient_to_lut
from core.prefs    import PREFS

class FocalMap(QtWidgets.QDialog):
    """Small window showing the full 1.00× view plus a cross-hair."""
    def __init__(self, lut, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.setWindowTitle("Focal Map")
        self.setFixedSize(350, 250)              # 3.5 : 2.5 aspect
        self._w, self._h = 350, 250

        self.label = QtWidgets.QLabel(self)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.label)

        self._base = self._render_full_view(lut)  # 1.00× bitmap
        self.label.setPixmap(self._base)

    # ──────────────────────────────────────────────────────────────
    def _render_full_view(self, lut) -> QtGui.QPixmap:
        iters = cuda_render(-2.5, 1.0, -1.25, 1.25,
                            self._w, self._h,
                            PREFS["max_iter"], PREFS["escape_radius"])

        norm  = np.clip(iters.astype(np.float64), 0, PREFS["max_iter"])
        idx   = (norm * (len(lut) - 1)) / PREFS["max_iter"]
        rgb   = lut[idx.astype(np.int32)]

        qimg  = QtGui.QImage(rgb.data, self._w, self._h, 3*self._w,
                             QtGui.QImage.Format.Format_RGB888).copy()
        return QtGui.QPixmap.fromImage(qimg)

    # ──────────────────────────────────────────────────────────────
    def update_crosshair(self, cx: float, cy: float):
        """cx,cy in fractal coords → draw cross-hair on fresh copy."""
        pm = self._base.copy()
        p  = QtGui.QPainter(pm)
        pen = QtGui.QPen(QtCore.Qt.red);  pen.setWidth(1)
        p.setPen(pen)

        x = int((cx + 2.5) / 3.5 * self._w)
        y = int((cy + 1.25) / 2.5 * self._h)
        p.drawLine(x, 0, x, self._h)
        p.drawLine(0, y, self._w, y)
        p.end()

        self.label.setPixmap(pm) 