# main.py

import sys
from PySide6 import QtWidgets, QtGui

# optional resource module ────────────────────────────────────────────────
try:
    import resources_rc           # generated from resources.qrc
except ModuleNotFoundError:
    # No embedded resources – continue without them
    pass

from core.prefs import APP_NAME
from ui.mainwindow import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("GlobileShop LLC")
    app.setApplicationName(APP_NAME)
    # optional: set a global window icon
    app.setWindowIcon(QtGui.QIcon(":/assets/logo.png"))
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()