import asyncio
import logging
import threading
import traceback
import webbrowser

from PySide6 import QtCore, QtGui, QtStateMachine, QtWidgets

from ..core.driver import Driver
from ..core.pluginmanager import PluginManager

from . import APP_TITLE, APP_VERSION, APP_CONTENTS_URL
from .preferences import PreferencesDialog
from .controller import TableController
from .connection import ConnectionConfig, ConnectionDialog
from .dashboard import DashboardWidget, TablePosition
from .utils import load_icon, load_text


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.settings = QtCore.QSettings()

        self.plugin_manager = PluginManager()

        self.table_controller = TableController()
        self.table_controller.failed.connect(self.show_exception)

        self.connection_configs: dict[str, ConnectionConfig] = {}

        self.quit_action = QtGui.QAction(self)
        self.quit_action.setText("&Quit")
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)

        self.preferences_action = QtGui.QAction(self)
        self.preferences_action.setText("&Preferences")
        self.preferences_action.triggered.connect(self.show_preferences)

        self.connect_action = QtGui.QAction(self)
        self.connect_action.setText("&Connect")
        self.connect_action.setIcon(load_icon("connect.svg"))
        self.connect_action.triggered.connect(self.connect_table)

        self.disconnect_action = QtGui.QAction(self)
        self.disconnect_action.setText("&Disconnect")
        self.disconnect_action.setIcon(load_icon("disconnect.svg"))
        self.disconnect_action.triggered.connect(self.disconnect_table)

        self.stop_action = QtGui.QAction(self)
        self.stop_action.setText("&Stop")
        self.stop_action.setIcon(load_icon("stop.svg"))
        self.stop_action.setShortcut("Ctrl+P")
        self.stop_action.triggered.connect(self.abort)

        self.joystick_action = QtGui.QAction(self)
        self.joystick_action.setCheckable(True)
        self.joystick_action.setText("&Joystick")
        self.joystick_action.setIcon(load_icon("joystick.svg"))
        self.joystick_action.toggled.connect(self.request_enable_joystick)

        self.contents_action = QtGui.QAction(self)
        self.contents_action.setShortcut("F1")
        self.contents_action.setText("&Contents")
        self.contents_action.triggered.connect(self.show_contents)

        self.about_qt_action = QtGui.QAction(self)
        self.about_qt_action.setText("About &Qt")
        self.about_qt_action.triggered.connect(self.show_about_qt)

        self.about_action = QtGui.QAction(self)
        self.about_action.setText("&About")
        self.about_action.triggered.connect(self.show_about)

        self.file_menu = self.menuBar().addMenu("&File")
        self.file_menu.addAction(self.quit_action)

        self.edit_menu = self.menuBar().addMenu("&Edit")
        self.edit_menu.addAction(self.preferences_action)

        self.view_menu = self.menuBar().addMenu("&View")
        self.view_menu.menuAction().setVisible(False)  # not used at default

        self.table_menu = self.menuBar().addMenu("&Table")
        self.table_menu.addAction(self.connect_action)
        self.table_menu.addAction(self.disconnect_action)
        self.table_menu.addSeparator()
        self.table_menu.addAction(self.joystick_action)
        self.table_menu.addSeparator()
        self.table_menu.addAction(self.stop_action)

        self.help_menu = self.menuBar().addMenu("&Help")
        self.help_menu.addAction(self.contents_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.about_qt_action)
        self.help_menu.addAction(self.about_action)

        # Toolbars

        self.main_tool_bar = self.addToolBar("main")
        self.main_tool_bar.setObjectName("main_tool_bar")
        self.main_tool_bar.addActions(self.table_menu.actions())

        # Central widget

        self.dashboard = DashboardWidget(self)
        self.setCentralWidget(self.dashboard)

        self.dashboard.relative_move_requested.connect(self.table_controller.move_relative)
        self.dashboard.absolute_move_requested.connect(self.table_controller.move_absolute)
        self.dashboard.calibrate_requested.connect(self.table_controller.calibrate)
        self.dashboard.range_measure_requested.connect(self.table_controller.range_measure)
        self.dashboard.stop_requested.connect(self.stop_action.trigger)
        self.dashboard.update_interval_changed.connect(self.table_controller.set_update_interval)
        self.dashboard.z_limit_enabled_changed.connect(self.table_controller.set_z_limit_enabled)
        self.dashboard.z_limit_changed.connect(self.table_controller.set_z_limit)
        self.table_controller.info_changed.connect(self.dashboard.set_controller)
        self.table_controller.position_changed.connect(self.dashboard.set_table_position)
        self.table_controller.calibration_changed.connect(self.dashboard.set_table_calibration)

        # Status bar

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()

        self.statusBar().addPermanentWidget(self.progress_bar)

        self.connected_state = QtStateMachine.QState()
        self.connected_state.entered.connect(self.enter_connected)

        self.disconnected_state = QtStateMachine.QState()
        self.disconnected_state.entered.connect(self.enter_disconnected)

        self.moving_state = QtStateMachine.QState()
        self.moving_state.entered.connect(self.enter_moving)

        self.connected_state.addTransition(self.table_controller.disconnected, self.disconnected_state)
        self.disconnected_state.addTransition(self.table_controller.connected, self.connected_state)
        self.disconnected_state.addTransition(self.table_controller.disconnected, self.disconnected_state)
        self.connected_state.addTransition(self.dashboard.move_requested, self.moving_state)
        self.moving_state.addTransition(self.table_controller.movement_finished, self.connected_state)
        self.moving_state.addTransition(self.table_controller.disconnected, self.disconnected_state)

        self.state_machine = QtStateMachine.QStateMachine(self)
        self.state_machine.addState(self.connected_state)
        self.state_machine.addState(self.disconnected_state)
        self.state_machine.addState(self.moving_state)
        self.state_machine.setInitialState(self.disconnected_state)
        self.state_machine.start()

        self.sync_controller()

    def register_plugin(self, plugin) -> None:
        self.plugin_manager.register_plugin(plugin)

    def install_plugins(self) -> None:
        self.plugin_manager.dispatch("install", (self,))

    def uninstall_plugins(self) -> None:
        self.plugin_manager.dispatch("uninstall", (self,))

    def register_connection(self, name: str, driver_cls: type[Driver], n_resources: int) -> None:
        self.connection_configs.update({name: ConnectionConfig(name, driver_cls, n_resources)})

    def read_settings(self) -> None:
        settings = self.settings
        self.plugin_manager.dispatch("before_read_settings", (settings,))
        settings.beginGroup("mainwindow")

        geometry: QtCore.QByteArray = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)  # type: ignore
        state: QtCore.QByteArray = settings.value("state", QtCore.QByteArray(), QtCore.QByteArray)  # type: ignore
        updateInterval: float = settings.value("update_interval", 1.0, float)  # type: ignore
        z_limit_enabled: bool = settings.value("z_limit_enabled", False, bool)  # type: ignore
        z_limit: float = settings.value("z_limit", 0.0, float)  # type: ignore
        self.restoreGeometry(geometry)
        self.restoreState(state)
        self.dashboard.set_update_interval(updateInterval)
        self.dashboard.set_z_limit_enabled(z_limit_enabled)
        self.dashboard.set_z_limit(z_limit)

        # Positions
        self.dashboard.clear_positions()
        size = settings.beginReadArray("positions")
        for i in range(size):
            settings.setArrayIndex(i)
            name = settings.value("name", "", type=str)
            x = settings.value("x", 0.0, type=float)
            y = settings.value("y", 0.0, type=float)
            z = settings.value("z", 0.0, type=float)
            comment = settings.value("comment", "", type=str)
            self.dashboard.add_position(TablePosition(name, x, y, z, comment))  # type: ignore
        settings.endArray()

        settings.endGroup()
        self.plugin_manager.dispatch("after_read_settings", (settings,))

    def write_settings(self) -> None:
        settings = self.settings
        self.plugin_manager.dispatch("before_write_settings", (settings,))
        settings.beginGroup("mainwindow")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.setValue("update_interval", self.dashboard.update_interval())
        settings.setValue("z_limit_enabled", self.dashboard.z_limit_enabled())
        settings.setValue("z_limit", self.dashboard.z_limit())

        # Positions
        positions = self.dashboard.positions()
        settings.beginWriteArray("positions", len(positions))
        for i, p in enumerate(positions):
            settings.setArrayIndex(i)
            settings.setValue("name", p.name)
            settings.setValue("x", p.x)
            settings.setValue("y", p.y)
            settings.setValue("z", p.z)
            settings.setValue("comment", p.comment)
        settings.endArray()

        settings.endGroup()
        self.plugin_manager.dispatch("after_write_settings", (settings,))

    def sync_controller(self) -> None:
        self.table_controller.update_interval = self.dashboard.update_interval()
        self.table_controller.set_z_limit_enabled(self.dashboard.z_limit_enabled())
        self.table_controller.set_z_limit(self.dashboard.z_limit())

    @QtCore.Slot()
    def show_preferences(self) -> None:
        dialog = PreferencesDialog(self)
        dialog.read_settings(self.settings)
        self.plugin_manager.dispatch("before_preferences", (dialog,))
        dialog.exec()
        self.plugin_manager.dispatch("after_preferences", (dialog,))
        dialog.write_settings(self.settings)

    @QtCore.Slot()
    def show_contents(self) -> None:
        webbrowser.open(APP_CONTENTS_URL)

    @QtCore.Slot()
    def show_about_qt(self) -> None:
        QtWidgets.QMessageBox.aboutQt(self, "About Qt")

    @QtCore.Slot()
    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(self, "About", load_text("about.txt").format(title=APP_TITLE, version=APP_VERSION))

    @QtCore.Slot(Exception)
    def show_exception(self, exc) -> None:
        details = "".join(traceback.format_tb(exc.__traceback__))
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Exception")
        dialog.setText(format(exc))
        dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        dialog.setDetailedText(details)
        dialog.setStandardButtons(dialog.StandardButton.Ok)
        dialog.setDefaultButton(dialog.StandardButton.Ok)
        # Fix message box width
        spacer = QtWidgets.QSpacerItem(448, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        layout = dialog.layout()
        if isinstance(layout, QtWidgets.QGridLayout):
            layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        dialog.exec()

    def setup_connection(self) -> bool:
        dialog = ConnectionDialog(self)
        for connection_config in self.connection_configs.values():
            dialog.add_connection(connection_config)
        dialog.read_settings()
        dialog.exec()
        if dialog.result() == dialog.DialogCode.Accepted:
            dialog.write_settings()
            self.table_controller.set_connection(dialog.create_connection())
        return dialog.result() == dialog.DialogCode.Accepted

    @QtCore.Slot()
    def connect_table(self) -> None:
        if self.setup_connection():
            self.connect_action.setEnabled(False)
            self.disconnect_action.setEnabled(False)
            self.table_controller.connect_table()
            self.table_controller.request_enable_joystick(self.joystick_action.isChecked())  # reset

    @QtCore.Slot()
    def disconnect_table(self) -> None:
        self.connect_action.setEnabled(False)
        self.disconnect_action.setEnabled(False)
        self.table_controller.disconnect_table()

    @QtCore.Slot()
    def abort(self) -> None:
        self.table_controller.abort()

    @QtCore.Slot(bool)
    def request_enable_joystick(self, checked: bool) -> None:
        self.table_controller.request_enable_joystick(checked)

    @QtCore.Slot()
    def enter_disconnected(self) -> None:
        self.plugin_manager.dispatch("before_enter_disconnected", (self,))
        self.connect_action.setEnabled(True)
        self.disconnect_action.setEnabled(False)
        self.stop_action.setEnabled(False)
        self.joystick_action.setEnabled(False)
        self.dashboard.enter_disconnected()
        self.progress_bar.hide()
        self.plugin_manager.dispatch("after_enter_disconnected", (self,))

    @QtCore.Slot()
    def enter_connected(self) -> None:
        self.plugin_manager.dispatch("before_enter_connected", (self,))
        self.connect_action.setEnabled(False)
        self.disconnect_action.setEnabled(True)
        self.stop_action.setEnabled(True)
        self.joystick_action.setChecked(False)  # reset
        self.joystick_action.setEnabled(True)
        self.dashboard.enter_connected()
        self.progress_bar.hide()
        self.plugin_manager.dispatch("after_enter_connected", (self,))

    @QtCore.Slot()
    def enter_moving(self) -> None:
        self.plugin_manager.dispatch("before_enter_moving", (self,))
        self.connect_action.setEnabled(False)
        self.disconnect_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.joystick_action.setEnabled(False)
        self.dashboard.enter_moving()
        self.progress_bar.show()
        self.plugin_manager.dispatch("after_enter_moving", (self,))

    @QtCore.Slot(QtGui.QCloseEvent)
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self.connect_action.isEnabled():
            result = QtWidgets.QMessageBox.question(self, "Quit?", "Close current connection?")
            if result != QtWidgets.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.disconnect_action.trigger()
        self.table_controller.shutdown()
        event.accept()
