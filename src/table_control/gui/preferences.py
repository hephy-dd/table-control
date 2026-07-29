import logging

from PySide6 import QtCore, QtWidgets

__all__ = ["PreferencesDialog"]

logger = logging.getLogger(__name__)


class PreferencesDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Preferences")

        self.misc_widget = QtWidgets.QWidget()

        self.require_calibration_check_box = QtWidgets.QCheckBox()
        self.require_calibration_check_box.setText("Require Calibration")
        self.require_calibration_check_box.setToolTip(
            "Require axis calibration for absolute movements"
        )

        misc_widget_layout = QtWidgets.QFormLayout(self.misc_widget)
        misc_widget_layout.addWidget(self.require_calibration_check_box)

        self.tab_widget = QtWidgets.QTabWidget(self)
        self.tab_widget.addTab(self.misc_widget, "Misc")

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.button_box)

    def add_tab(self, widget: QtWidgets.QWidget, title: str) -> None:
        self.tab_widget.addTab(widget, title)

    def insert_tab(self, index: int, widget: QtWidgets.QWidget, title: str) -> None:
        self.tab_widget.insertTab(index, widget, title)

    def remove_tab(self, widget: QtWidgets.QWidget) -> None:
        index = self.tab_widget.indexOf(widget)
        self.tab_widget.removeTab(index)

    def is_require_calibration(self) -> bool:
        return self.require_calibration_check_box.isChecked()

    def set_require_calibration(self, enabled: bool) -> None:
        self.require_calibration_check_box.setChecked(enabled)

    def read_settings(self, settings: QtCore.QSettings) -> None: ...

    def write_settings(self, settings: QtCore.QSettings) -> None: ...
