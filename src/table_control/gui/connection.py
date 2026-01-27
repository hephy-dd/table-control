import logging
from typing import Any

from PySide6 import QtCore, QtWidgets

from ..core import utils
from .controller import Appliance

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 2
BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]


class ResourceGroupBox(QtWidgets.QGroupBox):
    """
    A single 'Resource n' editor: resource name + optional baud + termination.
    Encapsulates enable/disable, baud visibility, (de)serialization and resource dict building.
    """

    def __init__(self, index: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self.setTitle(f"Resource {index + 1}")

        self.name = QtWidgets.QLineEdit(self)

        self.baud_label = QtWidgets.QLabel("Baud rate", self)
        self.baud = QtWidgets.QComboBox(self)
        for rate in BAUD_RATES:
            self.baud.addItem(str(rate), rate)
        self.baud.setCurrentIndex(self.baud.findData(9600))

        self.term_label = QtWidgets.QLabel("Termination", self)
        self.term = QtWidgets.QComboBox(self)
        self.term.addItem("CR+LF", "\r\n")
        self.term.addItem("CR", "\r")
        self.term.addItem("LF", "\n")

        layout = QtWidgets.QFormLayout(self)
        layout.addRow("Resource name", self.name)
        layout.addRow(self.baud_label, self.baud)
        layout.addRow(self.term_label, self.term)

        self.name.textChanged.connect(self._update_baud_visibility)

        # initial state
        self._update_baud_visibility()

    def set_slot_enabled(self, enabled: bool) -> None:
        # QGroupBox itself can be disabled; child widgets follow
        self.setEnabled(enabled)
        self._update_baud_visibility()

    def _update_baud_visibility(self) -> None:
        # If the whole group is disabled, hide baud unconditionally (matches your current behavior)
        if not self.isEnabled():
            self.baud_label.setEnabled(False)
            self.baud.setEnabled(False)
            return

        show = utils.is_serial_resource(self.name.text())
        self.baud_label.setEnabled(show)
        self.baud.setEnabled(show)

    def to_settings_dict(self) -> dict[str, Any]:
        return {
            "resource_name": self.name.text(),
            "termination": self.term.currentData() or "\r\n",
            "baud_rate": self.baud.currentData(),  # store; validate on read
        }

    def from_settings_dict(self, data: dict[str, Any]) -> None:
        self.name.setText(data.get("resource_name", ""))
        self.term.setCurrentIndex(self.term.findData(data.get("termination", "\r\n")))

        baud = data.get("baud_rate", 9600)
        idx = self.baud.findData(baud)
        if idx >= 0:
            self.baud.setCurrentIndex(idx)

        self._update_baud_visibility()

    def resource_dict(self) -> dict[str, Any]:
        raw_name = self.name.text()
        resource_name = utils.get_resource_name(raw_name)
        visa_library = utils.get_visa_library(resource_name)
        termination = self.term.currentData() or "\r\n"

        resource: dict[str, Any] = {
            "resource_name": resource_name,
            "visa_library": visa_library,
            "options": {
                "read_termination": termination,
                "write_termination": termination,
            },
        }

        if utils.is_serial_resource(resource_name):
            baud_rate = self.baud.currentData()
            if isinstance(baud_rate, int):
                resource["baud_rate"] = baud_rate

        return resource


class ConnectionDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connection")

        self.driver_combo_box = QtWidgets.QComboBox(self)

        root_layout = QtWidgets.QVBoxLayout(self)

        root_layout.addWidget(QtWidgets.QLabel("Controller"))
        root_layout.addWidget(self.driver_combo_box)

        self.connections: list[ResourceGroupBox] = []
        for i in range(MAX_CONNECTIONS):
            box = ResourceGroupBox(i, self)
            self.connections.append(box)
            root_layout.addWidget(box)

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        root_layout.addWidget(self.button_box)

        self.driver_combo_box.currentIndexChanged.connect(self._update_inputs)

        # set initial visibility / enabled states
        self._update_inputs(self.driver_combo_box.currentIndex())

    def _update_inputs(self, index: int) -> None:
        appliance = self.driver_combo_box.itemData(index)
        if not isinstance(appliance, dict):
            # if nothing is selected yet, disable all resource slots
            for box in self.connections:
                box.set_slot_enabled(False)
            return

        resources = int(appliance.get("resources", 0))
        for i, box in enumerate(self.connections):
            box.set_slot_enabled(resources > i)

    def read_settings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("connection_dialog")
        current_driver: str = settings.value("current_driver", "", str)  # type: ignore
        resources: list[dict] = settings.value("resources", [], list)  # type: ignore
        settings.endGroup()

        idx = self.driver_combo_box.findText(current_driver)
        self.driver_combo_box.setCurrentIndex(max(0, idx))

        for i, box in enumerate(self.connections):
            if i < len(resources) and isinstance(resources[i], dict):
                box.from_settings_dict(resources[i])

        # Make sure enable state matches the selected driver
        self._update_inputs(self.driver_combo_box.currentIndex())

    def write_settings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("connection_dialog")
        settings.setValue("current_driver", self.driver_combo_box.currentText())
        settings.setValue("resources", [box.to_settings_dict() for box in self.connections])
        settings.endGroup()

    def add_appliance(self, name: str, appliance: dict) -> None:
        self.driver_combo_box.addItem(name, appliance)

    def appliance(self) -> Appliance:
        name = self.driver_combo_box.currentText()
        appliance = self.driver_combo_box.currentData()
        driver = appliance.get("driver")

        count = int(appliance.get("resources", 0))
        resources: list[dict[str, Any]] = [self.connections[i].resource_dict() for i in range(count)]

        return Appliance(name, driver, resources)
