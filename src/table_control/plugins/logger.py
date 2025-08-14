import html
import logging
import threading
from typing import Callable, List

from PySide6 import QtCore, QtGui, QtWidgets

__all__ = ["LoggerPlugin"]


class LoggerPlugin:

    def install(self, window) -> None:
        self.logger = logging.getLogger()
        self.logging_widget = LoggingWidget()
        self.logging_widget.add_logger(self.logger)
        self.logging_widget.set_level(logging.DEBUG)

        self.logging_dock_widget = QtWidgets.QDockWidget("Logging")
        self.logging_dock_widget.setObjectName("logging_dock_widget")
        self.logging_dock_widget.setAllowedAreas(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea)
        self.logging_dock_widget.setWidget(self.logging_widget)
        self.logging_dock_widget.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.logging_dock_widget.hide()
        window.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.logging_dock_widget)

        self.logging_action = self.logging_dock_widget.toggleViewAction()
        self.logging_action.setStatusTip("Toggle logging dock window")

        window.view_menu.menuAction().setVisible(True)  # enable view menu
        window.view_menu.addAction(self.logging_action)

    def uninstall(self, window) -> None:
        window.view_menu.removeAction(self.logging_action)
        self.logging_widget.remove_logger(self.logger)
        self.logging_widget.shutdown()


class Handler(logging.Handler):

    def __init__(self, callback: Callable) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        self.callback(record)


class RecordsQueue:

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.records: List[logging.LogRecord] = []

    def append(self, record: logging.LogRecord) -> None:
        with self.lock:
            self.records.append(record)

    def fetch(self) -> List[logging.LogRecord]:
        with self.lock:
            records = self.records[:]
            self.records.clear()
            return records


class LoggingWidget(QtWidgets.QTextEdit):

    MAX_ENTRIES: int = 4096
    """Maximum number of visible log entries."""

    UPDATE_INTERVAL: int = 200
    """Update interval in milliseconds."""

    TIME_FORMAT: str = "yyyy-MM-dd hh:mm:ss"

    received = QtCore.Signal(logging.LogRecord)
    """Received is emitted when a new log record is appended by a logger."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(type(self).MAX_ENTRIES)
        self.records_queue = RecordsQueue()
        self.handler = Handler(self.received.emit)
        self.set_level(logging.INFO)
        self.received.connect(self.append_record)

        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.apply_records)
        self.update_timer.start(type(self).UPDATE_INTERVAL)

        self.record_formats: dict[int, QtGui.QTextCharFormat] = {}

        error_format = QtGui.QTextCharFormat()
        error_format.setForeground(QtGui.QColor("red"))
        self.record_formats[logging.ERROR] = error_format

        warning_format = QtGui.QTextCharFormat()
        warning_format.setForeground(QtGui.QColor("orange"))
        self.record_formats[logging.WARNING] = warning_format

        info_format = QtGui.QTextCharFormat()
        info_format.setForeground(QtGui.QColor())
        self.record_formats[logging.INFO] = info_format

        debug_format = QtGui.QTextCharFormat()
        debug_format.setForeground(QtGui.QColor("grey"))
        self.record_formats[logging.DEBUG] = debug_format

    def shutdown(self) -> None:
        self.update_timer.stop()

    def set_level(self, level: int) -> None:
        """Set log level of widget."""
        self.handler.setLevel(level)

    def add_logger(self, logger: logging.Logger) -> None:
        """Add logger to widget."""
        logger.addHandler(self.handler)

    def remove_logger(self, logger: logging.Logger) -> None:
        """Remove logger from widget."""
        logger.removeHandler(self.handler)

    def append_record(self, record: logging.LogRecord) -> None:
        """Append log record to queue."""
        self.records_queue.append(record)

    def apply_records(self) -> None:
        """Append records from queue to log widget."""
        records = self.records_queue.fetch()
        if records:
            # Get current scrollbar position
            scrollbar = self.verticalScrollBar()
            position = scrollbar.value()
            # Lock to current position or to bottom
            lock = False
            if position + 1 >= scrollbar.maximum():
                lock = True
            # Append formatted log messages
            for record in records:
                for level, record_format in self.record_formats.items():
                    if record.levelno >= level:
                        self.setCurrentCharFormat(record_format)
                        break
                self.append(self.format_record(record))
            # Scroll to bottom
            if lock:
                scrollbar.setValue(scrollbar.maximum())
            else:
                scrollbar.setValue(position)

    def ensure_recent_records_visible(self) -> None:
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @classmethod
    def format_time(cls, seconds: float) -> str:
        """Format timestamp for log record."""
        dt = QtCore.QDateTime.fromMSecsSinceEpoch(int(seconds * 1e3))
        return dt.toString(cls.TIME_FORMAT)

    @classmethod
    def format_record(cls, record: logging.LogRecord) -> str:
        """Format log record."""
        timestamp = cls.format_time(record.created)
        return "{}\t{}\t{}".format(timestamp, record.levelname, record.message)
