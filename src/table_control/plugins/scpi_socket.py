"""Generic SCPI interface for 3-axis motion control software.

Supported SCPI commands:

*IDN?                      application identity
*CLS                       clears error stack
[:]POSition?               get position
[:]CALibration[:STATe]?    get calibration
[:]MOVE[:STATe]?           is moving?
[:]MOVE:RELative <POS>     3-axis relative move
[:]MOVE:ABSolute <POS>     3-axis absolute move
[:]MOVE:ABORT              abort a movement
[:]ZLIMit[:VALue]?         get Z limit value
[:]ZLIMit:ENABle?          is Z limit enabled?
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
from typing import Final

from PySide6 import QtCore, QtWidgets

from table_control.gui import APP_TITLE, APP_VERSION
from table_control.gui.preferences import PreferencesDialog

logger = logging.getLogger(__name__)

DEFAULT_HOST: Final[str] = "localhost"
DEFAULT_PORT: Final[int] = 4000


class SCPISocketPlugin:
    def on_install(self, window) -> None:
        self.settings = window.settings
        self.socket_server: SocketServer | None = None
        self.table_controller = window.table_controller
        self.restart_server()

    def on_uninstall(self, window) -> None:
        if self.socket_server:
            self.socket_server.shutdown(timeout=60.0)
        logger.info("uninstalled %r", type(self).__name__)

    def on_before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        data = self.read_settings(self.settings)
        self.preferences_tab.from_dict(data)
        dialog.add_tab(self.preferences_tab, "SCPI")

    def on_after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(self.settings, self.preferences_tab.to_dict())
            self.restart_server()
        dialog.remove_tab(self.preferences_tab)

    def restart_server(self) -> None:
        data = self.read_settings(QtCore.QSettings())
        if self.socket_server:
            logger.info("SCPI socket: shutdown server...")
            self.socket_server.shutdown(timeout=60.0)
            self.socket_server = None
        if data.get("enabled", False):
            hostname = data.get("hostname", DEFAULT_HOST)
            port = data.get("port", DEFAULT_PORT)
            logger.info("SCPI socket: starting server on port %s...", port)
            self.socket_server = SocketServer(self.table_controller, hostname, port)
            thread = threading.Thread(target=self.socket_server)
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
                    logger.info(
                        "SCPI socket: listening on: %s:%s", self.host, self.port
                    )

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
            return f"{x:.6f},{y:.6f},{z:.6f}"

        # [:]CALibration[:STATe]?
        if re.match(r"^\:?cal(ibration)?(\:stat(e)?)?\?$", command):
            x, y, z = self.table.calibration()
            return f"{x:d},{y:d},{z:d}"

        # [:]MOVE[:STATe]?
        if re.match(r"^\:?move(\:stat(e)?)?\?$", command):
            moving = self.table.is_moving()
            return "1" if moving else "0"

        # [:]MOVE:RELative X Y Z
        if re.match(r"^\:?move\:rel(ative)?$", command):
            try:
                _, args = message.split(maxsplit=1)
                dx, dy, dz = args.split(",")
                self.table.move_relative(float(dx), float(dy), float(dz))
            except Exception:
                self.error_stack.append((101, "invalid attributes"))
                return None
            return None

        # [:]MOVE:ABSolute X Y Z
        if re.match(r"^\:?move\:abs(olute)?$", command):
            try:
                _, args = message.split(maxsplit=1)
                x, y, z = args.split(",")
                self.table.move_absolute(float(x), float(y), float(z))
            except Exception:
                self.error_stack.append((101, "invalid attributes"))
                return None
            return None

        # [:]ZLIMit:ENAbled?
        if re.match(r"^\:?zlim(it)?\:enab(le)?\?$", command):
            enabled = self.table.z_limit_enabled
            return "1" if enabled else "0"

        # [:]ZLIMit[:VALue]?
        if re.match(r"^\:?zlim(it)?(\:val(ue)?)?\?$", command):
            value = self.table.z_limit
            return f"{value:.6f}"

        # [:]MOVE:ABORT
        if re.match(r"^\:?move\:abort$", command):
            self.table.abort()
            return None

        # [:]SYStem:ERRor:COUNt?
        if re.match(r"^\:?sys(t(em)?)?\:err(or)?\:coun(t)?\?$", command):
            return format(len(self.error_stack))

        # [:]SYStem:ERRor[:NEXT]?
        if re.match(r"^\:?sys(t(em)?)?\:err(or)?(\:next)?\?$", command):
            if self.error_stack:
                code, msg = self.error_stack.pop(0)
                return f'{code},"{msg}"'
            return '0,"no error"'

        self.error_stack.append((100, "invalid command"))

        return None
