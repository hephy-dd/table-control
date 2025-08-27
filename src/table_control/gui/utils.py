import importlib.resources

from PySide6 import QtCore, QtGui, QtWidgets


def load_icon(filename: str) -> QtGui.QIcon:
    with importlib.resources.path("table_control.assets.icons", filename) as path:
        return QtGui.QIcon(str(path))


def load_text(filename: str) -> str:
    with importlib.resources.path("table_control.assets", filename) as path:
        with open(path, "r") as fp:
            return fp.read()


class FlashLabel(QtWidgets.QLabel):
    def __init__(self, flash_duration_ms: int = 250,
                 circle_color: QtGui.QColor | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.flash_duration_ms = int(flash_duration_ms)
        self.circle_color = circle_color or QtGui.QColor(0, 255, 0)
        self._flashing = False

        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._stop_flash)

    def flash(self) -> None:
        self._flashing = True
        self.update()
        self._timer.start(self.flash_duration_ms)

    def _stop_flash(self) -> None:
        self._flashing = False
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        # Draw the normal label (text etc.)
        super().paintEvent(event)

        # Draw a circle whose diameter equals the label's current HEIGHT,
        # centered in the label. If the width is smaller, it will be clipped.
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        if self._flashing:
            painter.setBrush(QtGui.QBrush(self.circle_color))
        else:
            painter.setBrush(QtGui.QBrush(QtGui.QColor("grey")))

        diameter = min(self.height(), self.width()) - 4

        x = 0
        y = (self.height() - diameter) / 2
        painter.drawEllipse(QtCore.QRectF(x, y, diameter, diameter))
