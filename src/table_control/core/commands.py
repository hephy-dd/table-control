import logging
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .driver import Driver, Vector, VectorMask


class Context(Protocol):
    logger: logging.Logger
    driver: Driver

    def set_moving(self, enabled: bool) -> None: ...

    def set_position(self, x: float, y: float, z: float) -> None: ...

    def set_calibration(self, x: int, y: int, z: int) -> None: ...

    def raise_on_abort(self) -> None: ...

    def raise_on_calibration_error(self) -> None: ...

    def perform_motion(self, motion: Callable[[Driver], None]) -> None: ...


class Command:
    def __call__(self, context: Context) -> None: ...


@dataclass(slots=True, frozen=True)
class ConnectCommand(Command): ...


@dataclass(slots=True, frozen=True)
class DisconnectCommand(Command): ...


@dataclass(slots=True, frozen=True)
class MoveRelativeCommand(Command):
    x: float
    y: float
    z: float

    def __call__(self, context: Context) -> None:
        context.logger.info("move relative: %.3f %.3f %.3f", self.x, self.y, self.z)
        context.set_moving(True)
        try:
            context.perform_motion(
                lambda driver: driver.move_relative(Vector(self.x, self.y, self.z))
            )
        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class MoveAbsoluteCommand(Command):
    x: float
    y: float
    z: float
    z_limit: float | None

    def __call__(self, context: Context) -> None:
        context.set_moving(True)
        try:
            context.raise_on_calibration_error()

            # No safety constraint: go straight to the target.
            if self.z_limit is None:
                context.logger.info("move absolute: %.3f %.3f %.3f", self.x, self.y, self.z)
                context.perform_motion(
                    lambda driver: driver.move_absolute(Vector(self.x, self.y, self.z))
                )
                return

            # Current position
            pos = context.driver.position()
            current_z = pos.z

            # 1) If we start ABOVE the safe travel Z, drop vertically to z_limit first.
            if current_z > self.z_limit:
                dz = current_z - self.z_limit
                context.logger.info("move relative: %.3f %.3f %.3f", 0, 0, -dz)
                context.perform_motion(
                    lambda driver: driver.move_relative(Vector(0, 0, -dz))
                )
                current_z = self.z_limit  # we are now exactly at the safe Z

            # 2) Move in X/Y at the current safe Z (do not change Z during XY travel).
            if pos.x != self.x or pos.y != self.y:
                context.logger.info("move absolute: %.3f %.3f %.3f", self.x, self.y, current_z)
                context.perform_motion(
                    lambda driver: driver.move_absolute(
                        Vector(self.x, self.y, current_z)
                    )
                )

            # 3) Finally, adjust Z to the exact target.
            if self.z != current_z:
                context.logger.info("move absolute: %.3f %.3f %.3f", self.x, self.y, self.z)
                context.perform_motion(
                    lambda driver: driver.move_absolute(Vector(self.x, self.y, self.z))
                )

        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class CalibrateCommand(Command):
    x: bool
    y: bool
    z: bool

    def __call__(self, context: Context) -> None:
        context.set_moving(True)
        try:
            context.logger.info("calibrate: x=%d y=%d z=%d", self.x, self.y, self.z)

            def calibrate(driver: Driver):
                driver.calibrate(VectorMask(self.x, self.y, self.z))

                while True:
                    time.sleep(1.0)
                    try:
                        if not driver.is_moving():
                            break
                    except Exception:
                        context.logger.warning("failed to read calibration moving state")
                    context.raise_on_abort()

            context.perform_motion(calibrate)
        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class RangeMeasureCommand(Command):
    x: bool
    y: bool
    z: bool

    def __call__(self, context: Context) -> None:
        context.set_moving(True)
        try:
            context.logger.info("range measure: x=%d y=%d z=%d", self.x, self.y, self.z)

            def range_measure(driver: Driver):
                driver.range_measure(VectorMask(self.x, self.y, self.z))

                while True:
                    time.sleep(1.0)
                    try:
                        if not driver.is_moving():
                            break
                    except Exception:
                        context.logger.warning("failed to read range measure moving state")
                    context.raise_on_abort()

            context.perform_motion(range_measure)
        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class EnableJoystickCommand(Command):
    enabled: bool

    def __call__(self, context: Context) -> None:
        context.logger.info("set joystick: %s", "on" if self.enabled else "off")
        context.driver.enable_joystick(self.enabled)


@dataclass(slots=True, frozen=True)
class QueryPositionCommand(Command):
    def __call__(self, context: Context) -> None:
        x, y, z = context.driver.position()
        context.set_position(x, y, z)


@dataclass(slots=True, frozen=True)
class QueryCalibrationCommand(Command):
    def __call__(self, context: Context) -> None:
        x, y, z = context.driver.calibration_state()
        context.set_calibration(int(x), int(y), int(z))
