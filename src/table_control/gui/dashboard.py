from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets


def decode_calibration(value: int) -> str:
    return {0x1: "CAL", 0x2: "RM", 0x3: "CAL+RM"}.get(value, "NONE")


class DashboardWidget(QtWidgets.QWidget):

    moveRequested = QtCore.pyqtSignal()

    def __init__(self, tableController, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.tableController = tableController

        self.xPosSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.xPosSpinBox.setButtonSymbols(QtWidgets.QDoubleSpinBox.NoButtons)
        self.xPosSpinBox.setReadOnly(True)
        self.xPosSpinBox.setDecimals(3)
        self.xPosSpinBox.setRange(-10000, 10000)
        self.xPosSpinBox.setSuffix(" mm")

        self.yPosSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.yPosSpinBox.setButtonSymbols(QtWidgets.QDoubleSpinBox.NoButtons)
        self.yPosSpinBox.setReadOnly(True)
        self.yPosSpinBox.setDecimals(3)
        self.yPosSpinBox.setRange(-10000, 10000)
        self.yPosSpinBox.setSuffix(" mm")

        self.zPosSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.zPosSpinBox.setButtonSymbols(QtWidgets.QDoubleSpinBox.NoButtons)
        self.zPosSpinBox.setReadOnly(True)
        self.zPosSpinBox.setDecimals(3)
        self.zPosSpinBox.setRange(-10000, 10000)
        self.zPosSpinBox.setSuffix(" mm")

        self.xCalibrationLineEdit = QtWidgets.QLineEdit(self)
        self.xCalibrationLineEdit.setReadOnly(True)

        self.yCalibrationLineEdit = QtWidgets.QLineEdit(self)
        self.yCalibrationLineEdit.setReadOnly(True)

        self.zCalibrationLineEdit = QtWidgets.QLineEdit(self)
        self.zCalibrationLineEdit.setReadOnly(True)

        self.xyStepSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.xyStepSpinBox.setDecimals(3)
        self.xyStepSpinBox.setRange(0, 10000)
        self.xyStepSpinBox.setValue(1)
        self.xyStepSpinBox.setSuffix(" mm")

        self.leftButton = QtWidgets.QPushButton("-X")
        self.leftButton.clicked.connect(lambda: self.relativeMove(-abs(self.xyStepSpinBox.value()), 0, 0))

        self.rightButton = QtWidgets.QPushButton("+X")
        self.rightButton.clicked.connect(lambda: self.relativeMove(+abs(self.xyStepSpinBox.value()), 0, 0))

        self.topButton = QtWidgets.QPushButton("+Y")
        self.topButton.clicked.connect(lambda: self.relativeMove(0, +abs(self.xyStepSpinBox.value()), 0))

        self.bottomButton = QtWidgets.QPushButton("-Y")
        self.bottomButton.clicked.connect(lambda: self.relativeMove(0, -abs(self.xyStepSpinBox.value()), 0))

        self.zStepSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.zStepSpinBox.setDecimals(3)
        self.zStepSpinBox.setRange(0, 10000)
        self.zStepSpinBox.setValue(1)
        self.zStepSpinBox.setSuffix(" mm")

        self.upButton = QtWidgets.QPushButton("+Z")
        self.upButton.clicked.connect(lambda: self.relativeMove(0, 0, +abs(self.zStepSpinBox.value())))

        self.downButton = QtWidgets.QPushButton("-Z")
        self.downButton.clicked.connect(lambda: self.relativeMove(0, 0, -abs(self.zStepSpinBox.value())))

        self.xRelSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.xRelSpinBox.setDecimals(3)
        self.xRelSpinBox.setRange(-10000, 10000)
        self.xRelSpinBox.setValue(0)
        self.xRelSpinBox.setSuffix(" mm")

        self.yRelSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.yRelSpinBox.setDecimals(3)
        self.yRelSpinBox.setRange(-10000, 10000)
        self.yRelSpinBox.setValue(0)
        self.yRelSpinBox.setSuffix(" mm")

        self.zRelSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.zRelSpinBox.setDecimals(3)
        self.zRelSpinBox.setRange(-10000, 10000)
        self.zRelSpinBox.setValue(0)
        self.zRelSpinBox.setSuffix(" mm")

        self.moveRelButton = QtWidgets.QPushButton("Move Rel")
        self.moveRelButton.clicked.connect(lambda: self.relativeMove(self.xRelSpinBox.value(), self.yRelSpinBox.value(), self.zRelSpinBox.value()))

        self.xAbsSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.xAbsSpinBox.setDecimals(3)
        self.xAbsSpinBox.setRange(0, 10000)
        self.xAbsSpinBox.setValue(0)
        self.xAbsSpinBox.setSuffix(" mm")

        self.yAbsSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.yAbsSpinBox.setDecimals(3)
        self.yAbsSpinBox.setRange(0, 10000)
        self.yAbsSpinBox.setValue(0)
        self.yAbsSpinBox.setSuffix(" mm")

        self.zAbsSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.zAbsSpinBox.setDecimals(3)
        self.zAbsSpinBox.setRange(0, 10000)
        self.zAbsSpinBox.setValue(0)
        self.zAbsSpinBox.setSuffix(" mm")

        self.moveAbsButton = QtWidgets.QPushButton("Move Abs")
        self.moveAbsButton.clicked.connect(lambda: self.absoluteMove(self.xAbsSpinBox.value(), self.yAbsSpinBox.value(), self.zAbsSpinBox.value()))

        self.clearRelButton = QtWidgets.QPushButton("Clear")
        self.clearRelButton.setMaximumWidth(48)
        self.clearRelButton.clicked.connect(self.clearRelPos)

        self.clearAbsButton = QtWidgets.QPushButton("Clear")
        self.clearAbsButton.setMaximumWidth(48)
        self.clearAbsButton.clicked.connect(self.clearAbsPos)

        self.loadAbsButton = QtWidgets.QPushButton("Load")
        self.loadAbsButton.setMaximumWidth(48)
        self.loadAbsButton.clicked.connect(self.loadAbsPos)

        self.xCalButton = QtWidgets.QPushButton("Cal")
        self.xCalButton.setMaximumWidth(54)
        self.xCalButton.clicked.connect(lambda: self.calibrate(True, False, False))
        self.xRmButton = QtWidgets.QPushButton("Rm")
        self.xRmButton.setMaximumWidth(54)
        self.xRmButton.clicked.connect(lambda: self.rangeMeasure(True, False, False))
        self.yCalButton = QtWidgets.QPushButton("Cal")
        self.yCalButton.setMaximumWidth(54)
        self.yCalButton.clicked.connect(lambda: self.calibrate(False, True, False))
        self.yRmButton = QtWidgets.QPushButton("Rm")
        self.yRmButton.setMaximumWidth(54)
        self.yRmButton.clicked.connect(lambda: self.rangeMeasure(False, True, False))
        self.zCalButton = QtWidgets.QPushButton("Cal")
        self.zCalButton.setMaximumWidth(54)
        self.zCalButton.clicked.connect(lambda: self.calibrate(False, False, True))
        self.zRmButton = QtWidgets.QPushButton("Rm")
        self.zRmButton.setMaximumWidth(54)
        self.zRmButton.clicked.connect(lambda: self.rangeMeasure(False, False, True))

        self.updateIntervalSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.updateIntervalSpinBox.setDecimals(2)
        self.updateIntervalSpinBox.setRange(0.01, 60.)
        self.updateIntervalSpinBox.setValue(1)
        self.updateIntervalSpinBox.setSingleStep(0.25)
        self.updateIntervalSpinBox.setSuffix(" s")
        self.updateIntervalSpinBox.valueChanged.connect(self.updateInterval)

        positionLayout = QtWidgets.QGridLayout()
        positionLayout.addWidget(QtWidgets.QLabel("X"), 0, 0)
        positionLayout.addWidget(QtWidgets.QLabel("Y"), 0, 1)
        positionLayout.addWidget(QtWidgets.QLabel("Z"), 0, 2)
        positionLayout.addWidget(self.xPosSpinBox, 1, 0)
        positionLayout.addWidget(self.yPosSpinBox, 1, 1)
        positionLayout.addWidget(self.zPosSpinBox, 1, 2)
        positionLayout.setColumnStretch(0, 1)
        positionLayout.setColumnStretch(1, 1)
        positionLayout.setColumnStretch(2, 1)
        positionLayout.setColumnStretch(3, 1)
        positionLayout.setColumnStretch(4, 1)

        xCalibrationLayout = QtWidgets.QHBoxLayout()
        xCalibrationLayout.addWidget(self.xCalButton)
        xCalibrationLayout.addWidget(self.xRmButton)

        yCalibrationLayout = QtWidgets.QHBoxLayout()
        yCalibrationLayout.addWidget(self.yCalButton)
        yCalibrationLayout.addWidget(self.yRmButton)

        zCalibrationLayout = QtWidgets.QHBoxLayout()
        zCalibrationLayout.addWidget(self.zCalButton)
        zCalibrationLayout.addWidget(self.zRmButton)

        calibrationLayout = QtWidgets.QGridLayout()
        calibrationLayout.addWidget(QtWidgets.QLabel("X"), 0, 0)
        calibrationLayout.addWidget(QtWidgets.QLabel("Y"), 0, 1)
        calibrationLayout.addWidget(QtWidgets.QLabel("Z"), 0, 2)
        calibrationLayout.addWidget(self.xCalibrationLineEdit, 1, 0)
        calibrationLayout.addWidget(self.yCalibrationLineEdit, 1, 1)
        calibrationLayout.addWidget(self.zCalibrationLineEdit, 1, 2)
        calibrationLayout.addLayout(xCalibrationLayout, 2, 0)
        calibrationLayout.addLayout(yCalibrationLayout, 2, 1)
        calibrationLayout.addLayout(zCalibrationLayout, 2, 2)
        calibrationLayout.setColumnStretch(0, 1)
        calibrationLayout.setColumnStretch(1, 1)
        calibrationLayout.setColumnStretch(2, 1)
        calibrationLayout.setColumnStretch(3, 1)
        calibrationLayout.setColumnStretch(4, 1)

        buttonLayout = QtWidgets.QGridLayout()
        buttonLayout.addWidget(self.xyStepSpinBox, 1, 1)
        buttonLayout.addWidget(self.leftButton, 1, 0)
        buttonLayout.addWidget(self.rightButton, 1, 2)
        buttonLayout.addWidget(self.topButton, 0, 1)
        buttonLayout.addWidget(self.bottomButton, 2, 1)

        buttonLayout.addWidget(self.upButton, 0, 3)
        buttonLayout.addWidget(self.zStepSpinBox, 1, 3)
        buttonLayout.addWidget(self.downButton, 2, 3)

        buttonLayout.addWidget(QtWidgets.QLabel("X"), 4, 0)
        buttonLayout.addWidget(QtWidgets.QLabel("Y"), 4, 1)
        buttonLayout.addWidget(QtWidgets.QLabel("Z"), 4, 2)

        buttonLayout.addWidget(self.xRelSpinBox, 5, 0)
        buttonLayout.addWidget(self.yRelSpinBox, 5, 1)
        buttonLayout.addWidget(self.zRelSpinBox, 5, 2)
        buttonLayout.addWidget(self.moveRelButton, 5, 3)
        buttonLayout.addWidget(self.clearRelButton, 5, 4)

        buttonLayout.addWidget(self.xAbsSpinBox, 6, 0)
        buttonLayout.addWidget(self.yAbsSpinBox, 6, 1)
        buttonLayout.addWidget(self.zAbsSpinBox, 6, 2)
        buttonLayout.addWidget(self.moveAbsButton, 6, 3)
        buttonLayout.addWidget(self.clearAbsButton, 6, 4)
        buttonLayout.addWidget(self.loadAbsButton, 6, 6)

        bottomLayout = QtWidgets.QGridLayout()
        bottomLayout.addWidget(QtWidgets.QLabel("Update Interval"), 0, 0, 1, 4)
        bottomLayout.addWidget(self.updateIntervalSpinBox, 1, 0)

        self.controllerLabel = QtWidgets.QLabel(self)

        leftLayout = QtWidgets.QVBoxLayout()
        leftLayout.addWidget(QtWidgets.QLabel("Controller"))
        leftLayout.addWidget(self.controllerLabel)
        leftLayout.addWidget(QtWidgets.QLabel("Position"))
        leftLayout.addLayout(positionLayout)
        leftLayout.addWidget(QtWidgets.QLabel("Calibration"))
        leftLayout.addLayout(calibrationLayout)
        leftLayout.addWidget(QtWidgets.QLabel("Movement"))
        leftLayout.addLayout(buttonLayout)
        leftLayout.addLayout(bottomLayout)
        leftLayout.addStretch(1)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addLayout(leftLayout)
        layout.addStretch(1)

        self.controlWidgets: list[QtWidgets.QWidget] = [
            self.leftButton,
            self.rightButton,
            self.topButton,
            self.bottomButton,
            self.upButton,
            self.downButton,
            self.moveRelButton,
            self.moveAbsButton,
            self.xCalButton,
            self.yCalButton,
            self.zCalButton,
            self.xRmButton,
            self.yRmButton,
            self.zRmButton,
        ]

    def enterDisconnected(self) -> None:
        self.setEnabled(False)
        self.clearState()

    def enterConnected(self) -> None:
        self.setEnabled(True)
        for widget in self.controlWidgets:
            widget.setEnabled(True)

    def enterMoving(self) -> None:
        for widget in self.controlWidgets:
            widget.setEnabled(False)

    def clearRelPos(self) -> None:
        self.xRelSpinBox.setValue(0)
        self.yRelSpinBox.setValue(0)
        self.zRelSpinBox.setValue(0)

    def clearAbsPos(self) -> None:
        self.xAbsSpinBox.setValue(0)
        self.yAbsSpinBox.setValue(0)
        self.zAbsSpinBox.setValue(0)

    def loadAbsPos(self) -> None:
        self.xAbsSpinBox.setValue(self.xPosSpinBox.value())
        self.yAbsSpinBox.setValue(self.yPosSpinBox.value())
        self.zAbsSpinBox.setValue(self.zPosSpinBox.value())

    def setController(self, info) -> None:
        self.controllerLabel.setText(format(info))

    def setTablePosition(self, x, y, z) -> None:
        self.xPosSpinBox.setValue(x)
        self.yPosSpinBox.setValue(y)
        self.zPosSpinBox.setValue(z)

    def setTableCalibration(self, x, y, z) -> None:
        x, y, z = map(decode_calibration, [x, y, z])
        self.xCalibrationLineEdit.setText(format(x))
        self.yCalibrationLineEdit.setText(format(y))
        self.zCalibrationLineEdit.setText(format(z))

    def relativeMove(self, x, y, z) -> None:
        self.moveRequested.emit()
        self.tableController.moveRelative(x, y, z)

    def absoluteMove(self, x, y, z) -> None:
        self.moveRequested.emit()
        self.tableController.moveAbsolute(x, y, z)

    def calibrate(self, x, y, z) -> None:
        self.moveRequested.emit()
        self.tableController.calibrate(x, y, z)

    def rangeMeasure(self, x, y, z) -> None:
        self.moveRequested.emit()
        self.tableController.rangeMeasure(x, y, z)

    def updateInterval(self, interval: float) -> None:
        self.tableController.setUpdateInterval(interval)

    def clearState(self) -> None:
        self.controllerLabel.clear()
        self.xPosSpinBox.clear()
        self.yPosSpinBox.clear()
        self.zPosSpinBox.clear()
        self.xCalibrationLineEdit.clear()
        self.yCalibrationLineEdit.clear()
        self.zCalibrationLineEdit.clear()
