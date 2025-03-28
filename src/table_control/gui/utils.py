import importlib.resources

from PySide6 import QtCore, QtGui


def loadIcon(filename: str) -> QtGui.QIcon:
    with importlib.resources.path("table_control.assets.icons", filename) as path:
        return QtGui.QIcon(str(path))


def loadText(filename: str) -> str:
    with importlib.resources.path("table_control.assets", filename) as path:
        with open(path, "r") as fp:
            return fp.read()
