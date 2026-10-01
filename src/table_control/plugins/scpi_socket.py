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
import re
import select
import socket
import threading
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
        self.table_controller = window.table_controller

        self.worker_shutdown = threading.Event()
        self.worker_update = threading.Event()

        self.worker_thread = threading.Thread(
            target=self._worker,
            name="SCPI socket worker",
            daemon=True,
        )
        self.worker_thread.start()

    def on_uninstall(self, window) -> None:
        logger.info("SCPI socket: stopping worker...")

        self.worker_shutdown.set()
        self.worker_update.set()  # Wake worker immediately.
        self.worker_thread.join(timeout=60.0)

        if self.worker_thread.is_alive():
            logger.warning("SCPI socket: worker did not stop within timeout")

        logger.info("uninstalled %r", type(self).__name__)

    def on_before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        data = self.read_settings(self.settings)
        self.preferences_tab.from_dict(data)
        dialog.add_tab(self.preferences_tab, "SCPI")

    def on_after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(
                self.settings,
                self.preferences_tab.to_dict(),
            )
            self.worker_update.set()

        dialog.remove_tab(self.preferences_tab)

    def _worker(self) -> None:
        server: SocketServer | None = None
        server_config: tuple[str, int] | None = None

        try:
            while not self.worker_shutdown.is_set():
                data = self.read_settings(self.settings)

                enabled = data.get("enabled", False)
                hostname = data.get("hostname", DEFAULT_HOST)
                port = data.get("port", DEFAULT_PORT)
                config = (hostname, port)

                # Stop an existing server if it was disabled or its configuration changed.
                if server is not None and (not enabled or config != server_config):
                    logger.info("SCPI socket: stopping server...")
                    server.close()
                    server = None
                    server_config = None

                # Create the server when enabled.
                if enabled and server is None:
                    try:
                        server = SocketServer(self.table_controller, hostname, port)
                    except OSError:
                        logger.exception(
                            "SCPI socket: failed to start on %s:%s", hostname, port
                        )
                        self.worker_update.wait(timeout=1.0)
                        self.worker_update.clear()
                        continue

                    server_config = config

                if server is not None:
                    server.process()
                else:
                    self.worker_update.wait(timeout=1.0)

                self.worker_update.clear()

        except Exception:
            logger.exception("SCPI socket: worker failed")

        finally:
            if server is not None:
                server.close()

            logger.info("SCPI socket: worker stopped")

    def read_settings(self, settings: QtCore.QSettings) -> dict:
        scpi_socket = settings.value("plugins/scpi_socket", {})
        if isinstance(scpi_socket, dict):
            return scpi_socket
        return {}

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
    def __init__(self, table, host: str, port: int) -> None:
        self.table = table
        self.error_stack: list = []
        self.host: str = host
        self.port: int = port
        self.timeout: float = 1.0

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen()

        # Receive buffer for each persistent connection.
        self.clients: dict[socket.socket, bytearray] = {}

        logger.info("SCPI socket: listening on: %s:%s", self.host, self.port)

    def close(self) -> None:
        for conn in self.clients:
            conn.close()
        self.clients.clear()

        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None

    def process(self) -> None:
        if self.socket is None:
            return

        ready, _, _ = select.select([self.socket, *self.clients], [], [], self.timeout)

        for sock in ready:
            if sock is self.socket:
                conn, addr = self.socket.accept()
                self.clients[conn] = bytearray()
                logger.info("SCPI socket: connection from: %s", addr)
            else:
                self.handle_client(sock)

    def handle_client(self, conn: socket.socket) -> None:
        try:
            data = conn.recv(4096)

            if not data:
                self.close_client(conn)
                return

            buffer = self.clients[conn]
            buffer.extend(data)

            while b"\n" in buffer:
                raw_line, _, remainder = buffer.partition(b"\n")
                buffer[:] = remainder

                line = raw_line.rstrip(b"\r").decode()
                if not line:
                    continue

                logger.info("SCPI socket: received: %s", line)

                resp = self.handle_message(line)
                if resp is not None:
                    conn.sendall(f"{resp}\n".encode())

            if len(buffer) > 4096:
                logger.warning("Exceeded maximum command length")
                self.close_client(conn)

        except Exception:
            logger.exception("failed to handle client")
            self.close_client(conn)

    def close_client(self, conn: socket.socket) -> None:
        self.clients.pop(conn, None)
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
