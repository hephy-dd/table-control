import threading
import time
import queue
import logging
import random
import contextlib
from typing import Any

from PySide6 import QtCore

from ..core.driver import Vector
from ..core.resource import Resource

TIMEOUT: float = 60.0


def poll_interval(steps, default_step=1.0):
    for step in steps:
        yield step
    while True:
        yield default_step


def create_resource(resource: dict) -> Resource:
    resource_name: str = resource.get("resource_name", "")
    visa_library: str = resource.get("visa_library", "@py")
    options: dict = resource.get("options", {})
    return Resource(resource_name, visa_library, **options)


class Appliance:

    def __init__(self, name: str, driver, resources):
        self.name: str = name
        self.driver = driver
        self.resources = resources


class Message:

    def __init__(self, name, *args) -> None:
        self.name = name
        self.args = args


class MessageQueue:

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()

    def put(self, name, *args) -> None:
        self._q.put_nowait(Message(name, *args))

    def pop(self) -> Message | None:
        try:
            return self._q.get(timeout=0.25)
        except queue.Empty:
            ...
        return None


class TableController(QtCore.QObject):

    connected = QtCore.Signal()
    disconnected = QtCore.Signal()
    info_changed = QtCore.Signal(str)
    position_changed = QtCore.Signal(float, float, float)
    movement_started = QtCore.Signal()
    movement_finished = QtCore.Signal()
    calibration_changed = QtCore.Signal(int, int, int)
    failed = QtCore.Signal(Exception)

    def __init__(self) -> None:
        super().__init__()
        self.update_interval: float = 1.0
        self.messages = MessageQueue()
        self.handler = MessageHandler(self)
        self.state: dict[str, Any] = {}
        self._appliance: Appliance | None = None
        self._abort = threading.Event()
        self._thread = threading.Thread(target=self.event_loop)
        self._thread.start()

    def appliance(self) -> Appliance | None:
        return self._appliance

    def set_appliance(self, appliance: Appliance) -> None:
        self._appliance = appliance

    def is_running(self) -> bool:
        return not self._abort.is_set()

    def shutdown(self) -> None:
        logging.info("shutting down table controller...")
        self._abort.set()
        self._thread.join()

    # Commands

    def connect_table(self) -> None:
        self.messages.put("connect")

    def disconnect_table(self) -> None:
        self.messages.put("disconnect")

    def request_stop(self) -> None:
        self.state.update({"stop_request": True})

    def request_update(self) -> None:
        self.messages.put("update")

    def move_relative(self, x, y, z):
        self.messages.put("move_relative", x, y, z)

    def move_absolute(self, x, y, z):
        self.messages.put("move_absolute", x, y, z)

    def calibrate(self, x, y, z):
        self.messages.put("calibrate", x, y, z)

    def range_measure(self, x, y, z):
        self.messages.put("range_measure", x, y, z)

    def set_update_interval(self, interval: float) -> None:
        self.update_interval = float(interval)

    def is_stop_requested(self) -> bool:
        return "stop_request" in self.state

    def is_moving(self) -> bool:
        return self.state.get("is_moving", False)

    def position(self) -> tuple[float, float, float]:
        return self.state.get("position", (0., 0., 0.))

    def calibration(self) -> tuple[int, int ,int]:
        return self.state.get("calibration", (0, 0, 0))

    def update_moving(self, state: bool) -> None:
        is_moving = self.state.get("is_moving")
        self.state.update({"is_moving": bool(state)})
        if is_moving != state:
            if state:
                self.movement_started.emit()
            else:
                self.movement_finished.emit()

    def update_position(self, position: Vector) -> None:
        x, y, z = position
        self.state.update({"position": (x, y, z)})
        self.position_changed.emit(x, y, z)

    def update_calibration(self, calibration: Vector) -> None:
        x, y, z = calibration
        self.state.update({"calibration": (int(x), int(y), int(z))})
        self.calibration_changed.emit(int(x), int(y), int(z))

    def clear(self) -> None:
        self.state.clear()
        self.position_changed.emit(float('nan'), float('nan'), float('nan'))

    # Event loop

    def event_loop(self) -> None:
        while self.is_running():
            try:
                self.handler.handle_messages()
            except Exception as exc:
                logging.exception(exc)
            time.sleep(1)  # throttle


class MessageHandler:

    def __init__(self, controller) -> None:
        self.controller = controller

    def handle_messages(self) -> None:
        msg = self.controller.messages.pop()
        if msg and msg.name == "connect":
            self.handle_connection()

    def handle_connection(self) -> None:
        try:
            self.controller.clear()
            appliance = self.controller.appliance()
            with contextlib.ExitStack() as es:
                resources = [es.enter_context(create_resource(res)) for res in appliance.resources]
                driver = appliance.driver(resources)
                self.controller.connected.emit()
                driver.configure()
                info = driver.identify()
                self.controller.info_changed.emit(format(info))
                t0 = time.monotonic()
                while self.controller.is_running():
                    self.handle_stop(driver)
                    msg = self.controller.messages.pop()
                    if msg:
                        if msg.name == "disconnect":
                            break
                        if msg.name == "move_relative":
                            x, y, z = msg.args
                            self.move_relative(driver, x, y, z)
                        elif msg.name == "move_absolute":
                            x, y, z = msg.args
                            self.move_absolute(driver, x, y, z)
                        elif msg.name == "calibrate":
                            x, y, z = msg.args
                            self.calibrate(driver, x, y, z)
                        elif msg.name == "range_measure":
                            x, y, z = msg.args
                            self.range_measure(driver, x, y, z)
                        elif msg.name == "update":
                            self.update_position(driver)
                            self.update_calibration(driver)
                    # Auto insert update request in regular intervals
                    elif time.monotonic() - t0 >= self.controller.update_interval:
                        t0 = time.monotonic()
                        self.controller.request_update()
                    else:
                        time.sleep(0.250)  # throttle
        except Exception as exc:
            logging.exception(exc)
            self.controller.failed.emit(exc)
        finally:
            self.controller.clear()
            self.controller.disconnected.emit()

    def update_position(self, driver) -> None:
        pos = driver.position()
        self.controller.update_position(pos)

    def update_calibration(self, driver) -> None:
        cal = driver.calibration_state()
        self.controller.update_calibration(cal)

    def move_relative(self, driver, x, y, z) -> None:
        self.controller.update_moving(True)
        driver.move_relative(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handle_stop(driver)
            pos = driver.position()
            self.controller.update_position(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        pos = driver.position()
        self.controller.update_position(pos)
        self.controller.update_moving(False)

    def move_absolute(self, driver, x, y, z) -> None:
        self.controller.update_moving(True)
        driver.move_absolute(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handle_stop(driver)
            pos = driver.position()
            self.controller.update_position(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        pos = driver.position()
        self.controller.update_position(pos)
        self.controller.update_moving(False)

    def calibrate(self, driver, x, y, z) -> None:
        self.controller.update_moving(True)
        driver.calibrate(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handle_stop(driver)
            pos = driver.position()
            self.controller.update_position(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        pos = driver.position()
        self.controller.update_position(pos)
        self.controller.update_moving(False)

    def range_measure(self, driver, x, y, z) -> None:
        self.controller.update_moving(True)
        driver.range_measure(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handle_stop(driver)
            pos = driver.position()
            self.controller.update_position(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        self.controller.update_moving(False)
        pos = driver.position()
        self.controller.update_position(pos)
        self.controller.update_moving(False)

    def handle_stop(self, driver) -> None:
        stopRequest = self.controller.state.pop("stop_request", None)
        if stopRequest:
            driver.abort()
