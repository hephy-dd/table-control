import time

from table_control.core.driver import Driver, Vector, VectorMask

__all__ = ["DummyPlugin"]


class DummyPlugin:

    def install(self, window) -> None:
        window.register_connection("Dummy", DummyDriver, 0)

    def uninstall(self, window) -> None:
        ...


class DummyDriver(Driver):

    def __init__(self, resources) -> None:
        super().__init__(resources)
        self._pos: list[float] = [0.0, 0.0, 0.0]
        self._vel: list[float] = [2.0, 2.0, 2.0]

        # simulation state
        self._start_pos: list[float] = self._pos.copy()
        self._target_pos: list[float] = self._pos.copy()
        self._t_start: float = 0.0
        self._moving: bool = False

    def identify(self) -> list[str]:
        return ["Dummy, v1.0"]

    def configure(self) -> None:
        ...

    def abort(self) -> None:
        self._update_motion()
        self._moving = False

    def calibration_state(self) -> Vector:
        return Vector(3, 3, 3)  # TODO

    def position(self) -> Vector:
        self._update_motion()
        x, y, z = self._pos
        return Vector(x, y, z)

    def is_moving(self) -> bool:
        self._update_motion()
        return self._moving

    def move_relative(self, delta: Vector) -> None:
        """Begin a relative move at the velocities in self._vel."""
        self._update_motion()
        # snapshot start
        self._start_pos = self._pos.copy()
        # compute target using attributes, not indexing
        self._target_pos = [
            self._start_pos[0] + delta.x,
            self._start_pos[1] + delta.y,
            self._start_pos[2] + delta.z,
        ]
        self._t_start = time.monotonic()
        self._moving  = True

    def move_absolute(self, position: Vector) -> None:
        """Begin an absolute move at the velocities in self._vel."""
        self._update_motion()
        self._start_pos = self._pos.copy()
        self._target_pos = [
            position.x,
            position.y,
            position.z,
        ]
        self._t_start = time.monotonic()
        self._moving  = True

    def calibrate(self, axes: VectorMask) -> None:
        ...

    def range_measure(self, axes: VectorMask) -> None:
        ...

    def enable_joystick(self, value: bool) -> None:
        ...

    def _clamp_step(self, start: float, target: float, vel: float, dt: float) -> float:
        """Compute new coordinate along one axis, moving from start toward target
        at speed vel (units/sec) over elapsed time dt, without overshooting.
        """
        # No motion needed or zero speed?
        if vel == 0.0 or start == target:
            return target

        # direction: +1 or -1
        direction = 1 if target > start else -1
        # candidate new position
        stepped = start + direction * vel * dt
        # clamp between start and target
        if direction > 0:
            return min(stepped, target)
        else:
            return max(stepped, target)

    def _update_motion(self) -> None:
        """Recompute pos and moving based on elapsed monotonic time."""
        if not self._moving:
            return

        now = time.monotonic()
        dt = now - self._t_start

        # Compute each axis’s new position
        new_pos: list[float] = [
            self._clamp_step(s, tgt, v, dt)
            for s, tgt, v in zip(self._start_pos, self._target_pos, self._vel)
        ]

        # If every axis has reached its target, stop; else keep moving
        if new_pos == self._target_pos:
            self._pos = new_pos
            self._moving = False
        else:
            self._pos = new_pos
