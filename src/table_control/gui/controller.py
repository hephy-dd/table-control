import threading
import time
import queue
import logging
import random
import contextlib
from dataclasses import dataclass
from typing import Any, Callable, Sequence, TypedDict

from PySide6 import QtCore

from ..core.driver import Driver, Vector
from ..core.resource import Resource

logger = logging.getLogger(__name__)


class AbortRequest(Exception): ...


class CalibrationError(Exception): ...


def poll_interval(steps: Sequence[float]):
    for step in steps:
        yield step
    while True:
        yield step


class ResourceConfig(TypedDict, total=False):
    resource_name: str
    visa_library: str
    options: dict[str, Any]


def create_resource(resource: ResourceConfig) -> Resource:
    resource_name: str = resource.get("resource_name", "")
    visa_library: str = resource.get("visa_library", "@py")
    options: dict = resource.get("options", {})
    return Resource(resource_name, visa_library, **options)


@dataclass(slots=True)
class Appliance:
    name: str
    driver: Driver
    resources: list[dict[str, Any]]


class Command: ...


@dataclass(slots=True, frozen=True)
class ConnectCommand(Command): ...


@dataclass(slots=True, frozen=True)
class DisconnectCommand(Command): ...


@dataclass(slots=True, frozen=True)
class MoveRelativeCommand(Command):
    x: float
    y: float
    z: float


@dataclass(slots=True, frozen=True)
class MoveAbsoluteCommand(Command):
    x: float
    y: float
    z: float
    z_limit: float | None


@dataclass(slots=True, frozen=True)
class CalibrateCommand(Command):
    x: float
    y: float
    z: float


@dataclass(slots=True, frozen=True)
class RangeMeasureCommand(Command):
    x: float
    y: float
    z: float


@dataclass(slots=True, frozen=True)
class EnableJoystickCommand(Command):
    enabled: bool


@dataclass(slots=True, frozen=True)
class QueryPositionCommand(Command): ...


@dataclass(slots=True, frozen=True)
class QueryCalibrationCommand(Command): ...


@dataclass(slots=True)
class TableState:
    is_moving: bool
    position: tuple[float, float, float]
    calibration: tuple[int, int, int]


class TableController(QtCore.QObject):

    connected = QtCore.Signal()
    disconnected = QtCore.Signal()
    info_changed = QtCore.Signal(str)
    position_changed = QtCore.Signal(float, float, float)
    movement_started = QtCore.Signal()
    movement_finished = QtCore.Signal()
    calibration_changed = QtCore.Signal(int, int, int)
    failed = QtCore.Signal(object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.motion_timeout: float = 60.0
        self.update_interval: float = 1.0
        self.z_limit_enabled: bool = False
        self.z_limit: float = 0.0
        self.queue_timeout: float = 0.250
        self._state: TableState = TableState(
            is_moving=False,
            position=(0, 0, 0),
            calibration=(0, 0, 0),
        )
        self._command_queue: queue.Queue[Command] = queue.Queue()
        self._command_handler: CommandHandler = CommandHandler(self)
        self._appliance: Appliance | None = None
        self._abort: threading.Event = threading.Event()
        self._stop_request: threading.Event = threading.Event()
        self._lock: threading.RLock = threading.RLock()
        self._thread: threading.Thread = threading.Thread(target=self.event_loop, name="TableController")
        self._thread.start()

    def send_command(self, command: Command) -> None:
        self._command_queue.put_nowait(command)

    def next_command(self, timeout: float | None = 0.25) -> Command | None:
        try:
            return self._command_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def appliance(self) -> Appliance | None:
        return self._appliance

    def set_appliance(self, appliance: Appliance) -> None:
        self._appliance = appliance

    def is_running(self) -> bool:
        return not self._abort.is_set()

    def shutdown(self) -> None:
        logger.info("shutting down table controller...")
        self._abort.set()
        self._thread.join()

    # Commands

    def connect_table(self) -> None:
        self.send_command(ConnectCommand())

    def disconnect_table(self) -> None:
        self.send_command(DisconnectCommand())

    def request_stop(self) -> None:
        self._stop_request.set()

    def request_enable_joystick(self, enabled: bool) -> None:
        self.send_command(EnableJoystickCommand(enabled))

    def request_update(self) -> None:
        self.send_command(QueryPositionCommand())

    def request_calibration_state(self) -> None:
        self.send_command(QueryCalibrationCommand())

    def move_relative(self, x, y, z):
        self.send_command(MoveRelativeCommand(x, y, z))

    def move_absolute(self, x, y, z):
        z_limit = self.z_limit if self.z_limit_enabled else None
        self.send_command(MoveAbsoluteCommand(x, y, z, z_limit))

    def calibrate(self, x, y, z):
        self.send_command(CalibrateCommand(x, y, z))

    def range_measure(self, x, y, z):
        self.send_command(RangeMeasureCommand(x, y, z))

    def set_update_interval(self, interval: float) -> None:
        self.update_interval = float(interval)

    def set_z_limit_enabled(self, enabled: bool) -> None:
        self.z_limit_enabled = bool(enabled)

    def set_z_limit(self, value: float) -> None:
        self.z_limit = float(value)

    def is_stop_requested(self) -> bool:
        return self._stop_request.is_set()

    def clear_stop_request(self) -> None:
        self._stop_request.clear()

    def is_moving(self) -> bool:
        with self._lock:
            return self._state.is_moving

    def position(self) -> tuple[float, float, float]:
        with self._lock:
            return self._state.position

    def calibration(self) -> tuple[int, int, int]:
        with self._lock:
            return self._state.calibration

    def update_moving(self, state: bool) -> None:
        with self._lock:
            is_moving = self._state.is_moving
            self._state.is_moving = state
        if is_moving != state:
            if state:
                self.movement_started.emit()
            else:
                self.movement_finished.emit()

    def update_position(self, position: Vector) -> None:
        x, y, z = position
        with self._lock:
            self._state.position = (x, y, z)
        self.position_changed.emit(x, y, z)

    def update_calibration(self, calibration: Vector) -> None:
        x, y, z = calibration
        with self._lock:
            self._state.calibration = (int(x), int(y), int(z))
        self.calibration_changed.emit(int(x), int(y), int(z))

    def clear(self) -> None:
        with self._lock:
            self._state.is_moving = False
            self._state.position = (float('nan'), float('nan'), float('nan'))
            self._state.calibration = (0, 0, 0)
        self.position_changed.emit(float('nan'), float('nan'), float('nan'))

    # Event loop

    def event_loop(self) -> None:
        while self.is_running():
            try:
                self._command_handler.handle_commands()
            except Exception as exc:
                logger.exception(exc)
            time.sleep(0.25)  # throttle


class CommandHandler:

    def __init__(self, controller) -> None:
        self.controller = controller

    def handle_commands(self) -> None:
        msg = self.controller.next_command(timeout=self.controller.queue_timeout)
        if isinstance(msg, ConnectCommand):
            self.handle_connection()

    def handle_connection(self) -> None:
        try:
            self.controller.clear()
            appliance = self.controller.appliance()
            if appliance is None:
                raise RuntimeError("No appliance set")
            with contextlib.ExitStack() as es:
                resources = [es.enter_context(create_resource(res)) for res in appliance.resources]
                driver = appliance.driver(resources)
                self.controller.connected.emit()
                driver.configure()
                info = driver.identify()
                self.controller.info_changed.emit(format(info))
                t0 = time.monotonic()
                while self.controller.is_running():
                    try:
                        self.handle_stop(driver)
                        cmd = self.controller.next_command(timeout=self.controller.queue_timeout)
                        match cmd:
                            case DisconnectCommand():
                                break
                            case MoveRelativeCommand(x=x, y=y, z=z):
                                self.move_relative(driver, x, y, z)
                            case MoveAbsoluteCommand(x=x, y=y, z=z, z_limit=z_limit):
                                self.move_absolute(driver, x, y, z, z_limit)
                            case CalibrateCommand(x=x, y=y, z=z):
                                self.calibrate(driver, x, y, z)
                            case RangeMeasureCommand(x=x, y=y, z=z):
                                self.range_measure(driver, x, y, z)
                            case EnableJoystickCommand(enabled=enabled):
                                self.enable_joystick(driver, enabled)
                            case QueryPositionCommand():
                                self.update_position(driver)
                            case QueryCalibrationCommand():
                                self.update_calibration(driver)
                            case _:
                                # Auto insert update request in regular intervals
                                if time.monotonic() - t0 >= self.controller.update_interval:
                                    t0 = time.monotonic()
                                    self.controller.request_update()
                                    self.controller.request_calibration_state()
                    except AbortRequest:
                        logger.info("Aborted!")
                        # Clear the queue
                        while True:
                            try:
                                self.controller._command_queue.get_nowait()
                            except queue.Empty:
                                break
                        self.controller.clear_stop_request()
                    except CalibrationError as exc:
                        logger.info(str(exc))
        except Exception as exc:
            logger.exception(exc)
            self.controller.failed.emit(exc)
        finally:
            self.controller.clear()
            self.controller.disconnected.emit()

    def update_position(self, driver: Driver) -> None:
        pos = driver.position()
        self.controller.update_position(pos)

    def update_calibration(self, driver: Driver) -> None:
        cal = driver.calibration_state()
        self.controller.update_calibration(cal)

    def move_relative(self, driver: Driver, x, y, z) -> None:
        self.controller.update_moving(True)
        try:
            self.handle_calibration_error(driver)
            self.perform_motion(driver, lambda: driver.move_relative(Vector(x, y, z)))
        finally:
            self.controller.update_moving(False)

    def move_absolute(self, driver: Driver, x, y, z, z_limit) -> None:
        self.controller.update_moving(True)
        try:
            self.handle_calibration_error(driver)
            if z_limit is not None:
                pos = driver.position()
                if pos.z > z_limit:
                    z_diff = abs(pos.z - z_limit)
                    self.perform_motion(driver, lambda: driver.move_relative(Vector(0, 0, -z_diff)))
                pos = driver.position()
                self.perform_motion(driver, lambda: driver.move_absolute(Vector(x, y, pos.z)))
                self.perform_motion(driver, lambda: driver.move_absolute(Vector(x, y, z)))
            else:
                self.perform_motion(driver, lambda: driver.move_absolute(Vector(x, y, z)))
        finally:
            self.controller.update_moving(False)

    def calibrate(self, driver: Driver, x, y, z) -> None:
        self.controller.update_moving(True)
        try:
            self.perform_motion(driver, lambda: driver.calibrate(Vector(x, y, z)))
        finally:
            self.controller.update_moving(False)

    def range_measure(self, driver: Driver, x, y, z) -> None:
        self.controller.update_moving(True)
        try:
            self.perform_motion(driver, lambda: driver.range_measure(Vector(x, y, z)))
        finally:
            self.controller.update_moving(False)

    def perform_motion(self, driver: Driver, motion: Callable[[], None]) -> None:
        self.handle_stop(driver)
        motion_timeout: float = self.controller.motion_timeout
        interval = poll_interval([0.100, 0.250, 0.500, 1.0])
        motion()
        t0 = time.monotonic()
        while driver.is_moving():
            self.handle_stop(driver)
            pos = driver.position()
            self.controller.update_position(pos)
            if time.monotonic() - t0 > motion_timeout:
                raise TimeoutError(f"Motion timed out after {motion_timeout:.1f}s")
            time.sleep(next(interval))
        self.handle_stop(driver)
        pos = driver.position()
        self.controller.update_position(pos)

    def enable_joystick(self, driver: Driver, enable) -> None:
        driver.enable_joystick(enable)

    def handle_stop(self, driver: Driver) -> None:
        if self.controller.is_stop_requested():
            driver.abort()
            raise AbortRequest()

    def handle_calibration_error(self, driver: Driver) -> None:
        for index, cal in enumerate(self.controller.calibration()):
            if cal != 0x3:  # TODO
                driver.abort()
                axis = "XYZ"[index]
                raise CalibrationError(f"Axis not calibrated: {axis}")
