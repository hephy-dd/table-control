import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TextIO

from PySide6 import QtCore, QtWidgets

from .utils import make_unique_name


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class TablePosition:
    name: str
    x: float
    y: float
    z: float
    comment: str


def get_position(item) -> TablePosition:
    name = item.text(0)
    x = safe_float(item.data(1, QtCore.Qt.ItemDataRole.UserRole))
    y = safe_float(item.data(2, QtCore.Qt.ItemDataRole.UserRole))
    z = safe_float(item.data(3, QtCore.Qt.ItemDataRole.UserRole))
    comment = item.text(4)
    return TablePosition(name, x, y, z, comment)


def set_position(item, position: TablePosition) -> None:
    item.setText(0, position.name)
    item.setText(1, f"{position.x:.6f}")
    item.setData(1, QtCore.Qt.ItemDataRole.UserRole, position.x)
    item.setText(2, f"{position.y:.6f}")
    item.setData(2, QtCore.Qt.ItemDataRole.UserRole, position.y)
    item.setText(3, f"{position.z:.6f}")
    item.setData(3, QtCore.Qt.ItemDataRole.UserRole, position.z)
    item.setText(4, position.comment)


def write_positions_csv(positions: Iterable[TablePosition], fp: TextIO) -> None:
    writer = csv.writer(fp)
    writer.writerow(["name", "x", "y", "z", "comment"])
    for p in positions:
        writer.writerow([p.name, p.x, p.y, p.z, p.comment])


def export_positions_csv(positions: Iterable[TablePosition], filename: str) -> None:
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        write_positions_csv(positions, fp)


class TablePositionsWidget(QtWidgets.QWidget):

    move_requested = QtCore.Signal(float, float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_position: tuple[float, float, float] = 0.0, 0.0, 0.0

        self.positions_tree = QtWidgets.QTreeWidget(self)
        self.positions_tree.setHeaderLabels(["Name", "X", "Y", "Z", "Comment"])
        self.positions_tree.setRootIsDecorated(False)
        self.positions_tree.currentItemChanged.connect(self.on_current_position_changed)
        self.positions_tree.itemDoubleClicked.connect(self.on_position_double_clicked)

        self.add_button = QtWidgets.QPushButton(self)
        self.add_button.setText("&Add...")
        self.add_button.clicked.connect(self.on_add)

        self.edit_button = QtWidgets.QPushButton(self)
        self.edit_button.setText("&Edit...")
        self.edit_button.clicked.connect(self.on_edit)

        self.up_button = QtWidgets.QPushButton(self)
        self.up_button.setText("&Up")
        self.up_button.clicked.connect(self.on_up)

        self.down_button = QtWidgets.QPushButton(self)
        self.down_button.setText("&Down")
        self.down_button.clicked.connect(self.on_down)

        self.remove_button = QtWidgets.QPushButton(self)
        self.remove_button.setText("&Remove")
        self.remove_button.clicked.connect(self.on_remove)

        self.move_button = QtWidgets.QPushButton("Move")
        self.move_button.clicked.connect(self.on_move_clicked)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(self.positions_tree, 0, 0, 8, 1)
        layout.addWidget(self.add_button, 0, 1)
        layout.addWidget(self.edit_button, 1, 1)
        layout.addWidget(self.remove_button, 2, 1)
        layout.setRowStretch(3, 1)
        layout.addWidget(self.up_button, 4, 1)
        layout.addWidget(self.down_button, 5, 1)
        layout.setRowStretch(6, 1)
        layout.addWidget(self.move_button, 7, 1)

        self.update_buttons()

    def update_buttons(self) -> None:
        current_item = self.positions_tree.currentItem()
        index = self.positions_tree.indexOfTopLevelItem(current_item)
        count = self.positions_tree.topLevelItemCount()
        self.add_button.setEnabled(True)
        self.edit_button.setEnabled(True if current_item else False)
        self.up_button.setEnabled(True if current_item and index != 0 else False)
        self.down_button.setEnabled(True if current_item and index + 1 < count else False)
        self.remove_button.setEnabled(True if current_item else False)
        self.move_button.setEnabled(True if current_item else False)

    def clear_positions(self) -> None:
        while self.positions_tree.topLevelItemCount():
            self.positions_tree.takeTopLevelItem(0)
        self.update_buttons()

    def add_position(self, position: TablePosition, set_current: bool = False) -> None:
        item = QtWidgets.QTreeWidgetItem(self.positions_tree)
        for col in (1, 2, 3):
            item.setTextAlignment(col, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        set_position(item, position)
        if set_current:
            self.positions_tree.setCurrentItem(item)
            self.positions_tree.scrollToItem(item)
        self.update_buttons()

    def positions(self) -> list[TablePosition]:
        positions = []
        for index in range(self.positions_tree.topLevelItemCount()):
            item = self.positions_tree.topLevelItem(index)
            if item:
                position = get_position(item)
                positions.append(position)
        return positions

    def enter_disconnected(self) -> None:
        self.setEnabled(False)

    def enter_connected(self) -> None:
        self.setEnabled(True)

    def enter_moving(self) -> None:
        self.setEnabled(False)

    def set_current_position(self, x: float, y: float, z: float) -> None:
        self._current_position = x, y, z

    @QtCore.Slot()
    def on_add(self) -> None:
        names = [p.name for p in self.positions()]
        name = make_unique_name("Unnamed", names)
        x, y, z = self._current_position
        position = TablePosition(name, x, y, z, "")
        dialog = TablePositionEditDialog(self)
        dialog.setWindowTitle("Add Position")
        dialog.set_position(position)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.add_position(dialog.position(), set_current=True)
        self.update_buttons()

    @QtCore.Slot()
    def on_edit(self) -> None:
        dialog = TablePositionEditDialog(self)
        current_item = self.positions_tree.currentItem()
        if current_item:
            position = get_position(current_item)
            dialog.set_position(position)
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                set_position(current_item, dialog.position())
        self.update_buttons()

    @QtCore.Slot()
    def on_up(self) -> None:
        item = self.positions_tree.currentItem()
        if item:
            index = self.positions_tree.indexOfTopLevelItem(item)
            if index > 0:
                self.positions_tree.takeTopLevelItem(index)
                self.positions_tree.insertTopLevelItem(index - 1, item)
                self.positions_tree.setCurrentItem(item)
                self.positions_tree.scrollToItem(item)

    @QtCore.Slot()
    def on_down(self) -> None:
        item = self.positions_tree.currentItem()
        if item:
            index = self.positions_tree.indexOfTopLevelItem(item)
            if index >= 0 and index < self.positions_tree.topLevelItemCount() - 1:
                self.positions_tree.takeTopLevelItem(index)
                self.positions_tree.insertTopLevelItem(index + 1, item)
                self.positions_tree.setCurrentItem(item)
                self.positions_tree.scrollToItem(item)

    @QtCore.Slot()
    def on_remove(self) -> None:
        current_item = self.positions_tree.currentItem()
        if not current_item:
            return

        name = current_item.text(0)
        reply = QtWidgets.QMessageBox.question(
            self,
            "Remove position",
            f"Remove position {name!r}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        index = self.positions_tree.indexOfTopLevelItem(current_item)
        if index >= 0:
            self.positions_tree.takeTopLevelItem(index)

        self.update_buttons()

    @QtCore.Slot()
    def on_move_clicked(self) -> None:
        item = self.positions_tree.currentItem()
        if not item:
            return

        position = get_position(item)
        self.move_requested.emit(position.x, position.y, position.z)

    def on_current_position_changed(self, current: QtWidgets.QTreeWidgetItem | None, previous: QtWidgets.QTreeWidgetItem | None) -> None:
        self.update_buttons()

    def on_position_double_clicked(self, item: QtWidgets.QTreeWidgetItem | None) -> None:
        self.on_edit()


class TablePositionEditDialog(QtWidgets.QDialog):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Edit Position")

        self.nameLineEdit = QtWidgets.QLineEdit(self)

        self.xSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.xSpinBox.setDecimals(6)
        self.xSpinBox.setRange(-9999, +9999)
        self.xSpinBox.setSuffix(" mm")

        self.ySpinBox = QtWidgets.QDoubleSpinBox(self)
        self.ySpinBox.setDecimals(6)
        self.ySpinBox.setRange(-9999, +9999)
        self.ySpinBox.setSuffix(" mm")

        self.zSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.zSpinBox.setDecimals(6)
        self.zSpinBox.setRange(-9999, +9999)
        self.zSpinBox.setSuffix(" mm")

        self.commentLineEdit = QtWidgets.QLineEdit(self)

        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.button_box.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("&Name", self.nameLineEdit)
        form_layout.addRow("X", self.xSpinBox)
        form_layout.addRow("Y", self.ySpinBox)
        form_layout.addRow("Z", self.zSpinBox)
        form_layout.addRow("&Comment", self.commentLineEdit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

    def set_position(self, position: TablePosition) -> None:
        self.nameLineEdit.setText(position.name)
        self.xSpinBox.setValue(position.x)
        self.ySpinBox.setValue(position.y)
        self.zSpinBox.setValue(position.z)
        self.commentLineEdit.setText(position.comment)

    def position(self) -> TablePosition:
        name = self.nameLineEdit.text()
        x = self.xSpinBox.value()
        y = self.ySpinBox.value()
        z = self.zSpinBox.value()
        comment = self.commentLineEdit.text()
        return TablePosition(name, x, y, z, comment)
