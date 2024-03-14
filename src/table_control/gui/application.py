import sys

from PyQt5 import QtWidgets

from . import APP_TITLE, APP_VERSION
from .mainwindow import MainWindow
from .utils import loadIcon


class Application:

    def __init__(self) -> None:
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName("table-control")
        self.app.setApplicationVersion(APP_VERSION)
        self.app.setOrganizationName("HEPHY")
        self.app.setOrganizationDomain("hephy.at")
        self.app.setApplicationDisplayName(f"{APP_TITLE} {APP_VERSION}")
        self.app.setWindowIcon(loadIcon("table_control.svg"))

        self.window = MainWindow()

        self.app.aboutToQuit.connect(self.shutdown)

    def registerPlugin(self, plugin) -> None:
        self.window.registerPlugin(plugin)

    def bootstrap(self) -> None:
        self.window.installPlugins()
        self.window.readSettings()
        self.window.show()

        self.app.exec()

    def shutdown(self) -> None:
        self.window.writeSettings()
        self.window.uninstallPlugins()
