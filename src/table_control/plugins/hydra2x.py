from table_control.core.driver import Driver, Vector, VectorMask
from table_control.core.resource import Resource

__all__ = ["Hydra2xPlugin"]


class Hydra2xPlugin:
    def on_install(self, window) -> None:
        window.register_connection("Hydra 2x", Hydra2xDriver, 2)

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


class Hydra2xDriver(Driver):
    def identify(self) -> list[str]:
        return [identity(res) for res in self.resources]

    def configure(self) -> None: ...

    def abort(self) -> None:
        self.resources[0].write(chr(0x03))  # Ctrl+C
        self.resources[1].write(chr(0x03))  # Ctrl+C

    def calibration_state(self) -> Vector:
        x = (int(self.resources[0].query("1 nst")) >> 3) & 0x3
        y = (int(self.resources[0].query("2 nst")) >> 3) & 0x3
        z = (int(self.resources[1].query("1 nst")) >> 3) & 0x3
        return Vector(x, y, z)  # TODO

    def position(self) -> Vector:
        x = float(self.resources[0].query("1 np"))
        y = float(self.resources[0].query("2 np"))
        z = float(self.resources[1].query("1 np"))
        return Vector(x, y, z)

    def is_moving(self) -> bool:
        return any(
            [
                test_state(int(self.resources[0].query("st")), 0x1),
                test_state(int(self.resources[1].query("st")), 0x1),
            ]
        )

    def move_relative(self, delta: Vector) -> None:
        x, y, z = delta
        self.resources[0].write(f"{x:.6f} {y:.6f} r")
        self.resources[1].write(f"{z:.6f} 0 r")

    def move_absolute(self, position: Vector) -> None:
        x, y, z = position
        self.resources[0].write(f"{x:.6f} {y:.6f} m")
        self.resources[1].write(f"{z:.6f} 0 m")

    def calibrate(self, axes: VectorMask) -> None:
        if axes.x:
            self.resources[0].write("1 ncal")
        if axes.y:
            self.resources[0].write("2 ncal")
        if axes.z:
            self.resources[1].write("1 ncal")

    def range_measure(self, axes: VectorMask) -> None:
        if axes.x:
            self.resources[0].write("1 nrm")
        if axes.y:
            self.resources[0].write("2 nrm")
        if axes.z:
            self.resources[1].write("1 nrm")

    def enable_joystick(self, value: bool) -> None:
        states = 0xF if value else 0x0
        for resource in self.resources:
            resource.write(f"{states:d} 1 setmanctrl")
            resource.write(f"{states:d} 2 setmanctrl")
