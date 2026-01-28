from PySide6 import QtCore, QtGui, QtWidgets

from .positions import TablePositionsWidget, TablePosition
from .utils import load_icon, FlashLabel


def decode_calibration(value: int) -> str:
    return {0x1: "CAL", 0x2: "RM", 0x3: "CAL+RM"}.get(value, "NONE")


class DashboardWidget(QtWidgets.QWidget):

    move_requested = QtCore.Signal()
    relative_move_requested = QtCore.Signal(float, float, float)
    absolute_move_requested = QtCore.Signal(float, float, float)
    calibrate_requested = QtCore.Signal(bool ,bool, bool)
    range_measure_requested = QtCore.Signal(bool ,bool, bool)
    stop_requested = QtCore.Signal()
    update_interval_changed = QtCore.Signal(float)
    z_limit_enabled_changed = QtCore.Signal(bool)
    z_limit_changed = QtCore.Signal(float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.x_pos_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.x_pos_spin_box.setButtonSymbols(QtWidgets.QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.x_pos_spin_box.setReadOnly(True)
        self.x_pos_spin_box.setDecimals(6)
        self.x_pos_spin_box.setRange(-10000, 10000)
        self.x_pos_spin_box.setSuffix(" mm")

        self.y_pos_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.y_pos_spin_box.setButtonSymbols(QtWidgets.QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.y_pos_spin_box.setReadOnly(True)
        self.y_pos_spin_box.setDecimals(6)
        self.y_pos_spin_box.setRange(-10000, 10000)
        self.y_pos_spin_box.setSuffix(" mm")

        self.z_pos_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.z_pos_spin_box.setButtonSymbols(QtWidgets.QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.z_pos_spin_box.setReadOnly(True)
        self.z_pos_spin_box.setDecimals(6)
        self.z_pos_spin_box.setRange(-10000, 10000)
        self.z_pos_spin_box.setSuffix(" mm")

        self.pos_flash_label = FlashLabel(flash_duration_ms=250)

        self.x_calibration_line_edit = QtWidgets.QLineEdit(self)
        self.x_calibration_line_edit.setReadOnly(True)

        self.y_calibration_line_edit = QtWidgets.QLineEdit(self)
        self.y_calibration_line_edit.setReadOnly(True)

        self.z_calibration_line_edit = QtWidgets.QLineEdit(self)
        self.z_calibration_line_edit.setReadOnly(True)

        self.xy_step_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.xy_step_spin_box.setDecimals(6)
        self.xy_step_spin_box.setRange(0, 10000)
        self.xy_step_spin_box.setValue(1)
        self.xy_step_spin_box.setSuffix(" mm")

        self.left_button = QtWidgets.QPushButton("-X")
        self.left_button.clicked.connect(lambda: self.relative_move(-abs(self.xy_step_spin_box.value()), 0, 0))

        self.right_button = QtWidgets.QPushButton("+X")
        self.right_button.clicked.connect(lambda: self.relative_move(+abs(self.xy_step_spin_box.value()), 0, 0))

        self.top_button = QtWidgets.QPushButton("+Y")
        self.top_button.clicked.connect(lambda: self.relative_move(0, +abs(self.xy_step_spin_box.value()), 0))

        self.bottom_button = QtWidgets.QPushButton("-Y")
        self.bottom_button.clicked.connect(lambda: self.relative_move(0, -abs(self.xy_step_spin_box.value()), 0))

        self.z_step_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.z_step_spin_box.setDecimals(6)
        self.z_step_spin_box.setRange(0, 10000)
        self.z_step_spin_box.setValue(1)
        self.z_step_spin_box.setSuffix(" mm")

        self.up_button = QtWidgets.QPushButton("+Z")
        self.up_button.clicked.connect(lambda: self.relative_move(0, 0, +abs(self.z_step_spin_box.value())))

        self.down_button = QtWidgets.QPushButton("-Z")
        self.down_button.clicked.connect(lambda: self.relative_move(0, 0, -abs(self.z_step_spin_box.value())))

        self.x_rel_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.x_rel_spin_box.setDecimals(6)
        self.x_rel_spin_box.setRange(-10000, 10000)
        self.x_rel_spin_box.setValue(0)
        self.x_rel_spin_box.setSuffix(" mm")

        self.y_rel_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.y_rel_spin_box.setDecimals(6)
        self.y_rel_spin_box.setRange(-10000, 10000)
        self.y_rel_spin_box.setValue(0)
        self.y_rel_spin_box.setSuffix(" mm")

        self.z_rel_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.z_rel_spin_box.setDecimals(6)
        self.z_rel_spin_box.setRange(-10000, 10000)
        self.z_rel_spin_box.setValue(0)
        self.z_rel_spin_box.setSuffix(" mm")

        self.move_rel_button = QtWidgets.QPushButton("Move Rel")
        self.move_rel_button.clicked.connect(lambda: self.relative_move(self.x_rel_spin_box.value(), self.y_rel_spin_box.value(), self.z_rel_spin_box.value()))

        self.x_abs_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.x_abs_spin_box.setDecimals(6)
        self.x_abs_spin_box.setRange(0, 10000)
        self.x_abs_spin_box.setValue(0)
        self.x_abs_spin_box.setSuffix(" mm")

        self.y_abs_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.y_abs_spin_box.setDecimals(6)
        self.y_abs_spin_box.setRange(0, 10000)
        self.y_abs_spin_box.setValue(0)
        self.y_abs_spin_box.setSuffix(" mm")

        self.z_abs_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.z_abs_spin_box.setDecimals(6)
        self.z_abs_spin_box.setRange(0, 10000)
        self.z_abs_spin_box.setValue(0)
        self.z_abs_spin_box.setSuffix(" mm")

        self.move_abs_button = QtWidgets.QPushButton("Move Abs")
        self.move_abs_button.clicked.connect(lambda: self.absolute_move(self.x_abs_spin_box.value(), self.y_abs_spin_box.value(), self.z_abs_spin_box.value()))

        self.clear_rel_button = QtWidgets.QPushButton("Clear")
        self.clear_rel_button.setMaximumWidth(48)
        self.clear_rel_button.clicked.connect(self.clear_rel_pos)

        self.clear_abs_button = QtWidgets.QPushButton("Clear")
        self.clear_abs_button.setMaximumWidth(48)
        self.clear_abs_button.clicked.connect(self.clear_abs_pos)

        self.load_abs_button = QtWidgets.QPushButton("Load")
        self.load_abs_button.setMaximumWidth(48)
        self.load_abs_button.clicked.connect(self.load_abs_pos)

        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setIcon(load_icon("stop.svg"))
        self.stop_button.clicked.connect(self.stop_requested)

        self.x_cal_button = QtWidgets.QPushButton("Cal")
        self.x_cal_button.setMaximumWidth(54)
        self.x_cal_button.clicked.connect(lambda: self.calibrate(True, False, False))
        self.x_rm_button = QtWidgets.QPushButton("Rm")
        self.x_rm_button.setMaximumWidth(54)
        self.x_rm_button.clicked.connect(lambda: self.range_measure(True, False, False))

        self.y_cal_button = QtWidgets.QPushButton("Cal")
        self.y_cal_button.setMaximumWidth(54)
        self.y_cal_button.clicked.connect(lambda: self.calibrate(False, True, False))
        self.y_rm_button = QtWidgets.QPushButton("Rm")
        self.y_rm_button.setMaximumWidth(54)
        self.y_rm_button.clicked.connect(lambda: self.range_measure(False, True, False))

        self.z_cal_button = QtWidgets.QPushButton("Cal")
        self.z_cal_button.setMaximumWidth(54)
        self.z_cal_button.clicked.connect(lambda: self.calibrate(False, False, True))
        self.z_rm_button = QtWidgets.QPushButton("Rm")
        self.z_rm_button.setMaximumWidth(54)
        self.z_rm_button.clicked.connect(lambda: self.range_measure(False, False, True))

        self.update_interval_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.update_interval_spin_box.setDecimals(2)
        self.update_interval_spin_box.setRange(0.01, 60.)
        self.update_interval_spin_box.setValue(1)
        self.update_interval_spin_box.setSingleStep(0.25)
        self.update_interval_spin_box.setSuffix(" s")
        self.update_interval_spin_box.valueChanged.connect(self.update_interval_changed)

        self.z_limit_enabled_check_box = QtWidgets.QCheckBox(self)
        self.z_limit_enabled_check_box.setText("Move Abs Z-Limit")
        self.z_limit_enabled_check_box.toggled.connect(self.z_limit_enabled_changed)

        self.z_limit_spin_box = QtWidgets.QDoubleSpinBox(self)
        self.z_limit_spin_box.setDecimals(6)
        self.z_limit_spin_box.setRange(-10000, 10000)
        self.z_limit_spin_box.setSuffix(" mm")
        self.z_limit_spin_box.valueChanged.connect(self.z_limit_changed)

        self.control_widget = QtWidgets.QWidget(self)

        self.positions_widget = TablePositionsWidget(self)
        self.positions_widget.move_requested.connect(self.absolute_move)
        self.positions_widget.stop_requested.connect(self.stop_requested)

        self.calibration_widget = QtWidgets.QWidget(self)

        self.tab_widget = QtWidgets.QTabWidget(self)
        self.tab_widget.addTab(self.control_widget, "&Control")
        self.tab_widget.addTab(self.positions_widget, "&Positions")
        self.tab_widget.addTab(self.calibration_widget, "&Calibration")

        position_layout = QtWidgets.QGridLayout()
        position_layout.addWidget(QtWidgets.QLabel("X"), 0, 0)
        position_layout.addWidget(QtWidgets.QLabel("Y"), 0, 1)
        position_layout.addWidget(QtWidgets.QLabel("Z"), 0, 2)
        position_layout.addWidget(self.x_pos_spin_box, 1, 0)
        position_layout.addWidget(self.y_pos_spin_box, 1, 1)
        position_layout.addWidget(self.z_pos_spin_box, 1, 2)
        position_layout.addWidget(self.pos_flash_label, 1, 3)
        position_layout.setColumnStretch(0, 1)
        position_layout.setColumnStretch(1, 1)
        position_layout.setColumnStretch(2, 1)
        position_layout.setColumnStretch(3, 1)
        position_layout.setColumnStretch(4, 1)

        x_calibration_layout = QtWidgets.QHBoxLayout()
        x_calibration_layout.addWidget(self.x_cal_button)
        x_calibration_layout.addWidget(self.x_rm_button)

        y_calibration_layout = QtWidgets.QHBoxLayout()
        y_calibration_layout.addWidget(self.y_cal_button)
        y_calibration_layout.addWidget(self.y_rm_button)

        z_calibration_layout = QtWidgets.QHBoxLayout()
        z_calibration_layout.addWidget(self.z_cal_button)
        z_calibration_layout.addWidget(self.z_rm_button)

        calibration_layout = QtWidgets.QGridLayout()
        calibration_layout.addWidget(QtWidgets.QLabel("X"), 0, 0)
        calibration_layout.addWidget(QtWidgets.QLabel("Y"), 0, 1)
        calibration_layout.addWidget(QtWidgets.QLabel("Z"), 0, 2)
        calibration_layout.addWidget(self.x_calibration_line_edit, 1, 0)
        calibration_layout.addWidget(self.y_calibration_line_edit, 1, 1)
        calibration_layout.addWidget(self.z_calibration_line_edit, 1, 2)
        calibration_layout.setColumnStretch(0, 1)
        calibration_layout.setColumnStretch(1, 1)
        calibration_layout.setColumnStretch(2, 1)
        calibration_layout.setColumnStretch(3, 1)
        calibration_layout.setColumnStretch(4, 1)

        button_layout = QtWidgets.QGridLayout(self.control_widget)
        button_layout.addWidget(self.xy_step_spin_box, 1, 1)
        button_layout.addWidget(self.left_button, 1, 0)
        button_layout.addWidget(self.right_button, 1, 2)
        button_layout.addWidget(self.top_button, 0, 1)
        button_layout.addWidget(self.bottom_button, 2, 1)

        button_layout.addWidget(self.up_button, 0, 3)
        button_layout.addWidget(self.z_step_spin_box, 1, 3)
        button_layout.addWidget(self.down_button, 2, 3)

        button_layout.addWidget(QtWidgets.QLabel("X"), 4, 0)
        button_layout.addWidget(QtWidgets.QLabel("Y"), 4, 1)
        button_layout.addWidget(QtWidgets.QLabel("Z"), 4, 2)

        button_layout.addWidget(self.x_rel_spin_box, 5, 0)
        button_layout.addWidget(self.y_rel_spin_box, 5, 1)
        button_layout.addWidget(self.z_rel_spin_box, 5, 2)
        button_layout.addWidget(self.move_rel_button, 5, 3)
        button_layout.addWidget(self.clear_rel_button, 5, 4)

        button_layout.addWidget(self.x_abs_spin_box, 6, 0)
        button_layout.addWidget(self.y_abs_spin_box, 6, 1)
        button_layout.addWidget(self.z_abs_spin_box, 6, 2)
        button_layout.addWidget(self.move_abs_button, 6, 3)
        button_layout.addWidget(self.clear_abs_button, 6, 4)
        button_layout.addWidget(self.load_abs_button, 6, 6)

        button_layout.addWidget(self.stop_button, 7, 3)

        calibration_widget_layout = QtWidgets.QGridLayout(self.calibration_widget)
        calibration_widget_layout.addWidget(QtWidgets.QLabel("X"), 0, 0)
        calibration_widget_layout.addWidget(QtWidgets.QLabel("Y"), 0, 1)
        calibration_widget_layout.addWidget(QtWidgets.QLabel("Z"), 0, 2)
        calibration_widget_layout.addLayout(x_calibration_layout, 1, 0)
        calibration_widget_layout.addLayout(y_calibration_layout, 1, 1)
        calibration_widget_layout.addLayout(z_calibration_layout, 1, 2)
        calibration_widget_layout.setColumnStretch(3, 1)
        calibration_widget_layout.setRowStretch(2, 1)

        buttom_layout = QtWidgets.QGridLayout()
        buttom_layout.addWidget(QtWidgets.QLabel("Update Interval"), 0, 0, 1, 1)
        buttom_layout.addWidget(self.update_interval_spin_box, 1, 0)
        buttom_layout.addWidget(self.z_limit_enabled_check_box, 0, 1, 1, 4)
        buttom_layout.addWidget(self.z_limit_spin_box, 1, 1)

        self.controller_label = QtWidgets.QLabel(self)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(QtWidgets.QLabel("Controller"))
        left_layout.addWidget(self.controller_label)
        left_layout.addWidget(QtWidgets.QLabel("Position"))
        left_layout.addLayout(position_layout)
        left_layout.addWidget(QtWidgets.QLabel("Calibration"))
        left_layout.addLayout(calibration_layout)
        left_layout.addWidget(QtWidgets.QLabel("Commands"))
        left_layout.addWidget(self.tab_widget)
        left_layout.addLayout(buttom_layout)
        left_layout.addStretch(1)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addLayout(left_layout)
        layout.addStretch(1)

        self.control_widgets: list[QtWidgets.QWidget] = [
            self.left_button,
            self.right_button,
            self.top_button,
            self.bottom_button,
            self.up_button,
            self.down_button,
            self.move_rel_button,
            self.move_abs_button,
            self.x_cal_button,
            self.y_cal_button,
            self.z_cal_button,
            self.x_rm_button,
            self.y_rm_button,
            self.z_rm_button,
            self.z_limit_enabled_check_box,
            self.z_limit_spin_box,
        ]

    def update_interval(self) -> float:
        return self.update_interval_spin_box.value()

    def set_update_interval(self, interval: float) -> None:
        return self.update_interval_spin_box.setValue(interval)

    def z_limit_enabled(self) -> bool:
        return self.z_limit_enabled_check_box.isChecked()

    def set_z_limit_enabled(self, enabled: bool) -> None:
        return self.z_limit_enabled_check_box.setChecked(enabled)

    def z_limit(self) -> float:
        return self.z_limit_spin_box.value()

    def set_z_limit(self, value: float) -> None:
        return self.z_limit_spin_box.setValue(value)

    def clear_rel_pos(self) -> None:
        self.x_rel_spin_box.setValue(0)
        self.y_rel_spin_box.setValue(0)
        self.z_rel_spin_box.setValue(0)

    def clear_abs_pos(self) -> None:
        self.x_abs_spin_box.setValue(0)
        self.y_abs_spin_box.setValue(0)
        self.z_abs_spin_box.setValue(0)

    def load_abs_pos(self) -> None:
        self.x_abs_spin_box.setValue(self.x_pos_spin_box.value())
        self.y_abs_spin_box.setValue(self.y_pos_spin_box.value())
        self.z_abs_spin_box.setValue(self.z_pos_spin_box.value())

    def set_controller(self, info) -> None:
        self.controller_label.setText(format(info))

    def set_table_position(self, x, y, z) -> None:
        self.x_pos_spin_box.setValue(x)
        self.y_pos_spin_box.setValue(y)
        self.z_pos_spin_box.setValue(z)
        self.pos_flash_label.flash()

    def set_table_calibration(self, x, y, z) -> None:
        x, y, z = map(decode_calibration, [x, y, z])
        self.x_calibration_line_edit.setText(format(x))
        self.y_calibration_line_edit.setText(format(y))
        self.z_calibration_line_edit.setText(format(z))

    def clear_positions(self) -> None:
        self.positions_widget.clear_positions()

    def add_position(self, position: TablePosition) -> None:
        self.positions_widget.add_position(position)

    def positions(self) -> list[TablePosition]:
        return self.positions_widget.positions()

    def enter_disconnected(self) -> None:
        self.positions_widget.enter_disconnected()
        self.setEnabled(False)
        self.clear_state()

    def enter_connected(self) -> None:
        self.positions_widget.enter_connected()
        self.setEnabled(True)
        for widget in self.control_widgets:
            widget.setEnabled(True)

    def enter_moving(self) -> None:
        self.positions_widget.enter_moving()
        for widget in self.control_widgets:
            widget.setEnabled(False)

    def relative_move(self, x, y, z) -> None:
        self.move_requested.emit()
        self.relative_move_requested.emit(x, y, z)

    def absolute_move(self, x, y, z) -> None:
        self.move_requested.emit()
        self.absolute_move_requested.emit(x, y, z)

    def calibrate(self, x, y, z) -> None:
        self.move_requested.emit()
        self.calibrate_requested.emit(x, y, z)
        if x:
            self.x_calibration_line_edit.clear()
        if y:
            self.y_calibration_line_edit.clear()
        if z:
            self.z_calibration_line_edit.clear()

    def range_measure(self, x, y, z) -> None:
        self.move_requested.emit()
        self.range_measure_requested.emit(x, y, z)
        if x:
            self.x_calibration_line_edit.clear()
        if y:
            self.y_calibration_line_edit.clear()
        if z:
            self.z_calibration_line_edit.clear()

    def clear_state(self) -> None:
        self.controller_label.clear()
        self.x_pos_spin_box.clear()
        self.y_pos_spin_box.clear()
        self.z_pos_spin_box.clear()
        self.x_calibration_line_edit.clear()
        self.y_calibration_line_edit.clear()
        self.z_calibration_line_edit.clear()
