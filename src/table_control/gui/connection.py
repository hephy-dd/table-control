import logging

from PySide6 import QtCore, QtWidgets

from ..core.resource import Resource
from ..core import utils

from .controller import Appliance

logger = logging.getLogger(__name__)


class ConnectionDialog(QtWidgets.QDialog):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Connection")

        self.driver_combo_box = QtWidgets.QComboBox(self)

        self.resource_name_line_edit = {}
        self.resource_name_line_edit[0] = QtWidgets.QLineEdit(self)
        self.resource_name_line_edit[1] = QtWidgets.QLineEdit(self)

        self.resource_termination_combo_box = {}
        self.resource_termination_combo_box[0] = QtWidgets.QComboBox()
        self.resource_termination_combo_box[0].addItem("CR+LF", "\r\n")
        self.resource_termination_combo_box[0].addItem("CR", "\r")
        self.resource_termination_combo_box[0].addItem("LF", "\n")
        self.resource_termination_combo_box[1] = QtWidgets.QComboBox()
        self.resource_termination_combo_box[1].addItem("CR+LF", "\r\n")
        self.resource_termination_combo_box[1].addItem("CR", "\r")
        self.resource_termination_combo_box[1].addItem("LF", "\n")

        self.widget = QtWidgets.QWidget(self)

        widget_layout = QtWidgets.QVBoxLayout(self.widget)
        widget_layout.addWidget(QtWidgets.QLabel("Controller"))
        widget_layout.addWidget(self.driver_combo_box)
        widget_layout.addWidget(QtWidgets.QLabel("Resource 1"))
        widget_layout.addWidget(self.resource_name_line_edit[0])
        widget_layout.addWidget(self.resource_termination_combo_box[0])
        widget_layout.addWidget(QtWidgets.QLabel("Resource 2"))
        widget_layout.addWidget(self.resource_name_line_edit[1])
        widget_layout.addWidget(self.resource_termination_combo_box[1])

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.widget)
        layout.addWidget(self.button_box)

        self.driver_combo_box.currentIndexChanged.connect(self.update_inputs)

    def read_settings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("connection_dialog")
        currentDriver: str = settings.value("current_driver", "", str)  # type: ignore
        resources: list[dict] = settings.value("resources", [], list)  # type: ignore
        settings.endGroup()
        index = self.driver_combo_box.findText(currentDriver)
        self.driver_combo_box.setCurrentIndex(max(0, index))
        for index, widget in enumerate(self.resource_name_line_edit.values()):
            if index < len(resources):
                widget.setText(resources[index].get("resource_name", ""))
                self.resource_termination_combo_box[index].setCurrentIndex(
                    self.resource_termination_combo_box[index].findData(resources[index].get("termination", "\r\n"))
                )

    def write_settings(self) -> None:
        resources = []
        for index, widget in enumerate(self.resource_name_line_edit.values()):
            resources.append({
                "resource_name": widget.text(),
                "termination": self.resource_termination_combo_box[index].currentData() or "\r\n",
            })
        settings = QtCore.QSettings()
        settings.beginGroup("connection_dialog")
        settings.setValue("current_driver", self.driver_combo_box.currentText())
        settings.setValue("resources", resources)
        settings.endGroup()

    def update_inputs(self, index: int) -> None:
        name = self.driver_combo_box.itemText(index)
        appliance = self.driver_combo_box.itemData(index)
        resources = appliance.get("resources", 0)
        for index, lineEdit in enumerate(self.resource_name_line_edit.values()):
            lineEdit.setEnabled(resources > index)
        for index, comboBox in enumerate(self.resource_termination_combo_box.values()):
            comboBox.setEnabled(resources > index)

    def get_resource(self, index: int) -> dict:
        resource_name = utils.get_resource_name(self.resource_name_line_edit[index].text())
        visa_library = utils.get_visa_library(resource_name)
        termination = self.resource_termination_combo_box[index].currentData()
        return {
            "resource_name": resource_name,
            "visa_library": visa_library,
            "options": {
                "read_termination": termination,
                "write_termination": termination,
            },
        }

    def add_appliance(self, name: str, appliance: dict) -> None:
        self.driver_combo_box.addItem(name, appliance)

    def appliance(self) -> Appliance:
        name = self.driver_combo_box.currentText()
        appliance = self.driver_combo_box.currentData()
        driver = appliance.get("driver")
        resources = []
        for index in range(appliance.get("resources", 0)):
            resources.append(self.get_resource(index))
        return Appliance(name, driver, resources)
