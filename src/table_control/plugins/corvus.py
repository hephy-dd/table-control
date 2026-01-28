from pyvisa.errors import VisaIOError
from pyvisa.constants import StatusCode
from pyvisa.resources import MessageBasedResource

from table_control.core.driver import Driver, Vector, VectorMask
from table_control.core.resource import Resource

__all__ = ["CorvusPlugin"]


class CorvusPlugin:

    def install(self, window) -> None:
        window.register_appliance("Corvus", {"driver": CorvusDriver, "resources": 1})

    def uninstall(self, window) -> None:
        ...


def identity(resource: Resource) -> str:
    return " ".join([
        resource.query("identify").strip(),
        resource.query("version").strip(),
        resource.query("getserialno").strip(),
    ])


def test_state(state: int, value: int) -> bool:
    return (state & value) == value


class CorvusDriver(Driver):

    def identify(self) -> list[str]:
        return [identity(res) for res in self.resources]

    def configure(self) -> None:
        self._write("0 mode")  # host mode, writes control bytes to buffer
        self._query("version")  # drain control bytes from buffer

    def abort(self) -> None:
        self._write(chr(0x03))  # Ctrl+C

    def calibration_state(self) -> Vector:
        x = self._query("1 getcaldone")
        y = self._query("2 getcaldone")
        z = self._query("3 getcaldone")
        return Vector(float(x), float(y), float(z))  # TODO

    def position(self) -> Vector:
        x, y, z = self._query("pos").split()
        return Vector(float(x), float(y), float(z))

    def is_moving(self) -> bool:
        return test_state(int(self._query("status")), 0x1)

    def move_relative(self, delta: Vector) -> None:
        x, y, z = delta
        self._write(f"{x:.6f} {y:.6f} {z:.6f} rmove")

    def move_absolute(self, position: Vector) -> None:
        x, y, z = position
        self._write(f"{x:.6f} {y:.6f} {z:.6f} move")

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
        self.resources[0].write(f"{value:d} joystick")

    def _write(self, message: str) -> int:
        return self.resources[0].write(message)

    def _query(self, message: str) -> str:
        return self.resources[0].query(message).strip()
