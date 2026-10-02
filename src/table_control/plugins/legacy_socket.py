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
from dataclasses import asdict, dataclass

from PySide6 import QtCore, QtWidgets

from table_control.gui.controller import TableController
from table_control.gui.preferences import PreferencesDialog

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Settings:
    enabled: bool = False
    hostname: str = "localhost"
    port: int = 6345


class LegacySocketPlugin:
    def on_install(self, window) -> None:
        self.settings = window.settings
        self.socket_server: SocketServer | None = None
        self.table_controller = window.table_controller

        self.worker_shutdown = threading.Event()
        self.worker_update = threading.Event()

        self.worker_thread = threading.Thread(
            target=self._worker,
            name="Legacy socket worker",
            daemon=True,
        )
        self.worker_thread.start()

    def on_uninstall(self, window) -> None:
        logger.info("Legacy socket: stopping worker...")

        self.worker_shutdown.set()
        self.worker_update.set()  # Wake worker immediately.
        self.worker_thread.join(timeout=5.0)

        if self.worker_thread.is_alive():
            logger.warning("Legacy socket: worker did not stop within timeout")

    def on_before_preferences(self, dialog: PreferencesDialog) -> None:
        self.preferences_tab = PreferencesWidget()
        settings = self.read_settings(self.settings)
        self.preferences_tab.from_settings(settings)
        dialog.add_tab(self.preferences_tab, "Legacy TCP")

    def on_after_preferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.write_settings(self.settings, self.preferences_tab.to_settings())
            self.worker_update.set()

        dialog.remove_tab(self.preferences_tab)

    def read_settings(self, settings: QtCore.QSettings) -> Settings:
        data = settings.value("plugins/legacy_socket", {})
        default_settings = Settings()
        if isinstance(data, dict):
            return Settings(
                enabled=data.get("enabled", default_settings.enabled),
                hostname=data.get("hostname", default_settings.hostname),
                port=data.get("port", default_settings.port),
            )
        return default_settings

    def write_settings(self, settings: QtCore.QSettings, data: Settings) -> None:
        settings.setValue("plugins/legacy_socket", asdict(data))

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
                    logger.info("Legacy socket: stopping server...")
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
                            "Legacy socket: failed to start on %s:%s", hostname, port
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
            logger.exception("Legacy socket: worker failed")

        finally:
            if server is not None:
                server.close()

            logger.info("Legacy socket: worker stopped")


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
            enabled=self.is_server_enabled(),
            hostname=self.hostname(),
            port=self.port(),
        )

    def from_settings(self, settings: Settings) -> None:
        self.set_server_enabled(settings.enabled)
        self.set_hostname(settings.hostname)
        self.set_port(settings.port)


class SocketServer:
    def __init__(self, handler: MessageHandler, host, port) -> None:
        self.handler = handler
        self.host: str = host
        self.port: int = port
        self.timeout: float = 1.0
        self.termination: bytes = b"\r\n"

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen()

        # Receive buffer for each persistent connection.
        self.clients: dict[socket.socket, bytearray] = {}

        logger.info("Legacy socket: listening on: %s:%s", self.host, self.port)

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
                logger.info("Legacy socket: connection from: %s", addr)
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

                logger.info("Legacy socket: received: %s", line)

                resp = self.handler.handle_message(line)
                if resp is not None:
                    conn.sendall(f"{resp}".encode() + self.termination)

            if len(buffer) > 4096:
                logger.warning("Legacy socket: exceeded maximum command length")
                self.close_client(conn)

        except Exception:
            logger.exception("Legacy socket: failed to handle client")
            self.close_client(conn)

    def close_client(self, conn: socket.socket) -> None:
        self.clients.pop(conn, None)
        conn.close()


class MessageHandler:
    def __init__(self, controller: TableController) -> None:
        self.controller = controller

    def handle_message(self, message: str) -> str | None:
        command = message.strip().split("=")[0]
        response_not_valid = "Command not valid !"
        response_error = "Error !"
        response_done = "Done ..."

        # PO?
        if command == "PO?":
            try:
                current_state = self.controller.current_state()
                x, y, z = current_state.position
                status = current_state.is_moving
                return f"{x:.6f},{y:.6f},{z:.6f},{status:d}"
            except Exception as exc:
                logger.error(exc)
                return response_error

        # MR=DELTA,AXIS
        if command == "MR":
            try:
                _, args = message.split("=")
                delta, axis = args.split(",")
                if axis not in ("1", "2", "3"):
                    raise ValueError(f"Invalid axis: {axis!r}")
                axis_index = int(axis) - 1
                delta_vector: list[float] = [0.0, 0.0, 0.0]
                delta_vector[axis_index] = float(delta)
                x, y, z = delta_vector
            except Exception as exc:
                logger.error(exc)
                return response_not_valid
            try:
                self.controller.move_relative(float(x), float(y), float(z))
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
                self.controller.move_absolute(float(x), float(y), float(z))
                return response_done
            except Exception as exc:
                logger.error(exc)
                return response_error

        # ???
        if command == "???":
            # Note: Corvus Controller v3.0.2 bug sends "\n\r"
            sep = "\n"
            return sep.join(
                [
                    "Command list:",
                    "PO? - Get Table Position and Status",
                    "MA=x.xxx,x.xxx,x.xxx - Move absolute [X,Y,Z]",
                    "MR=x.xxx,x - Move relative [StepWidth,Axis]",
                    "??? - This command",
                ]
            )

        return response_not_valid
