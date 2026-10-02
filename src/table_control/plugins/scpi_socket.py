"""Generic SCPI interface for 3-axis motion control software.

Supported SCPI commands:

*IDN?                      application identity
*CLS                       clears error stack
[:]POSition?               get position
[:]CALibration[:STATe]?    get calibration
[:]MOVE[:STATe]?           is moving?
[:]MOVE:RELative <POS>     3-axis relative move
[:]MOVE:ABSolute <POS>     3-axis absolute move
[:]MOVE:ABORt              abort a movement
[:]ZLIMit[:VALue]?         get Z limit value
[:]ZLIMit:ENABle?          is Z limit enabled?
[:]SYSTem:ERRor[:NEXT]?    next error on stack
[:]SYSTem:ERRor:COUNt?     size of error stack

All SCPI commands are case insensitive (e.g. pos? is equal to POS?).

"""

import logging
import select
import socket
import threading
from dataclasses import asdict, dataclass

from PySide6 import QtCore, QtWidgets

from table_control.gui import APP_TITLE, APP_VERSION
from table_control.gui.controller import TableController
from table_control.gui.preferences import PreferencesDialog

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Settings:
    enabled: bool = False
    hostname: str = "localhost"
    port: int = 4000


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
        self.worker_thread.join(timeout=5.0)

        if self.worker_thread.is_alive():
            logger.warning("SCPI socket: worker did not stop within timeout")

    def on_before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        settings = self.read_settings(self.settings)
        self.preferences_tab.from_settings(settings)
        dialog.add_tab(self.preferences_tab, "SCPI")

    def on_after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(self.settings, self.preferences_tab.to_settings())
            self.worker_update.set()

        dialog.remove_tab(self.preferences_tab)

    def read_settings(self, settings: QtCore.QSettings) -> Settings:
        data = settings.value("plugins/scpi_socket", {})
        default_settings = Settings()
        if isinstance(data, dict):
            return Settings(
                enabled=data.get("enabled", default_settings.enabled),
                hostname=data.get("hostname", default_settings.hostname),
                port=data.get("port", default_settings.port),
            )
        return default_settings

    def write_settings(self, settings: QtCore.QSettings, data: Settings) -> None:
        settings.setValue("plugins/scpi_socket", asdict(data))

    def _worker(self) -> None:
        server: SocketServer | None = None
        server_config: tuple[str, int] | None = None

        try:
            while not self.worker_shutdown.is_set():
                settings = self.read_settings(self.settings)

                enabled = settings.enabled
                hostname = settings.hostname
                port = settings.port
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
                        server = SocketServer(
                            MessageHandler(self.table_controller), hostname, port
                        )
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
        default_settings = Settings()
        self.set_hostname(default_settings.hostname)
        self.set_port(default_settings.port)

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

    def to_settings(self) -> Settings:
        return Settings(
            hostname=self.hostname(),
            port=self.port(),
            enabled=self.is_server_enabled(),
        )

    def from_settings(self, settings: Settings) -> None:
        self.set_hostname(settings.hostname)
        self.set_port(settings.port)
        self.set_server_enabled(settings.enabled)


class SocketServer:
    def __init__(self, handler: MessageHandler, host: str, port: int) -> None:
        self.handler: MessageHandler = handler
        self.host: str = host
        self.port: int = port
        self.timeout: float = 1.0
        self.termination: bytes = b"\n"

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

            while self.termination in buffer:
                raw_line, _, remainder = buffer.partition(self.termination)
                buffer[:] = remainder

                line = raw_line.rstrip(b"\r").decode()
                if not line:
                    continue

                logger.info("SCPI socket: received: %s", line)

                resp = self.handler.handle_message(line)
                if resp is not None:
                    conn.sendall(f"{resp}".encode() + self.termination)

            if len(buffer) > 4096:
                logger.warning("Exceeded maximum command length")
                self.close_client(conn)

        except Exception:
            logger.exception("failed to handle client")
            self.close_client(conn)

    def close_client(self, conn: socket.socket) -> None:
        self.clients.pop(conn, None)
        conn.close()


class MessageHandler:
    def __init__(self, controller: TableController) -> None:
        self.controller = controller
        self.error_queue = ErrorQueue()

    def handle_message(self, message: str) -> str | None:
        message = message.strip()

        if not message:
            self.error_queue.append_error(-102, "Syntax error")
            return None

        # Separate header from parameters.
        parts = message.split(None, 1)
        header = parts[0]
        arguments = parts[1] if len(parts) == 2 else None

        query = header.endswith("?")
        if query:
            header = header[:-1]

        # IEEE 488.2 common commands
        if header.upper() == "*IDN":
            if not query:
                self.error_queue.append_error(-113, "Undefined header")
                return None

            if arguments is not None:
                self.error_queue.append_error(-108, "Parameter not allowed")
                return None

            return f"MBI,{APP_TITLE},0,{APP_VERSION}"

        if header.upper() == "*CLS":
            if query:
                self.error_queue.append_error(-113, "Undefined header")
                return None

            if arguments is not None:
                self.error_queue.append_error(-108, "Parameter not allowed")
                return None

            self.error_queue.clear()
            return None

        # :POSition[:STATe]?
        if match_header(header, "POSition") or match_header(header, "POSition:STATe"):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            x, y, z = self.controller.current_state().position
            return f"{x:.6f},{y:.6f},{z:.6f}"

        # :CALibration[:STATe]?
        if match_header(header, "CALibration") or match_header(
            header, "CALibration:STATe"
        ):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            x, y, z = self.controller.current_state().calibration
            return f"{x:d},{y:d},{z:d}"

        # :MOVE[:STATe]?
        if match_header(header, "MOVE") or match_header(header, "MOVE:STATe"):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            return "1" if self.controller.current_state().is_moving else "0"

        # :MOVE:RELative <x>,<y>,<z>
        if match_header(header, "MOVE:RELative"):
            if query:
                return self._undefined_header()

            values = self._float_parameters(arguments, 3)
            if values is None:
                return None

            self.controller.move_relative(*values)
            return None

        # :MOVE:ABSolute <x>,<y>,<z>
        if match_header(header, "MOVE:ABSolute"):
            if query:
                return self._undefined_header()

            values = self._float_parameters(arguments, 3)
            if values is None:
                return None

            self.controller.move_absolute(*values)
            return None

        # :MOVE:ABORt
        if match_header(header, "MOVE:ABORt"):
            if query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            self.controller.abort()
            return None

        # :ZLIMit:ENAbled?
        if match_header(header, "ZLIMit:ENAbled"):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            return "1" if self.controller.current_state().z_limit_enabled else "0"

        # :ZLIMit[:VALue]?
        if match_header(header, "ZLIMit") or match_header(header, "ZLIMit:VALue"):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            return f"{self.controller.current_state().z_limit:.6f}"

        # :SYSTem:ERRor:COUNt?
        if match_header(header, "SYSTem:ERRor:COUNt"):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            return str(self.error_queue.count())

        # :SYSTem:ERRor[:NEXT]?
        if match_header(header, "SYSTem:ERRor") or match_header(
            header, "SYSTem:ERRor:NEXT"
        ):
            if not query:
                return self._undefined_header()

            if arguments is not None:
                return self._parameter_not_allowed()

            if error := self.error_queue.next_error():
                return str(error)

            return str(SCPIError(0, "No error"))

        return self._undefined_header()

    def _undefined_header(self) -> None:
        self.error_queue.append_error(-113, "Undefined header")

    def _parameter_not_allowed(self) -> None:
        self.error_queue.append_error(-108, "Parameter not allowed")

    def _float_parameters(
        self,
        arguments: str | None,
        count: int,
    ) -> tuple[float, ...] | None:
        if arguments is None:
            self.error_queue.append_error(-109, "Missing parameter")
            return None

        parts = [p.strip() for p in arguments.split(",")]

        if len(parts) < count:
            self.error_queue.append_error(-109, "Missing parameter")
            return None

        if len(parts) > count:
            self.error_queue.append_error(-108, "Parameter not allowed")
            return None

        try:
            return tuple(float(p) for p in parts)
        except ValueError:
            self.error_queue.append_error(-128, "Numeric data error")
            return None


@dataclass(frozen=True, slots=True)
class SCPIError:
    code: int
    message: str

    def __str__(self) -> str:
        return f'{self.code},"{self.message}"'


class ErrorQueue:
    def __init__(self) -> None:
        self.error_queue: list[SCPIError] = []

    def append_error(self, code: int, message: str) -> None:
        self.error_queue.append(SCPIError(code, message))

    def count(self) -> int:
        return len(self.error_queue)

    def clear(self) -> None:
        self.error_queue.clear()

    def next_error(self) -> SCPIError | None:
        if self.error_queue:
            return self.error_queue.pop(0)
        return None


def match_keyword(token: str, specification: str) -> bool:
    """Match a SCPI keyword according to its short/long form."""

    token = token.upper()
    full = specification.upper()

    min_length = sum(c.isupper() for c in specification)

    return min_length <= len(token) <= len(full) and full.startswith(token)


def match_header(header: str, specification: str) -> bool:
    """Match a hierarchical SCPI header."""

    header = header.lstrip(":")
    specification = specification.lstrip(":")

    actual = header.split(":")
    expected = specification.split(":")

    if len(actual) != len(expected):
        return False

    return all(match_keyword(a, e) for a, e in zip(actual, expected))
