"""Legacy TCP socket emulating MBI LabView XYZ table controller.

Supported TCP commands:

PO? - Get Table Position and Status
MA=x.xxx,x.xxx,x.xxx - Move absolute [X,Y,Z]
MR=x.xxx,x - Move relative [StepWidth,Axis]
??? - command help

"""

import logging
import select
import socket
import threading
import time
import re
from typing import Final

from PySide6 import QtCore, QtWidgets

from table_control.gui import APP_TITLE, APP_VERSION
from table_control.gui.preferences import PreferencesDialog

logger = logging.getLogger(__name__)

DEFAULT_HOST: Final[str] = "localhost"
DEFAULT_PORT: Final[int] = 6345


class LegacySocketPlugin:

    def install(self, window) -> None:
        self.settings = window.settings
        self.socket_server: SocketServer | None = None
        self.table_controller = window.table_controller
        self.restartServer()

    def uninstall(self, window) -> None:
        if self.socket_server:
            self.socket_server.shutdown(timeout=60.0)
        logger.info("uninstalled %r", type(self).__name__)

    def before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        data = self.read_settings(self.settings)
        self.preferences_tab.from_dict(data)
        dialog.tab_widget.addTab(self.preferences_tab, "Legacy TCP")

    def after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(self.settings, self.preferences_tab.to_dict())
            self.restartServer()
        index = dialog.tab_widget.indexOf(self.preferences_tab)
        dialog.tab_widget.removeTab(index)

    def restartServer(self) -> None:
        data = self.read_settings(QtCore.QSettings())
        if self.socket_server:
            logger.info("legacy socket: shutdown server...")
            self.socket_server.shutdown(timeout=60.0)
            self.socket_server = None
        if data.get("enabled", False):
            hostname = data.get("hostname", DEFAULT_HOST)
            port = data.get("port", DEFAULT_PORT)
            logger.info("legacy socket: starting server on port %s...", port)
            self.socket_server = SocketServer(self.table_controller, hostname, port)
            thread = threading.Thread(target=self.socket_server)
            thread.start()

    def read_settings(self, settings: QtCore.QSettings) -> dict:
        return settings.value("plugins/legacy_socket", {})  # type: ignore

    def write_settings(self, settings: QtCore.QSettings, data: dict) -> None:
        settings.setValue("plugins/legacy_socket", data)


class PreferencesWidget(QtWidgets.QWidget):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.enabled_check_box = QtWidgets.QCheckBox(self)
        self.enabled_check_box.setText("Enabled")

        self.hostname_line_edit = QtWidgets.QLineEdit(self)

        self.port_spin_box = QtWidgets.QSpinBox(self)
        self.port_spin_box.setRange(0, 65535)

        self.reset_defaults_button = QtWidgets.QPushButton(self)
        self.reset_defaults_button.setText("Reset to Defaults")
        self.reset_defaults_button.setToolTip("Restore inputs to their default values")
        self.reset_defaults_button.clicked.connect(self.reset_defaults)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow(self.enabled_check_box)
        layout.addRow("Hostname", self.hostname_line_edit)
        layout.addRow("Port", self.port_spin_box)
        layout.addWidget(self.reset_defaults_button)

    def reset_defaults(self) -> None:
        self.set_hostname(DEFAULT_HOST)
        self.set_port(DEFAULT_PORT)

    def hostname(self) -> str:
        return self.hostname_line_edit.text().strip()

    def set_hostname(self, hostname: str) -> None:
        self.hostname_line_edit.setText(hostname.strip())

    def port(self) -> int:
        return self.port_spin_box.value()

    def set_port(self, port: int) -> None:
        self.port_spin_box.setValue(port)

    def is_server_enabled(self) -> bool:
        return self.enabled_check_box.isChecked()

    def set_server_enabled(self, enabled: bool) -> None:
        self.enabled_check_box.setChecked(enabled)

    def to_dict(self) -> dict:
        return {
            "hostname": self.hostname(),
            "port": self.port(),
            "enabled": self.is_server_enabled(),
        }

    def from_dict(self, data: dict) -> None:
        self.set_hostname(data.get("hostname", DEFAULT_HOST))
        self.set_port(data.get("port", DEFAULT_PORT))
        self.set_server_enabled(data.get("enabled", False))


class SocketServer:

    def __init__(self, table, host, port) -> None:
        self.shutdown_requested = threading.Event()
        self.shutdown_finished = threading.Event()
        self.table = table
        self.host: str = host
        self.port: int = port
        self.timeout: float = 1.0
        self.termination: str = "\r\n"

    def shutdown(self, timeout: float | None = None) -> None:
        self.shutdown_requested.set()
        if timeout is not None:
            self.shutdown_finished.wait(timeout=timeout)

    def __call__(self) -> None:
        while not self.shutdown_requested.is_set():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((self.host, self.port))
                    s.listen()
                    logger.info("legacy socket: listening on: %s:%s", self.host, self.port)

                    while True:
                        ready, _, _ = select.select([s], [], [], self.timeout)
                        if s in ready:
                            conn, addr = s.accept()
                            self.handle_client(conn, addr)
                        if self.shutdown_requested.is_set():
                            break

            except Exception as exc:
                logger.exception(exc)
                time.sleep(1.0)
        self.shutdown_finished.set()

    def handle_client(self, conn, addr):
        logger.info("legacy socket: connection from: %s", addr)
        try:
            with conn.makefile("r") as f:
                for raw_line in f:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    logger.info("legacy socket: received: %s", line)
                    resp = self.handle_message(line)
                    if resp is not None:
                        conn.sendall(f"{resp}{self.termination}".encode())
        except Exception as exc:
            logger.exception(exc)
        finally:
            conn.close()

    def handle_message(self, message: str) -> str | None:
        command = message.strip().split("=")[0]
        response_not_valid = "Command not valid !"
        response_error = "Error !"
        response_done = "Done ..."

        # PO?
        if command == "PO?":
            try:
                x, y, z = self.table.position()
                status = self.table.is_moving()
                return f"{x:.6f},{y:.6f},{z:.6f},{status:d}"
            except Exception as exc:
                logger.error(exc)
                return response_error

        # MR=DELTA,AXIS
        if command == "MR":
            try:
                _, args = message.split("=")
                delta, axis = args.split(",")
                axis_index = int(axis) - 1
                delta_vector: list[float] = [0.0, 0.0, 0.0]
                delta_vector[axis_index] = float(delta)
                x, y, z = delta_vector
            except Exception as exc:
                logger.error(exc)
                return response_not_valid
            try:
                self.table.move_relative(float(x), float(y), float(z))
                return response_done
            except Exception as exc:
                logger.error(exc)
                return response_error

        # MA=X,Y,Z
        if command == "MA":
            try:
                _, args = message.split("=")
                x, y, z = args.split(",")
            except Exception as exc:
                logger.error(exc)
                return response_not_valid
            try:
                self.table.move_absolute(float(x), float(y), float(z))
                return response_done
            except Exception as exc:
                logger.error(exc)
                return response_error

        # ???
        if command == "???":
            # Note: Corvus Controller v3.0.2 bug sends "\n\r"
            return "\n".join([
                "Command list:",
                "PO? - Get Table Position and Status",
                "MA=x.xxx,x.xxx,x.xxx - Move absolute [X,Y,Z]",
                "MR=x.xxx,x - Move relative [StepWidth,Axis]",
                "??? - This command",
            ])

        return response_not_valid
