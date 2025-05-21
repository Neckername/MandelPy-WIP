from PySide6 import QtWidgets, QtGui, QtCore
import pathlib, datetime

# optional resource module (same rationale as in main.py) ────────────────
try:
    import resources_rc
except ModuleNotFoundError:
    pass

from core.prefs    import PREFS, DEFAULT_PREFS, save_prefs, APP_NAME
from core.gradient import gradient_to_lut
from ui.canvas    import MandelbrotCanvas
from ui.dialogs   import PrefsDialog, GradientDialog
from ui.focalmap  import FocalMap

SOFTWARE_VERSION = "1.2.0"        # shown in Help ▸ About

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # ─── Window setup ──────────────────────────────────────────────
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QtGui.QIcon(":/assets/logo.png"))
        self.resize(1100, 800)

        # ─── Central canvas ───────────────────────────────────────────
        self.canvas = MandelbrotCanvas()
        self.setCentralWidget(self.canvas)
        self.canvas.requestStatus.connect(self.statusBar().showMessage)

        # ─── Zoom indicator (right side of status-bar) ───────────────────
        self._lbl_zoom = QtWidgets.QLabel()
        self.statusBar().addPermanentWidget(self._lbl_zoom)

        # keep it updated
        self.canvas.zoomChanged.connect(self._update_zoom_label)
        # initialise with current value
        self._update_zoom_label(self.canvas.compute_zoom())

        # ─── Actions (re-used by menus) ────────────────────────────────
        act_save   = QtGui.QAction("Save",      self,
                                   shortcut="Ctrl+S",
                                   triggered=self.quick_save)

        act_saveAs = QtGui.QAction("Save as…",  self,
                                   shortcut="Ctrl+Shift+S",
                                   triggered=self.save_as)

        act_exit   = QtGui.QAction("Exit",      self,
                                   shortcut="Ctrl+Q",
                                   triggered=self.close)

        act_grad   = QtGui.QAction("Gradient…", self,
                                   triggered=self.edit_gradient)

        act_prefs  = QtGui.QAction("Preferences…", self,
                                   shortcut="Ctrl+,",
                                   triggered=self.edit_prefs)

        act_home   = QtGui.QAction("Full view", self,
                                   shortcut="Home",
                                   triggered=self.canvas.reset_view)

        act_focal  = QtGui.QAction("Focal Map", self,
                                   triggered=self._open_focal_map)

        act_about  = QtGui.QAction("About",     self,
                                   triggered=self._about)

        # ─── Menu-bar organisation ───────────────────────────────────
        mb = self.menuBar()

        m_file = mb.addMenu("&File")
        m_file.addAction(act_save)
        m_file.addAction(act_saveAs)
        m_file.addAction(act_prefs)
        m_file.addSeparator()
        m_file.addAction(act_exit)

        m_edit = mb.addMenu("&Edit")
        m_edit.addAction(act_grad)

        m_view = mb.addMenu("&View")
        m_view.addActions([act_home, act_focal])

        m_help = mb.addMenu("&Help")
        m_help.addAction(act_about)

        self._focal_map = None

    # ─── Helpers for saving ─────────────────────────────────────────
    def _default_name(self) -> pathlib.Path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return pathlib.Path(PREFS["default_save"]) / f"mandelbrot_{ts}.png"

    def quick_save(self):
        path = self._default_name()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.canvas.current_qimage.save(str(path))
        self.statusBar().showMessage(f"Saved to {path}")

    def save_as(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save image",
            str(self._default_name()),
            "PNG image (*.png)"
        )
        if fn:
            self.canvas.current_qimage.save(fn)
            self.statusBar().showMessage(f"Saved to {fn}")


    # ─── Preferences & Gradient ────────────────────────────────────
    def edit_prefs(self):
        dlg = PrefsDialog(self)
        if dlg.exec():
            # PREFS has already been updated & saved by PrefsDialog.accept()
            self.canvas.escape_radius = PREFS["escape_radius"]
            self.canvas.full_render()

    def edit_gradient(self):
        # build gradient editor with current stops (or defaults)
        grad_src = PREFS.get("gradient") or DEFAULT_PREFS["gradient"]
        dlg = GradientDialog(self, grad_src)

        # realtime preview: whenever the model changes, regenerate LUT & repaint
        def _update_preview():
            lut = gradient_to_lut(dlg.get_gradient())
            self.canvas.set_color_lut(lut)

        for sig in (
            dlg.model.dataChanged,
            dlg.model.rowsInserted,
            dlg.model.rowsRemoved,
            dlg.model.modelReset,
            dlg.model.layoutChanged
        ):
            sig.connect(_update_preview)

        # run dialog
        if dlg.exec():
            # user clicked OK: persist prefs & ensure final LUT
            PREFS["gradient"] = dlg.get_gradient()
            save_prefs(PREFS)
            _update_preview()

    # ────────────────────────────────────────────────────────────────────
    # Zoom label helpers
    # --------------------------------------------------------------------
    def _format_zoom(self, z: float) -> str:
        """Return e.g. 950.00x   1.00 Mx   2.50 Bx   3.40 Tx …"""
        abbrev = [("T", 1e12), ("B", 1e9), ("M", 1e6)]
        for suffix, factor in abbrev:
            if z >= factor:
                return f"{z / factor:0.2f} {suffix}x"
        return f"{z:0.2f}x"

    def _update_zoom_label(self, z: float):
        self._lbl_zoom.setText(self._format_zoom(z))

    # ────────────────────────────────────────────────────────────────────
    # Help ▸ About
    # --------------------------------------------------------------------
    def _about(self):
        QtWidgets.QMessageBox.about(
            self,
            f"About {APP_NAME}",
            (f"<b>{APP_NAME}</b> — version {SOFTWARE_VERSION}<br>"
             "© 2025 Neckername")
        )

    # Focal-map helper
    def _open_focal_map(self):
        if self._focal_map is None or not self._focal_map.isVisible():
            self._focal_map = FocalMap(self.canvas.color_lut, self)
            # keep crosshair in sync with future viewport changes
            self.canvas.viewportChanged.connect(
                self._focal_map.update_crosshair,
                QtCore.Qt.ConnectionType.UniqueConnection
            )

        # always (re-)draw crosshair for CURRENT viewport
        cx = (self.canvas.xmin + self.canvas.xmax) / 2.0
        cy = (self.canvas.ymin + self.canvas.ymax) / 2.0
        self._focal_map.update_crosshair(cx, cy)

        self._focal_map.show()
        self._focal_map.raise_()