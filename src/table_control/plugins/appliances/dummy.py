import time

from table_control.core.driver import Driver, Vector

__all__ = ["DummyPlugin"]


class DummyPlugin:

    def install(self, window) -> None:
        window.registerAppliance("Dummy", {"driver": DummyDriver})

    def uninstall(self, window) -> None:
        ...


class DummyDriver(Driver):

    def __init__(self, resources):
        super().__init__(resources)
        self._move_ts = 0

    def identify(self) -> list[str]:
        return ["Dummy, v1.0"]

    def configure(self) -> None:
        ...

    def abort(self) -> None:
        ...

    def calibration_state(self) -> Vector:
        return Vector(3, 3, 3)  # TODO

    def position(self) -> Vector:
        x, y, z = self.__dict__.get("_pos", [0., 0., 0.])
        return Vector(x, y, z)

    def is_moving(self) -> bool:
        return False

    def move_relative(self, delta: Vector) -> None:
        x, y, z = self.__dict__.get("_pos", [0., 0., 0.])
        x += delta.x
        y += delta.y
        z += delta.z
        self.__dict__.update({"_pos": [x, y, z]})

    def move_absolute(self, position: Vector) -> None:
        x, y, z = position
        self.__dict__.update({"_pos": [x, y, z]})

    def calibrate(self, axes: Vector) -> None:
        x, y, z = axes


    def range_measure(self, axes: Vector) -> None:
        x, y, z = axes
