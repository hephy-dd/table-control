from table_control.core.driver import Driver, Vector, VectorMask
from table_control.core.resource import Resource

__all__ = ["AndromedaPlugin"]


class AndromedaPlugin:
    def on_install(self, window) -> None:
        window.register_connection("Andromeda", AndromedaDriver, 1)

    def on_uninstall(self, window) -> None: ...


def identity(resource: Resource) -> str:
    return " ".join(
        [
            resource.query("identify").strip(),
            resource.query("version").strip(),
            resource.query("getserialno").strip(),
        ]
    )


def test_state(state: int, value: int) -> bool:
    return (state & value) == value


class AndromedaDriver(Driver):
    def identify(self) -> list[str]:
        return [identity(res) for res in self.resources]

    def configure(self) -> None: ...

    def abort(self) -> None:
        self._write(chr(0x03))  # Ctrl+C

    def calibration_state(self) -> Vector:
        x = (int(self._query("1 nst")) >> 3) & 0x3
        y = (int(self._query("2 nst")) >> 3) & 0x3
        z = (int(self._query("3 nst")) >> 3) & 0x3
        return Vector(x, y, z)  # TODO

    def position(self) -> Vector:
        x = float(self._query("1 np"))
        y = float(self._query("2 np"))
        z = float(self._query("3 np"))
        return Vector(x, y, z)

    def is_moving(self) -> bool:
        return test_state(int(self._query("st")), 0x1)

    def move_relative(self, delta: Vector) -> None:
        x, y, z = delta
        self._write(f"{x:.6f} {y:.6f} {z:.6f} r")

    def move_absolute(self, position: Vector) -> None:
        x, y, z = position
        self._write(f"{x:.6f} {y:.6f} {z:.6f} m")

    def calibrate(self, axes: VectorMask) -> None:
        if axes.x:
            self._write("1 ncal")
        if axes.y:
            self._write("2 ncal")
        if axes.z:
            self._write("3 ncal")

    def range_measure(self, axes: VectorMask) -> None:
        if axes.x:
            self._write("1 nrm")
        if axes.y:
            self._write("2 nrm")
        if axes.z:
            self._write("3 nrm")

    def enable_joystick(self, value: bool) -> None:
        states = 0xF if value else 0x0
        self._write(f"{states:d} 1 setmanctrl")
        self._write(f"{states:d} 2 setmanctrl")
        self._write(f"{states:d} 3 setmanctrl")

    def _write(self, message: str) -> int:
        return self.resources[0].write(message)

    def _query(self, message: str) -> str:
        return self.resources[0].query(message).strip()
