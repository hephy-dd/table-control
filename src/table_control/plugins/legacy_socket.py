"""Legacy TCP socket emulating HEPHY LabView XYZ table controller.

Supported TCP commands:

PO? - Get Table Position and Status
MA=x.xxx,x.xxx,x.xxx - Move absolute [X,Y,Z]
MR=x.xxx,x - Move relative [StepWidth,Axis]
??? - This command

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
        self._tableController = window.tableController
        self.restartServer()
        logger.info("installed %r", type(self).__name__)

    def uninstall(self, window) -> None:
        if self._server:
            self._server.shutdown(timeout=60.0)
        logger.info("uninstalled %r", type(self).__name__)

    def beforePreferences(self, dialog: PreferencesDialog) -> None:
        self.preferencesTab = PreferencesWidget()
        data = self.readSettings(dialog.settings)
        self.preferencesTab.fromDict(data)
        dialog.tabWidget.addTab(self.preferencesTab, "Legacy")

    def afterPreferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.writeSettings(dialog.settings, self.preferencesTab.toDict())
            self.restartServer()
        index = dialog.tabWidget.indexOf(self.preferencesTab)
        dialog.tabWidget.removeTab(index)

    def restartServer(self) -> None:
        data = self.readSettings(QtCore.QSettings())
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

    def readSettings(self, settings: QtCore.QSettings) -> dict:
        return settings.value("plugins/legacy_socket", {})  # type: ignore

    def writeSettings(self, settings: QtCore.QSettings, data: dict) -> None:
        settings.setValue("plugins/legacy_socket", data)


class PreferencesWidget(QtWidgets.QWidget):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.enabledCheckBox = QtWidgets.QCheckBox(self)
        self.enabledCheckBox.setText("Enabled")

        self.hostnameLineEdit = QtWidgets.QLineEdit(self)

        self.portSpinBox = QtWidgets.QSpinBox(self)
        self.portSpinBox.setRange(0, 99999)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow(self.enabledCheckBox)
        layout.addRow("Hostname", self.hostnameLineEdit)
        layout.addRow("Port", self.portSpinBox)

    def hostname(self) -> str:
        return self.hostnameLineEdit.text().strip()

    def setHostname(self, hostname: str) -> None:
        self.hostnameLineEdit.setText(hostname.strip())

    def port(self) -> int:
        return self.portSpinBox.value()

    def setPort(self, port: int) -> None:
        self.portSpinBox.setValue(port)

    def isServerEnabled(self) -> bool:
        return self.enabledCheckBox.isChecked()

    def setServerEnabled(self, enabled: bool) -> None:
        self.enabledCheckBox.setChecked(enabled)

    def toDict(self) -> dict:
        return {
            "hostname": self.hostname(),
            "port": self.port(),
            "enabled": self.isServerEnabled(),
        }

    def fromDict(self, data: dict) -> None:
        self.setHostname(data.get("hostname", "localhost"))
        self.setPort(data.get("port", 4001))
        self.setServerEnabled(data.get("enabled", False))


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

        # PO?
        if command == "PO?":
            x, y, z = self.table.position()
            return f"{x:.3f},{y:.3f},{z:.3f}"  # TODO!

        # MR=DELTA,AXIS
        if command == "MR":
            try:
                _, args = message.split("=")
                delta, axis = args.split(",")
                if axis in ["1", "2", "3"]:
                    vec = [0, 0, 0]
                    vec[int(axis) - 1] = float(delta)
                    self.table.moveRelative(vec[0], vec[1], vec[2])
            except Exception:
                return None
            return None

        # MA=X,Y,Z
        if command == "MA":
            try:
                _, args = message.split("=")
                x, y, z = args.split(",")
                self.table.moveAbsolute(float(x), float(y), float(z))
            except Exception:
                return None
            return None

        # ???
        if command == "???":
            return "\n".join([
                "PO? - Get Table Position and Status",
                "MA=x.xxx,x.xxx,x.xxx - Move absolute [X,Y,Z]",
                "MR=x.xxx,x - Move relative [StepWidth,Axis]",
                "??? - This command",
            ])

        return None
