"""Generic SCPI interface for 3-axis table control software.

Supported SCPI commands:

*IDN?                      application identity
*CLS                       clears error stack
[:]POSition?               get position
[:]CALibration[:STATe]?    get calibration
[:]MOVE[:STATe]?           is moving?
[:]MOVE:RELative <POS>     3-axis relative move
[:]MOVE:ABSolute <POS>     3-axis absolute move
[:]MOVE:ABORT              abort a movement
[:]SYStem:ERRor[:NEXT]?    next error on stack
[:]SYStem:ERRor:COUNt?     size of error stack

All SCPI commands are case insensitive (e.g. pos? is equal to POS?).

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


class SCPISocketPlugin:

    def install(self, window) -> None:
        self._server: SocketServer | None = None
        self._tableController = window.table_controller
        self.restart_server()

    def uninstall(self, window) -> None:
        if self._server:
            self._server.shutdown(timeout=60.0)

    def before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        data = self.read_settings(dialog.settings)
        self.preferences_tab.from_dict(data)
        dialog.tab_widget.addTab(self.preferences_tab, "SCPI")

    def after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(dialog.settings, self.preferences_tab.to_dict())
            self.restart_server()
        index = dialog.tab_widget.indexOf(self.preferences_tab)
        dialog.tab_widget.removeTab(index)

    def restart_server(self) -> None:
        data = self.read_settings(QtCore.QSettings())
        if self._server:
            logger.info("SCPI socket: shutdown server...")
            self._server.shutdown(timeout=60.0)
            self._server = None
        if data.get("enabled", False):
            hostname = data.get("hostname", "localhost")
            port = data.get("port", 4000)
            logger.info("SCPI socket: starting server on port %s...", port)
            self._server = SocketServer(self._tableController, hostname, port)
            thread = threading.Thread(target=self._server)
            thread.start()

    def read_settings(self, settings: QtCore.QSettings) -> dict:
        return settings.value("plugins/scpi_socket", {})  # type: ignore

    def write_settings(self, settings: QtCore.QSettings, data: dict) -> None:
        settings.setValue("plugins/scpi_socket", data)


class PreferencesWidget(QtWidgets.QWidget):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.enabled_check_box = QtWidgets.QCheckBox(self)
        self.enabled_check_box.setText("Enabled")

        self.hostname_line_edit = QtWidgets.QLineEdit(self)

        self.port_spin_box = QtWidgets.QSpinBox(self)
        self.port_spin_box.setRange(0, 65535)

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
        self.set_port(data.get("port", 4000))
        self.set_server_enabled(data.get("enabled", False))


class SocketServer:

    def __init__(self, table, host, port) -> None:
        self.shutdown_requested = threading.Event()
        self.shutdown_finished = threading.Event()
        self.table = table
        self.error_stack: list = []
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
                    logger.info("SCPI socket: listening on: %s:%s", self.host, self.port)

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
        logger.info("SCPI socket: connection from: %s", addr)
        try:
            with conn.makefile("r") as f:
                for raw_line in f:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    logger.info("SCPI socket: received: %s", line)
                    resp = self.handle_message(line)
                    if resp is not None:
                        conn.sendall(f"{resp}\n".encode())
        except Exception as exc:
            logger.exception(exc)
        finally:
            conn.close()

    def handle_message(self, message: str) -> str | None:
        command = message.split()[0].lower()

        # *IDN?
        if re.match(r"^\*idn\?$", command):
            return f"{APP_TITLE} v{APP_VERSION}"

        # *CLS
        if re.match(r"^\*cls$", command):
            self.error_stack.clear()
            return None

        # [:]POSition[:STATe]?
        if re.match(r"^\:?pos(ition)?(\:stat(e)?)?\?$", command):
            x, y, z = self.table.position()
            return f"{x:.3f} {y:.3f} {z:.3f}"

        # [:]CALibration[:STATe]?
        if re.match(r"^\:?cal(ibration)?(\:stat(e)?)?\?$", command):
            x, y, z = self.table.calibration()
            return f"{x:d} {y:d} {z:d}"

        # [:]MOVE[:STATe]?
        if re.match(r"^\:?move(\:stat(e)?)?\?$", command):
            moving = self.table.is_moving()
            return "1" if moving else "0"

        # [:]MOVE:RELative X Y Z
        if re.match(r"^\:?move\:rel(ative)?$", command):
            try:
                _, dx, dy, dz = message.split()
                self.table.move_relative(float(dx), float(dy), float(dz))
            except Exception:
                self.error_stack.append((101, "invalid attributes"))
                return None
            return None

        # [:]MOVE:ABSolute X Y Z
        if re.match(r"^\:?move\:abs(olute)?$", command):
            try:
                _, x, y, z = message.split()
                self.table.move_absolute(float(x), float(y), float(z))
            except Exception:
                self.error_stack.append((101, "invalid attributes"))
                return None
            return None

        # [:]MOVE:ABORT
        if re.match(r"^\:?move\:abort$", command):
            self.table.request_stop()
            return None

        # [:]SYStem:ERRor:COUNt?
        if re.match(r"^\:?sys(t(em)?)?\:err(or)?\:coun(t)?\?$", command):
            return format(len(self.error_stack))

        # [:]SYStem:ERRor[:NEXT]?
        if re.match(r"^\:?sys(t(em)?)?\:err(or)?(\:next)?\?$", command):
            if self.error_stack:
                code, msg = self.error_stack.pop(0)
                return f"{code},\"{msg}\""
            return "0,\"no error\""

        self.error_stack.append((100, "invalid command"))

        return None
