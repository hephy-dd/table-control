import sys

from PySide6 import QtWidgets

from . import APP_NAME, APP_TITLE, APP_VERSION
from .mainwindow import MainWindow
from .utils import load_icon


class Application:

    def __init__(self) -> None:
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setApplicationVersion(APP_VERSION)
        self.app.setOrganizationName("MBI")
        self.app.setOrganizationDomain("mbi.oeaw.ac.at")
        self.app.setApplicationDisplayName(f"{APP_TITLE} {APP_VERSION}")
        self.app.setWindowIcon(load_icon("table_control.svg"))

        self.window = MainWindow()

        self.app.aboutToQuit.connect(self.shutdown)

    def register_plugin(self, plugin) -> None:
        self.window.register_plugin(plugin)

    def bootstrap(self) -> None:
        self.window.install_plugins()
        self.window.read_settings()
        self.window.show()

        self.app.exec()

    def shutdown(self) -> None:
        self.window.write_settings()
        self.window.uninstall_plugins()
