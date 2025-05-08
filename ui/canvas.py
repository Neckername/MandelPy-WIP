from PySide6 import QtWidgets, QtGui, QtCore
import numpy as np
from core.render   import cuda_render
from core.gradient import gradient_to_lut
from core.prefs    import PREFS

class MandelbrotCanvas(QtWidgets.QLabel):
    requestStatus = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        # … your look & feel / sizePolicy / tracking code …

        # viewport defaults
        self.xmin, self.xmax = -2.5, 1.0
        self.ymin, self.ymax = -1.25, 1.25

        # prefs & LUT
        self.max_iter      = PREFS["max_iter"]
        self.escape_radius = PREFS["escape_radius"]
        self.color_lut     = gradient_to_lut(PREFS["gradient"])

        # interaction state
        self.dragging = False
        self.last_pos = QtCore.QPoint()

        # ←── initial render
        self.full_render()

    def full_render(self):
        W = self.width()  or 800
        H = self.height() or 600

        self.requestStatus.emit("Rendering…")
        QtWidgets.QApplication.processEvents()

        iters = cuda_render(self.xmin, self.xmax,
                            self.ymin, self.ymax,
                            W, H,
                            self.max_iter,
                            self.escape_radius)

        norm   = np.clip(iters, 0, self.max_iter-1).astype(np.int32)
        idx    = (norm * (len(self.color_lut)-1)) // self.max_iter
        colors = self.color_lut[idx]

        qimg = QtGui.QImage(colors.data, W, H, 3*W,
                            QtGui.QImage.Format.Format_RGB888).copy()
        self.setPixmap(QtGui.QPixmap.fromImage(qimg))
        self.current_qimage = qimg

        self.requestStatus.emit(f"Rendered {W}×{H}")

    def set_color_lut(self, lut: np.ndarray):
        """Update the colour lookup and repaint immediately."""
        self.color_lut = lut.copy()
        self.full_render()

    def reset_view(self):
        """Reset viewport to defaults and repaint."""
        self.xmin, self.xmax = -2.5, 1.0
        self.ymin, self.ymax = -1.25, 1.25
        self.full_render()

    def wheelEvent(self, e: QtGui.QWheelEvent):
        zoom = 0.85 if e.angleDelta().y() > 0 else 1/0.85
        pos = e.position()
        px, py = pos.x()/self.width(), pos.y()/self.height()
        cx = self.xmin + px*(self.xmax-self.xmin)
        cy = self.ymin + py*(self.ymax-self.ymin)
        self.xmin = cx + (self.xmin - cx)*zoom
        self.xmax = cx + (self.xmax - cx)*zoom
        self.ymin = cy + (self.ymin - cy)*zoom
        self.ymax = cy + (self.ymax - cy)*zoom
        self.full_render()

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_pos = e.position()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self.dragging:
            dx = e.position().x() - self.last_pos.x()
            dy = e.position().y() - self.last_pos.y()
            self.last_pos = e.position()
            rx = (self.xmax - self.xmin)/self.width()
            ry = (self.ymax - self.ymin)/self.height()
            self.xmin -= dx*rx; self.xmax -= dx*rx
            self.ymin -= dy*ry; self.ymax -= dy*ry
            self.full_render()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        self.dragging = False

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        key = e.key()
        # pan with arrows
        step = 0.05
        dx = (self.xmax - self.xmin)*step
        dy = (self.ymax - self.ymin)*step
        if   key == QtCore.Qt.Key.Key_Left:  self.xmin -= dx; self.xmax -= dx
        elif key == QtCore.Qt.Key.Key_Right: self.xmin += dx; self.xmax += dx
        elif key == QtCore.Qt.Key.Key_Up:    self.ymin -= dy; self.ymax -= dy
        elif key == QtCore.Qt.Key.Key_Down:  self.ymin += dy; self.ymax += dy
        # zoom with plus/minus
        elif key in (QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Equal):
            factor = 0.85
            cx = (self.xmin + self.xmax)/2; cy = (self.ymin + self.ymax)/2
            self.xmin = cx + (self.xmin - cx)*factor
            self.xmax = cx + (self.xmax - cx)*factor
            self.ymin = cy + (self.ymin - cy)*factor
            self.ymax = cy + (self.ymax - cy)*factor
        elif key in (QtCore.Qt.Key.Key_Minus, QtCore.Qt.Key.Key_Underscore):
            factor = 1/0.85
            cx = (self.xmin + self.xmax)/2; cy = (self.ymin + self.ymax)/2
            self.xmin = cx + (self.xmin - cx)*factor
            self.xmax = cx + (self.xmax - cx)*factor
            self.ymin = cy + (self.ymin - cy)*factor
            self.ymax = cy + (self.ymax - cy)*factor
        else:
            return
        self.full_render() 