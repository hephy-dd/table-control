import logging
from PySide6 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class PreferencesDialog(QtWidgets.QDialog):

    def __init__(self, settings: QtCore.QSettings, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.settings = settings

        self.tab_widget = QtWidgets.QTabWidget(self)

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.button_box)
