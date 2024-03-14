import importlib.resources

from PyQt5 import QtCore, QtGui

# Support assets from optional pyrcc resources
try:
    from .. import _resources
except ImportError:
    _resources = None


def loadIcon(filename: str) -> QtGui.QIcon:
    if _resources:
        return QtGui.QIcon(f":/icons/{filename}")
    with importlib.resources.path("table_control.assets.icons", filename) as path:
        return QtGui.QIcon(str(path))


def loadText(filename: str) -> str:
    if _resources:
        text = ""
        file = QtCore.QFile(f":/{filename}")
        if file.open(QtCore.QFile.ReadOnly | QtCore.QFile.Text):
            text = QtCore.QTextStream(file).readAll()
            file.close()
        return text
    with importlib.resources.path("table_control.assets", filename) as path:
        with open(path, "r") as fp:
            return fp.read()
