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
        dialog.tabWidget.addTab(self.preferencesTab, "SCPI")

    def afterPreferences(self, dialog: PreferencesDialog) -> None:
        if dialog.result() == dialog.DialogCode.Accepted:
            self.writeSettings(dialog.settings, self.preferencesTab.toDict())
            self.restartServer()
        index = dialog.tabWidget.indexOf(self.preferencesTab)
        dialog.tabWidget.removeTab(index)

    def restartServer(self) -> None:
        data = self.readSettings(QtCore.QSettings())
        if self._server:
            logging.info("shutdown SCPI server...")
            self._server.shutdown(timeout=60.0)
            self._server = None
        if data.get("enabled", False):
            hostname = data.get("hostname", "localhost")
            port = data.get("port", 4000)
            logging.info("starting SCPI server on port %s...", port)
            self._server = SocketServer(self._tableController, hostname, port)
            thread = threading.Thread(target=self._server)
            thread.start()

    def readSettings(self, settings: QtCore.QSettings) -> dict:
        return settings.value("plugins/scpi_socket", {})  # type: ignore

    def writeSettings(self, settings: QtCore.QSettings, data: dict) -> None:
        settings.setValue("plugins/scpi_socket", data)


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
        self.setPort(data.get("port", 4000))
        self.setServerEnabled(data.get("enabled", False))


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
                    logger.info(f"{type(self).__name__!r} listening on {self.host}:{self.port}")

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
        logging.info(f"Connection from {addr}")
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break  # Connection closed by the client

                message = data.decode().strip()
                response = None

                logging.info(message)
                response = self.handle_message(message)

                if response is not None:
                    conn.sendall(f"{response}\n".encode())

        except Exception as exc:
            logging.exception(exc)
        finally:
            conn.close()

    def handle_message(self, message: str) -> str | None:
        command = message.split()[0].lower()
        logger.info(["command", command])

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
            moving = self.table.isMoving()
            return "1" if moving else "0"

        # [:]MOVE:RELative X Y Z
        if re.match(r"^\:?move\:rel(ative)?$", command):
            try:
                _, dx, dy, dz = message.split()
                self.table.moveRelative(float(dx), float(dy), float(dz))
            except Exception:
                self.error_stack.append((101, "invalid attributes"))
                return None
            return None

        # [:]MOVE:ABSolute X Y Z
        if re.match(r"^\:?move\:abs(olute)?$", command):
            try:
                _, x, y, z = message.split()
                self.table.moveAbsolute(float(x), float(y), float(z))
            except Exception:
                self.error_stack.append((101, "invalid attributes"))
                return None
            return None

        # [:]MOVE:ABORT
        if re.match(r"^\:?move\:abort$", command):
            self.table.requestStop()
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
