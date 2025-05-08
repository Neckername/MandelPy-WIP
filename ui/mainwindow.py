from PySide6 import QtWidgets, QtGui, QtCore
import pathlib, datetime

# ensure the Qt resources (.qrc → .py) get registered
import resources_rc    # our top-level resources_rc.py

from core.prefs    import PREFS, DEFAULT_PREFS, save_prefs, APP_NAME
from core.gradient import gradient_to_lut
from ui.canvas    import MandelbrotCanvas
from ui.dialogs   import PrefsDialog, GradientDialog


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

        # ─── Ribbon toolbar ───────────────────────────────────────────
        tb = QtWidgets.QToolBar("Main")
        tb.setIconSize(QtCore.QSize(16, 16))
        self.addToolBar(tb)

        # Home / full-view button
        act_home = QtGui.QAction("Full view", self)
        act_home.setShortcut("Home")
        act_home.triggered.connect(self.canvas.reset_view)
        tb.addAction(act_home)

        # Save / Save As / Gradient / Prefs
        act_save   = QtGui.QAction("Save",      self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.quick_save)

        act_saveAs = QtGui.QAction("Save as…",  self)
        act_saveAs.setShortcut("Ctrl+Shift+S")
        act_saveAs.triggered.connect(self.save_as)

        act_grad   = QtGui.QAction("Gradient…", self)
        act_grad.triggered.connect(self.edit_gradient)

        act_prefs  = QtGui.QAction("Prefs…",    self)
        act_prefs.triggered.connect(self.edit_prefs)

        tb.addActions([act_save, act_saveAs, act_grad, act_prefs])


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
            self.canvas.max_iter      = PREFS["max_iter"]
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