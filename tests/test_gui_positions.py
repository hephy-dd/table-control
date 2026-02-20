import csv
import io
from pathlib import Path

from table_control.gui.positions import (
    TablePosition,
    write_positions_csv,
    export_positions_csv,
)


def parse_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def test_write_positions_csv_writes_header_only_for_empty_iterable() -> None:
    buffer = io.StringIO()

    write_positions_csv([], buffer)

    rows = parse_csv(buffer.getvalue())
    assert rows == [["name", "x", "y", "z", "comment"]]


def test_write_positions_csv_writes_rows_correctly() -> None:
    positions = [
        TablePosition("A", 1.0, 2.0, 3.0, "alpha"),
        TablePosition("B", -1.5, 0.0, 42.25, "beta"),
    ]

    buffer = io.StringIO()
    write_positions_csv(positions, buffer)

    rows = parse_csv(buffer.getvalue())

    assert rows[0] == ["name", "x", "y", "z", "comment"]
    assert rows[1] == ["A", "1.0", "2.0", "3.0", "alpha"]
    assert rows[2] == ["B", "-1.5", "0.0", "42.25", "beta"]


def test_write_positions_csv_handles_commas_and_newlines() -> None:
    positions = [
        TablePosition("P", 1.0, 2.0, 3.0, "line1\nline2,with comma"),
    ]

    buffer = io.StringIO()
    write_positions_csv(positions, buffer)

    rows = parse_csv(buffer.getvalue())

    assert rows[1][4] == "line1\nline2,with comma"


def test_write_positions_csv_accepts_any_iterable() -> None:
    def generator():
        yield TablePosition("X", 1, 2, 3, "")
        yield TablePosition("Y", 4, 5, 6, "")

    buffer = io.StringIO()
    write_positions_csv(generator(), buffer)

    rows = parse_csv(buffer.getvalue())
    assert [r[0] for r in rows[1:]] == ["X", "Y"]


def test_export_positions_csv_creates_file(tmp_path: Path) -> None:
    output = tmp_path / "positions.csv"

    positions = [TablePosition("A", 1, 2, 3, "c")]
    export_positions_csv(positions, str(output))

    assert output.exists()

    rows = list(csv.reader(output.open(encoding="utf-8")))
    assert rows[1][0] == "A"


def test_export_positions_csv_creates_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "dir" / "positions.csv"

    positions = [TablePosition("P", 1, 2, 3, "")]
    export_positions_csv(positions, str(nested))

    assert nested.exists()
    assert nested.parent.exists()


def test_export_positions_csv_overwrites_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "positions.csv"
    output.write_text("old content", encoding="utf-8")

    positions = [TablePosition("New", 9, 8, 7, "")]
    export_positions_csv(positions, str(output))

    rows = list(csv.reader(output.open(encoding="utf-8")))
    assert rows[1][0] == "New"
    assert len(rows) == 2
