import logging
from typing import Optional

from PyQt5 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class PreferencesDialog(QtWidgets.QDialog):

    def __init__(self, settings: QtCore.QSettings, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.settings = settings

        self.tabWidget = QtWidgets.QTabWidget(self)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tabWidget)
        layout.addWidget(self.buttonBox)
