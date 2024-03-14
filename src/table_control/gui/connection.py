import logging
from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ..core.resource import Resource
from ..core import utils

from .controller import Appliance

logger = logging.getLogger(__name__)


class ConnectionDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Connection")

        self.driverComboBox = QtWidgets.QComboBox(self)

        self.resourceNameLineEdit = {}
        self.resourceNameLineEdit[0] = QtWidgets.QLineEdit(self)
        self.resourceNameLineEdit[1] = QtWidgets.QLineEdit(self)

        self.resourceTerminationComboBox = {}
        self.resourceTerminationComboBox[0] = QtWidgets.QComboBox()
        self.resourceTerminationComboBox[0].addItem("CR+LF", "\r\n")
        self.resourceTerminationComboBox[0].addItem("CR", "\r")
        self.resourceTerminationComboBox[0].addItem("LF", "\n")
        self.resourceTerminationComboBox[1] = QtWidgets.QComboBox()
        self.resourceTerminationComboBox[1].addItem("CR+LF", "\r\n")
        self.resourceTerminationComboBox[1].addItem("CR", "\r")
        self.resourceTerminationComboBox[1].addItem("LF", "\n")

        self.widget = QtWidgets.QWidget(self)

        layout1 = QtWidgets.QVBoxLayout(self.widget)
        layout1.addWidget(QtWidgets.QLabel("Controller"))
        layout1.addWidget(self.driverComboBox)
        layout1.addWidget(QtWidgets.QLabel("Resource 1"))
        layout1.addWidget(self.resourceNameLineEdit[0])
        layout1.addWidget(self.resourceTerminationComboBox[0])
        layout1.addWidget(QtWidgets.QLabel("Resource 2"))
        layout1.addWidget(self.resourceNameLineEdit[1])
        layout1.addWidget(self.resourceTerminationComboBox[1])

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.widget)
        layout.addWidget(self.buttonBox)

        self.driverComboBox.currentIndexChanged.connect(self.updateInputs)

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("connectiondialog")
        currentDriver = settings.value("currentDriver", "", str)
        resources = settings.value("resources", [], list)
        settings.endGroup()
        index = self.driverComboBox.findText(currentDriver)
        self.driverComboBox.setCurrentIndex(max(0, index))
        for index, widget in enumerate(self.resourceNameLineEdit.values()):
            if index < len(resources):
                widget.setText(resources[index].get("resource_name", ""))
                self.resourceTerminationComboBox[index].setCurrentIndex(self.resourceTerminationComboBox[index].findData(resources[index].get("termination", "\r\n")))

    def writeSettings(self) -> None:
        resources = []
        for index, widget in enumerate(self.resourceNameLineEdit.values()):
            resources.append({
                "resource_name": widget.text(),
                "termination": self.resourceTerminationComboBox[index].currentData() or "\r\n",
            })
        settings = QtCore.QSettings()
        settings.beginGroup("connectiondialog")
        settings.setValue("currentDriver", self.driverComboBox.currentText())
        settings.setValue("resources", resources)
        settings.endGroup()

    def updateInputs(self, index: int) -> None:
        name = self.driverComboBox.itemText(index)
        appliance = self.driverComboBox.itemData(index)
        resources = appliance.get("resources", 0)
        for index, widget in enumerate(self.resourceNameLineEdit.values()):
            widget.setEnabled(resources > index)
        for index, widget in enumerate(self.resourceTerminationComboBox.values()):
            widget.setEnabled(resources > index)

    def getResource(self, index: int) -> dict:
        resource_name = utils.get_resource_name(self.resourceNameLineEdit[index].text())
        visa_library = utils.get_visa_library(resource_name)
        termination = self.resourceTerminationComboBox[index].currentData()
        return {
            "resource_name": resource_name,
            "visa_library": visa_library,
            "options": {
                "read_termination": termination,
                "write_termination": termination,
            },
        }

    def addAppliance(self, name: str, appliance: dict) -> None:
        self.driverComboBox.addItem(name, appliance)

    def appliance(self) -> Appliance:
        name = self.driverComboBox.currentText()
        appliance = self.driverComboBox.currentData()
        driver = appliance.get("driver")
        resources = []
        for index in range(appliance.get("resources", 0)):
            resources.append(self.getResource(index))
        return Appliance(name, driver, resources)
