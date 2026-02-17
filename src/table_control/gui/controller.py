import itertools
import threading
import time
import queue
import logging
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, Sequence

from PySide6 import QtCore

from ..core.driver import Driver, Vector, VectorMask
from ..core.resource import ResourceConfig, Resource

logger = logging.getLogger(__name__)


class Context: ...


class Command:
    def __call__(self, context: Context) -> None: ...


@dataclass(slots=True, order=True, frozen=True)
class CommandEnvelope:
    priority: int
    counter: int
    command: Command


class AbstractController(QtCore.QObject):

    connected = QtCore.Signal()
    disconnected = QtCore.Signal()
    failed = QtCore.Signal(object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.queue_timeout: float = 0.01
        self._q: queue.PriorityQueue[CommandEnvelope] = queue.PriorityQueue()
        self._q_counter = itertools.count()
        self._shutdown_request: threading.Event = threading.Event()
        self._lock: threading.RLock = threading.RLock()
        self._thread: threading.Thread = threading.Thread(target=self.event_loop, name=type(self).__name__)
        self._thread.start()

    @contextmanager
    def context_factory(self) -> Iterator[Context]:
        yield Context()

    def put_command(self, command: Command, priority: int = 0) -> None:
        with self._lock:
            if not isinstance(command, Command):
                raise TypeError(f"command not of type: {Command}")
            self._q.put(CommandEnvelope(priority, next(self._q_counter), command))

    def get_command(self, *, timeout=None) -> Command | None:
        try:
            task = self._q.get(timeout=timeout)
            if isinstance(task, CommandEnvelope):
                return task.command
        except queue.Empty:
            ...
        return None

    def drain_queue(self) -> None:
        with self._lock:
            while True:
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break

    def is_running(self) -> bool:
        return not self._shutdown_request.is_set()

    def shutdown(self) -> None:
        logger.info("shutting down table controller...")
        self._shutdown_request.set()
        self._thread.join()

    def event_loop(self) -> None:
        while self.is_running():
            try:
                command = self.get_command(timeout=self.queue_timeout)
                if isinstance(command, Command):
                    self.event_pump(command)
            except Exception as exc:
                logger.exception(exc)
                self.disconnected.emit()

    def event_pump(self, command: Command) -> None:
        time.sleep(0.01)


# Table controller

class DisconnectRequest(Exception): ...


class AbortRequest(Exception): ...


class CalibrationError(Exception): ...


def poll_interval(steps: Sequence[float]):
    for step in steps:
        yield step
    while True:
        yield step


@dataclass(slots=True)
class Connection:
    name: str
    driver: type[Driver]
    resources: list[ResourceConfig]


@dataclass(slots=True, frozen=True)
class ConnectCommand(Command): ...


@dataclass(slots=True, frozen=True)
class DisconnectCommand(Command): ...


@dataclass(slots=True, frozen=True)
class MoveRelativeCommand(Command):
    x: float
    y: float
    z: float

    def __call__(self, context) -> None:
        logger.info("move relative: %.3f %.3f %.3f", self.x, self.y, self.z)
        context.set_moving(True)
        try:
            context.perform_motion(lambda driver: driver.move_relative(Vector(self.x, self.y, self.z)))
        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class MoveAbsoluteCommand(Command):
    x: float
    y: float
    z: float
    z_limit: float | None

    def __call__(self, context) -> None:
        context.set_moving(True)
        try:
            context.raise_on_calibration_error()

            # No safety constraint: go straight to the target.
            if self.z_limit is None:
                logger.info("move absolute: %.3f %.3f %.3f", self.x, self.y, self.z)
                context.perform_motion(lambda driver: driver.move_absolute(Vector(self.x, self.y, self.z)))
                return

            # Current position
            pos = context.driver.position()
            current_z = pos.z

            # 1) If we start ABOVE the safe travel Z, drop vertically to z_limit first.
            if current_z > self.z_limit:
                dz = current_z - self.z_limit
                logger.info("move relative: %.3f %.3f %.3f", 0, 0, -dz)
                context.perform_motion(lambda driver: driver.move_relative(Vector(0, 0, -dz)))
                current_z = self.z_limit  # we are now exactly at the safe Z

            # 2) Move in X/Y at the current safe Z (do not change Z during XY travel).
            if pos.x != self.x or pos.y != self.y:
                logger.info("move absolute: %.3f %.3f %.3f", self.x, self.y, current_z)
                context.perform_motion(lambda driver: driver.move_absolute(Vector(self.x, self.y, current_z)))

            # 3) Finally, adjust Z to the exact target.
            if self.z != current_z:
                logger.info("move absolute: %.3f %.3f %.3f", self.x, self.y, self.z)
                context.perform_motion(lambda driver: driver.move_absolute(Vector(self.x, self.y, self.z)))

        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class CalibrateCommand(Command):
    x: bool
    y: bool
    z: bool

    def __call__(self, context) -> None:
        context.set_moving(True)
        try:
            logger.info("calibrate: x=%d y=%d z=%d", self.x, self.y, self.z)
            context.perform_motion(lambda driver: driver.calibrate(VectorMask(self.x, self.y, self.z)))
        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class RangeMeasureCommand(Command):
    x: bool
    y: bool
    z: bool

    def __call__(self, context) -> None:
        context.set_moving(True)
        try:
            logger.info("range measure: x=%d y=%d z=%d", self.x, self.y, self.z)
            context.perform_motion(lambda driver: driver.range_measure(VectorMask(self.x, self.y, self.z)))
        finally:
            context.set_moving(False)


@dataclass(slots=True, frozen=True)
class EnableJoystickCommand(Command):
    enabled: bool

    def __call__(self, context) -> None:
        logger.info("set joystick: %s", "on" if self.enabled else "off")
        context.driver.enable_joystick(self.enabled)


@dataclass(slots=True, frozen=True)
class QueryPositionCommand(Command):
    def __call__(self, context) -> None:
        x, y, z = context.driver.position()
        context.set_position(x, y, z)


@dataclass(slots=True, frozen=True)
class QueryCalibrationCommand(Command):
    def __call__(self, context) -> None:
        x, y, z = context.driver.calibration_state()
        context.set_calibration(int(x), int(y), int(z))


@dataclass(slots=True)
class TableState:
    is_moving: bool
    position: tuple[float, float, float]
    calibration: tuple[int, int, int]
    z_limit_enabled: bool
    z_limit: float


class TableContext(Context):
    def __init__(self, controller: "TableController", driver: Driver) -> None:
        self._controller = controller
        self.driver = driver

    def set_moving(self, enabled: bool) -> None:
        self._controller.set_moving(enabled)

    def set_position(self, x: float, y: float, z: float) -> None:
        self._controller.set_position(x, y, z)

    def set_calibration(self, x: int, y: int, z: int) -> None:
        self._controller.set_calibration(x, y, z)

    def raise_on_abort(self) -> None:
        timeout = 60.0
        if self._controller.is_abort_requested():
            self.driver.abort()
            t0 = time.monotonic()
            while self.driver.is_moving():
                if time.monotonic() - t0 > timeout:
                    logger.error("Abort failed to stop movement!")
                    break
                time.sleep(0.01)  # avoid spin
            raise AbortRequest()


    def raise_on_calibration_error(self) -> None:
        for index, cal in enumerate(self._controller.calibration()):
            if cal != 0x3:  # TODO
                self.driver.abort()
                axis = "XYZ"[index]
                raise CalibrationError(f"Axis not calibrated: {axis}")


    def perform_motion(self, motion: Callable[[Driver], None]) -> None:
        self.raise_on_abort()
        motion_timeout: float = self._controller.motion_timeout
        interval = poll_interval([0.010, 0.100, 0.250, 0.500, 1.0])
        motion(self.driver)  # start async motion
        t0 = time.monotonic()
        while self.driver.is_moving():
            self.raise_on_abort()
            x, y, z = self.driver.position()
            self.set_position(x, y, z)
            if time.monotonic() - t0 > motion_timeout:
                raise TimeoutError(f"Motion timed out after {motion_timeout:.1f}s")
            time.sleep(next(interval))
        self.raise_on_abort()
        x, y, z = self.driver.position()
        self.set_position(x, y, z)


class TableController(AbstractController):

    info_changed = QtCore.Signal(str)
    movement_started = QtCore.Signal()
    movement_finished = QtCore.Signal()
    position_changed = QtCore.Signal(float, float, float)
    calibration_changed = QtCore.Signal(int, int, int)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.motion_timeout: float = 60.0
        self.update_interval: float = 1.0
        self._state: TableState = TableState(
            is_moving=False,
            position=(0.0, 0.0, 0.0),
            calibration=(0, 0, 0),
            z_limit_enabled=False,
            z_limit=0.0,
        )
        self._connection: Connection | None = None
        self._t0 = time.monotonic()
        self._abort_request: threading.Event = threading.Event()

    @contextmanager
    def context_factory(self) -> Iterator[TableContext]:
        """Open all resources described by `appliance`, construct its driver,
        and yield (driver, resources). All are closed on exit.
        """
        connection = self._connection
        if connection is None:
            raise RuntimeError("No appliance set")

        with ExitStack() as es:
            self.clear_state()
            resources = [es.enter_context(Resource(res)) for res in connection.resources]
            driver = connection.driver(resources)
            yield TableContext(self, driver)
            self.clear_state()

    def connection(self) -> Connection | None:
        return self._connection

    def set_connection(self, connection: Connection) -> None:
        self._connection = connection

    # Commands

    def abort(self) -> None:
        self._abort_request.set()

    def connect_table(self) -> None:
        self.put_command(ConnectCommand(), priority=-1)

    def disconnect_table(self) -> None:
        self.put_command(DisconnectCommand(), priority=-1)

    def request_enable_joystick(self, enabled: bool) -> None:
        self.put_command(EnableJoystickCommand(enabled))

    def request_update(self) -> None:
        self.put_command(QueryPositionCommand())

    def request_calibration_state(self) -> None:
        self.put_command(QueryCalibrationCommand())

    def move_relative(self, x: float, y: float, z: float) -> None:
        self.put_command(MoveRelativeCommand(x, y, z))

    def move_absolute(self, x: float, y: float, z: float) -> None:
        z_limit = self._state.z_limit if self._state.z_limit_enabled else None
        self.put_command(MoveAbsoluteCommand(x, y, z, z_limit))

    def calibrate(self, x: bool, y: bool, z: bool) -> None:
        self.put_command(CalibrateCommand(x, y, z))

    def range_measure(self, x: bool, y: bool, z: bool) -> None:
        self.put_command(RangeMeasureCommand(x, y, z))

    def set_update_interval(self, interval: float) -> None:
        self.update_interval = float(interval)

    def set_z_limit_enabled(self, enabled: bool) -> None:
        self._state.z_limit_enabled = bool(enabled)

    def set_z_limit(self, value: float) -> None:
        self._state.z_limit = float(value)

    def is_abort_requested(self) -> bool:
        return self._abort_request.is_set()

    def clear_abort_request(self) -> None:
        self._abort_request.clear()

    def is_moving(self) -> bool:
        with self._lock:
            return self._state.is_moving

    def position(self) -> tuple[float, float, float]:
        with self._lock:
            return self._state.position

    def calibration(self) -> tuple[int, int, int]:
        with self._lock:
            return self._state.calibration

    def set_moving(self, state: bool) -> None:
        with self._lock:
            if state != self._state.is_moving:
                self._state.is_moving = state
        if state:
            self.movement_started.emit()
        else:
            self.movement_finished.emit()

    def set_position(self, x: float, y: float, z: float) -> None:
        with self._lock:
            self._state.position = (x, y, z)
        self.position_changed.emit(x, y, z)

    def set_calibration(self, x: int, y: int, z: int) -> None:
        with self._lock:
            self._state.calibration = (x, y, z)
        self.calibration_changed.emit(x, y, z)

    def clear_state(self) -> None:
        x = y = z = float("nan")
        with self._lock:
            self._state.is_moving = False
            self._state.position = (x, y, z)
            self._state.calibration = (0, 0, 0)
        self.position_changed.emit(x, y, z)

    def on_connected(self, context) -> None:
        context.driver.configure()  # TODO tricky: Corvus requires to set mode before identify
        info = context.driver.identify()
        logger.info("Connected to: %s", "; ".join([str(idn) for idn in info]))
        self.info_changed.emit(format(info))

    def on_disconnected(self, context) -> None:
        logger.info("Disconnected")

    def on_exception(self, context, exc) -> bool:
        if isinstance(exc, AbortRequest):
            logger.info("Aborted")
            self.drain_queue()
            self.clear_abort_request()
            self.movement_finished.emit()
            return True
        elif isinstance(exc, CalibrationError):
            logger.error(str(exc))
            return True
        return False

    def on_idle(self, context) -> None:
        context.raise_on_abort()
        # Auto insert update request in regular intervals
        if time.monotonic() - self._t0 >= self.update_interval:
            self._t0 = time.monotonic()
            self.request_update()
            self.request_calibration_state()

    def event_pump(self, command: Command) -> None:
        if isinstance(command, ConnectCommand):
            with self.context_factory() as context:
                self.handle_context(context)

    def handle_context(self, context: TableContext) -> None:
        try:
            self.connected.emit()
            self.on_connected(context)
            while self.is_running():
                try:
                    command = self.get_command(timeout=self.queue_timeout)
                    if isinstance(command, DisconnectCommand):
                        break
                    elif isinstance(command, Command):
                        command(context)
                    elif command is None:
                        self.on_idle(context)
                except Exception as exc:
                    if not self.on_exception(context, exc):
                        raise
        finally:
            try:
                self.on_disconnected(context)
            finally:
                self.disconnected.emit()
