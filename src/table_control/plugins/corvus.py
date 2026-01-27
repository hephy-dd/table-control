from pyvisa.errors import VisaIOError
from pyvisa.resources import MessageBasedResource

from table_control.core.driver import Driver, Vector

__all__ = ["CorvusPlugin"]


class CorvusPlugin:

    def install(self, window) -> None:
        window.register_appliance("Corvus", {"driver": CorvusDriver, "resources": 1})

    def uninstall(self, window) -> None:
        ...


def to_vector(s: str) -> Vector:
    x, y, z = s.split()[:3]
    return Vector(float(x), float(y), float(z))


def drain(resource: MessageBasedResource, max_reads: int = 100) -> None:
    """Helper to drain junk bytes from serial buffers."""
    timeout = resource.timeout
    resource.timeout = 200
    try:
        for _ in range(max_reads):
            try:
                _ = resource.read()
            except VisaIOError:
                # timeout => nothing left
                break
    finally:
        resource.timeout = timeout


def identity(resource) -> str:
    return " ".join([
        resource.query("identify"),
        resource.query("version")
    ])


def test_state(state: int, value: int) -> bool:
    return (state & value) == value


class CorvusDriver(Driver):

    def identify(self) -> list[str]:
        return [identity(res) for res in self.resources]

    def configure(self) -> None:
        self.resources[0].write("0 mode")  # host mode
        drain(self.resources[0].resource)

    def abort(self) -> None:
        self.resources[0].write(chr(0x03))  # Ctrl+C

    def calibration_state(self) -> Vector:
        x, y, z = map(int, self.resources[0].query("-1 getcaldone").split())
        return Vector(x, y, z)  # TODO

    def position(self) -> Vector:
        return to_vector(self.resources[0].query("pos"))

    def is_moving(self) -> bool:
        return test_state(int(self.resources[0].query(f"status")), 0x1)

    def move_relative(self, delta: Vector) -> None:
        x, y, z = delta
        self.resources[0].write(f"{x:.6f} {y:.6f} {z:.6f} rmove")

    def move_absolute(self, position: Vector) -> None:
        x, y, z = position
        self.resources[0].write(f"{x:.6f} {y:.6f} {z:.6f} move")

    def calibrate(self, axes: Vector) -> None:
        x, y, z = axes
        if x:
            self.resources[0].write(f"1 ncal")
        if y:
            self.resources[0].write(f"2 ncal")
        if z:
            self.resources[0].write(f"3 ncal")

    def range_measure(self, axes: Vector) -> None:
        x, y, z = axes
        if x:
            self.resources[0].write(f"1 nrm")
        if y:
            self.resources[0].write(f"2 nrm")
        if z:
            self.resources[0].write(f"3 nrm")

    def enable_joystick(self, value: bool) -> None:
        self.resources[0].write(f"{value:d} joystick")
