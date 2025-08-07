"""Legacy TCP socket emulating HEPHY LabView XYZ table controller.

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

from PySide6 import QtCore, QtWidgets

from table_control.gui import APP_TITLE, APP_VERSION
from table_control.gui.preferences import PreferencesDialog

logger = logging.getLogger(__name__)



class LegacySocketPlugin:

    def install(self, window) -> None:
        self._server: SocketServer | None = None
        self._tableController = window.table_controller
        self.restartServer()
        logger.info("installed %r", type(self).__name__)

    def uninstall(self, window) -> None:
        if self._server:
            self._server.shutdown(timeout=60.0)
        logger.info("uninstalled %r", type(self).__name__)

    def before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        data = self.read_settings(dialog.settings)
        self.preferences_tab.from_dict(data)
        dialog.tab_widget.addTab(self.preferences_tab, "Legacy")

    def after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(dialog.settings, self.preferences_tab.to_dict())
            self.restartServer()
        index = dialog.tab_widget.indexOf(self.preferences_tab)
        dialog.tab_widget.removeTab(index)

    def restartServer(self) -> None:
        data = self.read_settings(QtCore.QSettings())
        if self._server:
            logger.info("legacy socket: shutdown server...")
            self._server.shutdown(timeout=60.0)
            self._server = None
        if data.get("enabled", False):
            hostname = data.get("hostname", "localhost")
            port = data.get("port", 4001)
            logger.info("legacy socket: starting server on port %s...", port)
            self._server = SocketServer(self._tableController, hostname, port)
            thread = threading.Thread(target=self._server)
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
        self.port_spin_box.setRange(0, 99999)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow(self.enabled_check_box)
        layout.addRow("Hostname", self.hostname_line_edit)
        layout.addRow("Port", self.port_spin_box)

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
        self.set_hostname(data.get("hostname", "localhost"))
        self.set_port(data.get("port", 4001))
        self.set_server_enabled(data.get("enabled", False))


class SocketServer:

    def __init__(self, table, host, port) -> None:
        self.shutdown_requested = threading.Event()
        self.shutdown_finished = threading.Event()
        self.table = table
        self.host: str = host
        self.port: int = port
        self.timeout: float = 1.0

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
                    logger.info("Legacy socket: listening on: %s:%s", self.host, self.port)

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
            while True:
                data = conn.recv(1024)
                if not data:
                    break  # Connection closed by the client

                message = data.decode().strip()
                response = None

                logger.info("legacy socket: received: %s", message)
                response = self.handle_message(message)

                if response is not None:
                    conn.sendall(f"{response}\n".encode())

        except Exception as exc:
            logger.exception(exc)
        finally:
            conn.close()

    def handle_message(self, message: str) -> str | None:
        command = message.split("=")[0]
        error_response = "Command not valid !"

        # PO?
        if command == "PO?":
            x, y, z = self.table.position()
            status = 0  # TODO!
            return f"{x:.6f},{y:.6f},{z:.6f},{status:d}"

        # MR=DELTA,AXIS
        if command == "MR":
            try:
                _, args = message.split("=")
                delta, axis = args.split(",")
                axis_index = int(axis) - 1
                delta_vector: list[float] = [0.0, 0.0, 0.0]
                delta_vector[axis_index] = float(delta)
                x, y, z = delta_vector
                self.table.move_relative(float(x), float(y), float(z))
            except Exception:
                return error_response
            return None

        # MA=X,Y,Z
        if command == "MA":
            try:
                _, args = message.split("=")
                x, y, z = args.split(",")
                self.table.move_absolute(float(x), float(y), float(z))
            except Exception:
                return error_response
            return None

        # ???
        if command == "???":
            return "\n".join([
                "Command list:",
                "PO? - Get Table Position and Status",
                "MA=x.xxx,x.xxx,x.xxx - Move absolute [X,Y,Z]",
                "MR=x.xxx,x - Move relative [StepWidth,Axis]",
                "??? - This command",
            ])

        return error_response
