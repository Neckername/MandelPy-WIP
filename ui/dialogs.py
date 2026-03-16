import pathlib
import shutil

from PySide6 import QtCore, QtGui, QtWidgets

from core.prefs import DEFAULT_PREFS, PREFS, save_prefs
from core.gradient import (
    ASSETS_DIR,
    PresetValidationError,
    _unique_default_name,
    gradient_preview_pixmap,
    list_presets,
    load_preset_file,
    preset_path_for_name,
    save_preset_file,
    validate_preset_name,
)


class PrefsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        form = QtWidgets.QFormLayout(self)

        self.dspin_esc = QtWidgets.QDoubleSpinBox()
        self.dspin_esc.setRange(2.0, 16.0)
        self.dspin_esc.setValue(PREFS["escape_radius"])

        self.combo_quality = QtWidgets.QComboBox()
        self.combo_quality.addItems(["Low", "Medium", "High", "Ultra", "Custom"])
        self.combo_quality.setCurrentText(PREFS.get("quality", "Medium"))

        self.spin_min_iter = QtWidgets.QSpinBox()
        self.spin_min_iter.setRange(10, 20000)

        self.dspin_mult = QtWidgets.QDoubleSpinBox()
        self.dspin_mult.setRange(1.0, 500.0)
        self.dspin_mult.setDecimals(1)

        self.path_edit = QtWidgets.QLineEdit(PREFS["default_save"])
        btn_browse = QtWidgets.QPushButton("...")
        btn_browse.clicked.connect(self.browse_path)
        hl = QtWidgets.QHBoxLayout()
        hl.addWidget(self.path_edit)
        hl.addWidget(btn_browse)

        form.addRow("Escape radius:", self.dspin_esc)
        form.addRow("Render quality:", self.combo_quality)
        form.addRow("Min iterations:", self.spin_min_iter)
        form.addRow("Multiplier:", self.dspin_mult)
        form.addRow("Default save dir:", hl)

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

        self._qmap = {"Low": 0.5, "Medium": 1.0, "High": 2.0, "Ultra": 4.0}

        def _apply_values(quality: str):
            custom = quality == "Custom"
            self.spin_min_iter.setEnabled(custom)
            self.dspin_mult.setEnabled(custom)

            if custom:
                self.spin_min_iter.setValue(PREFS.get("custom_min_iter", 64))
                self.dspin_mult.setValue(PREFS.get("custom_multiplier", 50.0))
            else:
                qfactor = self._qmap.get(quality, 1.0)
                self.spin_min_iter.setValue(64)
                self.dspin_mult.setValue(50.0 * qfactor)

        _apply_values(self.combo_quality.currentText())
        self.combo_quality.currentTextChanged.connect(_apply_values)

    def browse_path(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose directory",
            PREFS["default_save"],
        )
        if d:
            self.path_edit.setText(d)

    def accept(self):
        PREFS["escape_radius"] = self.dspin_esc.value()
        PREFS["quality"] = self.combo_quality.currentText()
        if PREFS["quality"] == "Custom":
            PREFS["custom_min_iter"] = self.spin_min_iter.value()
            PREFS["custom_multiplier"] = self.dspin_mult.value()
        PREFS["default_save"] = self.path_edit.text().strip()
        save_prefs(PREFS)
        super().accept()


class ColourDelegate(QtWidgets.QStyledItemDelegate):
    """Paint the color cell and edit it through QColorDialog."""

    def paint(self, painter, option, index):
        if index.column() == 1:
            col = QtGui.QColor(index.data())
            painter.fillRect(option.rect, col)
            if option.state & QtWidgets.QStyle.State_HasFocus:
                super().paint(painter, option, index)
        else:
            super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        if index.column() == 1:
            current = QtGui.QColor(index.data() or "#FFFFFF")
            new_col = QtWidgets.QColorDialog.getColor(
                current,
                parent,
                "Choose color",
                QtWidgets.QColorDialog.ShowAlphaChannel,
            )
            if new_col.isValid():
                index.model().setData(index, new_col.name())
            return None
        return super().createEditor(parent, option, index)


class GradientBar(QtWidgets.QWidget):
    """Draw a linear gradient based on the model rows."""

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(30)
        self.model = model
        for sig in (
            model.dataChanged,
            model.rowsInserted,
            model.rowsRemoved,
            model.modelReset,
            model.layoutChanged,
        ):
            sig.connect(self.update)

    def paintEvent(self, event):
        if self.model.rowCount() < 2:
            return
        grad = QtGui.QLinearGradient(0, 0, self.width(), 0)
        for row in range(self.model.rowCount()):
            pos_item = self.model.item(row, 0)
            col_item = self.model.item(row, 1)
            try:
                pos = float(pos_item.text())
                col = QtGui.QColor(col_item.text())
                grad.setColorAt(pos, col)
            except Exception:
                pass
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), grad)
        painter.end()


class GradientDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, gradient=None):
        super().__init__(parent)
        self.setWindowTitle("Edit gradient")
        self.resize(450, 320)

        self.model = QtGui.QStandardItemModel(0, 2, self)
        self.model.setHorizontalHeaderLabels(["Position (0-1)", "Color"])
        for p, c in (gradient or DEFAULT_PREFS["gradient"]):
            self._add_row(p, c)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegate(ColourDelegate(self.table))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        btn_add = QtWidgets.QPushButton("Add stop")
        btn_rm = QtWidgets.QPushButton("Remove")
        btn_def = QtWidgets.QPushButton("Reset to defaults")
        btn_save = QtWidgets.QPushButton("Save")
        btn_pst = QtWidgets.QPushButton("Presets")

        btn_add.clicked.connect(self.add_stop)
        btn_rm.clicked.connect(lambda: self.model.removeRow(self.table.currentIndex().row()))
        btn_def.clicked.connect(self.reset_defaults)
        btn_save.clicked.connect(self.save_as_preset)
        btn_pst.clicked.connect(self.open_presets)

        hl = QtWidgets.QHBoxLayout()
        hl.addWidget(btn_add)
        hl.addWidget(btn_rm)
        hl.addWidget(btn_def)
        hl.addStretch(1)
        hl.addWidget(btn_save)
        hl.addWidget(btn_pst)

        bar = GradientBar(self.model)

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.table)
        lay.addLayout(hl)
        lay.addWidget(bar)
        lay.addWidget(bb)

    def _add_row(self, pos, col):
        item_pos = QtGui.QStandardItem(str(pos))
        item_col = QtGui.QStandardItem(col)
        self.model.appendRow([item_pos, item_col])

    def add_stop(self):
        self._add_row(0.5, "#FFFFFF")

    def reset_defaults(self):
        self.model.setRowCount(0)
        for p, c in DEFAULT_PREFS["gradient"]:
            self._add_row(p, c)

    def save_as_preset(self):
        default = _unique_default_name()
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Save gradient as preset",
            "Preset name:",
            text=default,
        )
        if not ok:
            return

        name = (name or default).strip()
        try:
            safe_name = validate_preset_name(name)
            path = preset_path_for_name(safe_name)
        except PresetValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid preset name", str(exc))
            return

        if path.exists():
            ans = QtWidgets.QMessageBox.question(
                self,
                "Overwrite preset?",
                f'Preset "{safe_name}" already exists - overwrite?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if ans != QtWidgets.QMessageBox.Yes:
                return

        try:
            save_preset_file(self.get_gradient(), safe_name)
        except (PresetValidationError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not save preset", str(exc))
            return

        QtWidgets.QMessageBox.information(
            self,
            "Preset saved",
            f'Stored as "{safe_name}.grd" in {ASSETS_DIR}',
        )

    def open_presets(self):
        dlg = GradientPresetsDialog(self)
        if dlg.exec():
            grad = dlg.selected_gradient or []
            self.model.setRowCount(0)
            for p, c in grad:
                self._add_row(p, c)

    def accept(self):
        if self.model.rowCount() < 2:
            QtWidgets.QMessageBox.warning(
                self,
                "Gradient",
                "Please keep at least two color stops.",
            )
            return
        super().accept()

    def get_gradient(self):
        stops = []
        for row in range(self.model.rowCount()):
            try:
                p = float(self.model.item(row, 0).text())
                c = self.model.item(row, 1).text()
                stops.append((max(0.0, min(p, 1.0)), c))
            except ValueError:
                pass
        return stops


class GradientPresetsDialog(QtWidgets.QDialog):
    """List, import, rename, delete and apply .grd presets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gradient presets")
        self.resize(400, 310)
        self.selected_gradient = None

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Preview"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.apply_selected)

        btn_add = QtWidgets.QPushButton("Add...")
        btn_rm = QtWidgets.QPushButton("Remove")
        btn_ren = QtWidgets.QPushButton("Rename")
        btn_apply = QtWidgets.QPushButton("Apply")
        btn_close = QtWidgets.QPushButton("Close")

        btn_add.clicked.connect(self.add_preset)
        btn_rm.clicked.connect(self.remove_selected)
        btn_ren.clicked.connect(self.rename_selected)
        btn_apply.clicked.connect(self.apply_selected)
        btn_close.clicked.connect(self.reject)

        bl = QtWidgets.QHBoxLayout()
        bl.addStretch(1)
        for w in (btn_add, btn_rm, btn_ren):
            bl.addWidget(w)
        bl.addStretch(1)
        bl.addWidget(btn_apply)
        bl.addWidget(btn_close)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(bl)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for fp in list_presets():
            try:
                name, grad = load_preset_file(fp)
            except PresetValidationError:
                # Keep malformed presets out of UI interactions.
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            it_name = QtWidgets.QTableWidgetItem(name)
            it_name.setData(QtCore.Qt.UserRole, str(fp))
            self.table.setItem(row, 0, it_name)

            lbl = QtWidgets.QLabel()
            lbl.setPixmap(gradient_preview_pixmap(grad))
            self.table.setCellWidget(row, 1, lbl)

    def _current_path(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        item = self.table.item(r, 0)
        if item is None:
            return None
        raw = item.data(QtCore.Qt.UserRole)
        if not isinstance(raw, str):
            return None
        try:
            path = pathlib.Path(raw).resolve(strict=False)
            path.relative_to(ASSETS_DIR.resolve())
        except (OSError, ValueError):
            return None
        return path

    def apply_selected(self, *args):
        path = self._current_path()
        if not path:
            return
        try:
            _, grad = load_preset_file(path)
        except PresetValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid preset", str(exc))
            self.refresh()
            return
        self.selected_gradient = grad
        self.accept()

    def add_preset(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import preset",
            "",
            "Gradient preset (*.grd)",
        )
        if not fn:
            return

        src = pathlib.Path(fn)
        if src.suffix.lower() != ".grd":
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid preset",
                "Imported preset must use the .grd extension.",
            )
            return

        try:
            dest = preset_path_for_name(src.stem)
        except PresetValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid preset name", str(exc))
            return

        if dest.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Preset exists",
                "A preset with the same name already exists.",
            )
            return

        try:
            shutil.copy(src, dest)
            load_preset_file(dest)
        except (OSError, PresetValidationError) as exc:
            dest.unlink(missing_ok=True)
            QtWidgets.QMessageBox.warning(self, "Invalid preset", str(exc))
            return

        self.refresh()

    def remove_selected(self):
        path = self._current_path()
        if not path:
            return
        ans = QtWidgets.QMessageBox.question(
            self,
            "Delete preset",
            f'Delete preset "{path.stem}" from disk?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if ans == QtWidgets.QMessageBox.Yes:
            path.unlink(missing_ok=True)
            self.refresh()

    def rename_selected(self):
        path = self._current_path()
        if not path:
            return
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename preset",
            "New name:",
            text=path.stem,
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        try:
            safe_name = validate_preset_name(new_name)
            new_path = preset_path_for_name(safe_name)
            _, grad = load_preset_file(path)
        except PresetValidationError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid preset", str(exc))
            return

        if new_path.exists() and new_path != path:
            QtWidgets.QMessageBox.warning(
                self,
                "Exists",
                "Another preset with that name already exists.",
            )
            return

        try:
            if new_path != path:
                path.rename(new_path)
            save_preset_file(grad, safe_name)
        except (OSError, PresetValidationError) as exc:
            QtWidgets.QMessageBox.warning(self, "Rename failed", str(exc))
            return

        self.refresh()
