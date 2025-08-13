from table_control.core.driver import Driver, Vector

__all__ = ["Hydra2xPlugin"]


class Hydra2xPlugin:

    def install(self, window) -> None:
        window.register_appliance("Hydra 2x", {"driver": Hydra2xDriver, "resources": 2})

    def uninstall(self, window) -> None:
        ...


def identity(resource) -> str:
    return " ".join([
        resource.query("identify"),
        resource.query("version"),
        resource.query("getserialno"),
    ])


def test_state(state: int, value: int) -> bool:
    return (state & value) == value


class Hydra2xDriver(Driver):

    def identify(self) -> list[str]:
        return [identity(res) for res in self.resources]

    def configure(self) -> None:
        ...

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
        return any([
            test_state(int(self.resources[0].query(f"st")), 0x1),
            test_state(int(self.resources[1].query(f"st")), 0x1),
        ])

    def move_relative(self, delta: Vector) -> None:
        x, y, z = delta
        self.resources[0].write(f"{x} {y} r")
        self.resources[1].write(f"{z} 0 r")

    def move_absolute(self, position: Vector) -> None:
        x, y, z = position
        self.resources[0].write(f"{x} {y} m")
        self.resources[1].write(f"{z} 0 m")

    def calibrate(self, axes: Vector) -> None:
        x, y, z = axes
        if x:
            self.resources[0].write(f"1 ncal")
        if y:
            self.resources[0].write(f"2 ncal")
        if z:
            self.resources[1].write(f"1 ncal")

    def range_measure(self, axes: Vector) -> None:
        x, y, z = axes
        if x:
            self.resources[0].write(f"1 nrm")
        if y:
            self.resources[0].write(f"2 nrm")
        if z:
            self.resources[1].write(f"1 nrm")

    def enable_joystick(self, value: bool) -> None:
        states = 0xF if value else 0x0
        for resource in self.resources:
            resource.write(f"{states:d} 1 setmanctrl")
            resource.write(f"{states:d} 2 setmanctrl")
