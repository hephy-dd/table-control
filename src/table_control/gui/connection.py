import logging
from dataclasses import dataclass
from typing import Any

from PySide6 import QtCore, QtWidgets

from ..core import utils
from ..core.driver import Driver
from ..core.resource import ResourceConfig
from .controller import Connection

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = 2
BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]


@dataclass
class ConnectionConfig:
    name: str
    driver_cls: type[Driver]
    n_resources: int


class ResourceGroupBox(QtWidgets.QGroupBox):
    """
    A single 'Resource n' editor: resource name + optional baud + termination.
    Encapsulates enable/disable, baud visibility, (de)serialization and resource dict building.
    """

    def __init__(self, index: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self.setTitle(f"Resource {index + 1}")

        self.resource_name_label = QtWidgets.QLabel("Resource Name", self)
        self.resource_name_line_edit = QtWidgets.QLineEdit(self)

        self.baud_rate_label = QtWidgets.QLabel("Baud Rate", self)
        self.baud_rate_combo_box = QtWidgets.QComboBox(self)
        for rate in BAUD_RATES:
            self.baud_rate_combo_box.addItem(str(rate), rate)
        self.baud_rate_combo_box.setCurrentIndex(self.baud_rate_combo_box.findData(9600))

        self.termination_label = QtWidgets.QLabel("Termination", self)
        self.termination_combo_box = QtWidgets.QComboBox(self)
        self.termination_combo_box.addItem("CR+LF", "\r\n")
        self.termination_combo_box.addItem("CR", "\r")
        self.termination_combo_box.addItem("LF", "\n")

        layout = QtWidgets.QFormLayout(self)
        layout.addRow(self.resource_name_label, self.resource_name_line_edit)
        layout.addRow(self.baud_rate_label, self.baud_rate_combo_box)
        layout.addRow(self.termination_label, self.termination_combo_box)

        self.resource_name_line_edit.textChanged.connect(self._update_baud_visibility)

        self._update_baud_visibility()

    def resource_name(self) -> str:
        return self.resource_name_line_edit.text().strip()

    def baud_rate(self) -> int | None:
        return self.baud_rate_combo_box.currentData()

    def termination(self) -> str:
        return self.termination_combo_box.currentData() or "\r\n"

    def timeout(self) -> float:
        return 4.0

    def set_slot_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)
        self._update_baud_visibility()

    def _update_baud_visibility(self) -> None:
        if not self.isEnabled():
            self.baud_rate_label.setEnabled(False)
            self.baud_rate_combo_box.setEnabled(False)
            return

        show = utils.is_serial_resource(self.resource_name())
        self.baud_rate_label.setEnabled(show)
        self.baud_rate_combo_box.setEnabled(show)

    def to_settings_dict(self) -> dict[str, Any]:
        return {
            "resource_name": self.resource_name(),
            "termination": self.termination(),
            "baud_rate": self.baud_rate(),
        }

    def from_settings_dict(self, data: dict[str, Any]) -> None:
        self.resource_name_line_edit.setText(data.get("resource_name", ""))
        self.termination_combo_box.setCurrentIndex(self.termination_combo_box.findData(data.get("termination", "\r\n")))

        baud_rate = data.get("baud_rate", 9600)
        index = self.baud_rate_combo_box.findData(baud_rate)
        if index >= 0:
            self.baud_rate_combo_box.setCurrentIndex(index)

        self._update_baud_visibility()

    def resource_config(self) -> ResourceConfig:
        resource_name = utils.get_resource_name(self.resource_name())
        visa_library = utils.get_visa_library(resource_name)
        termination = self.termination()
        timeout = self.timeout()

        baud_rate = None
        if utils.is_serial_resource(resource_name):
            baud_rate = self.baud_rate()

        return ResourceConfig(
            visa_library=visa_library,
            resource_name=resource_name,
            baud_rate=baud_rate,
            termination=termination,
            timeout=timeout,
        )


class ConnectionDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connection")

        self.driver_combo_box = QtWidgets.QComboBox(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Controller"))
        layout.addWidget(self.driver_combo_box)

        self.resource_group_boxes: list[ResourceGroupBox] = []
        for i in range(MAX_CONNECTIONS):
            group_box = ResourceGroupBox(i, self)
            self.resource_group_boxes.append(group_box)
            layout.addWidget(group_box)

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout.addWidget(self.button_box)

        self.driver_combo_box.currentIndexChanged.connect(self._update_inputs)

        # set initial visibility / enabled states
        self._update_inputs(self.driver_combo_box.currentIndex())

    def _update_inputs(self, index: int) -> None:
        config = self.driver_combo_box.itemData(index)
        if not isinstance(config, ConnectionConfig):
            for group_box in self.resource_group_boxes:
                group_box.set_slot_enabled(False)
            return

        for i, group_box in enumerate(self.resource_group_boxes):
            group_box.set_slot_enabled(config.n_resources > i)

    def read_settings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("connection_dialog")
        current_driver: str = settings.value("current_driver", "", str)  # type: ignore
        resources: list[dict] = settings.value("resources", [], list)  # type: ignore
        settings.endGroup()

        index = self.driver_combo_box.findText(current_driver)
        self.driver_combo_box.setCurrentIndex(max(0, index))

        for i, group_box in enumerate(self.resource_group_boxes):
            if i < len(resources) and isinstance(resources[i], dict):
                group_box.from_settings_dict(resources[i])

        # Make sure enable state matches the selected driver
        self._update_inputs(self.driver_combo_box.currentIndex())

    def write_settings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("connection_dialog")
        settings.setValue("current_driver", self.driver_combo_box.currentText())
        settings.setValue("resources", [group_box.to_settings_dict() for group_box in self.resource_group_boxes])
        settings.endGroup()

    def add_connection(self, connection: ConnectionConfig) -> None:
        self.driver_combo_box.addItem(connection.name, connection)

    def create_connection(self) -> Connection:
        connection: ConnectionConfig = self.driver_combo_box.currentData()
        name = connection.name
        driver = connection.driver_cls
        n_resources = connection.n_resources
        resources: list[ResourceConfig] = []
        for i in range(n_resources):
            resources.append(self.resource_group_boxes[i].resource_config())
        return Connection(name, driver, resources)
