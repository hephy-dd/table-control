import threading
import time
import queue
import logging
import random
import contextlib
from typing import Optional

from PyQt5 import QtCore

from ..core.driver import Vector
from ..core.resource import Resource

TIMEOUT: float = 60.0


def poll_interval(steps, default_step=1.0):
    for step in steps:
        yield step
    while True:
        yield default_step


def create_resource(resource: dict) -> Resource:
    resource_name = resource.get("resource_name")
    visa_library = resource.get("visa_library", "@py")
    options = resource.get("options", {})
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
        self._q = queue.Queue()

    def put(self, name, *args) -> None:
        self._q.put_nowait(Message(name, *args))

    def pop(self) -> Optional[Message]:
        try:
            return self._q.get(timeout=0.25)
        except queue.Empty:
            ...
        return None


class TableController(QtCore.QObject):

    connected = QtCore.pyqtSignal()
    disconnected = QtCore.pyqtSignal()
    infoChanged = QtCore.pyqtSignal(str)
    positionChanged = QtCore.pyqtSignal(float, float, float)
    movementStarted = QtCore.pyqtSignal()
    movementFinished = QtCore.pyqtSignal()
    calibrationChanged = QtCore.pyqtSignal(int, int, int)
    failed = QtCore.pyqtSignal(Exception)

    def __init__(self) -> None:
        super().__init__()
        self.update_interval: float = 1.0
        self.messages = MessageQueue()
        self.handler = MessageHandler(self)
        self.state = {}
        self._appliance: Optional[Appliance] = None
        self._abort = threading.Event()
        self._thread = threading.Thread(target=self.eventLoop)
        self._thread.start()

    def appliance(self) -> Optional[Appliance]:
        return self._appliance

    def setAppliance(self, appliance: Appliance) -> None:
        self._appliance = appliance

    def isRunning(self) -> bool:
        return not self._abort.is_set()

    def shutdown(self) -> None:
        logging.info("shutting down table controller...")
        self._abort.set()
        self._thread.join()

    # Commands

    def connect(self) -> None:
        self.messages.put("connect")

    def disconnect(self) -> None:
        self.messages.put("disconnect")

    def requestStop(self) -> None:
        self.state.update({"stop_request": True})

    def requestUpdate(self) -> None:
        self.messages.put("update")

    def moveRelative(self, x, y, z):
        self.messages.put("move_relative", x, y, z)

    def moveAbsolute(self, x, y, z):
        self.messages.put("move_absolute", x, y, z)

    def calibrate(self, x, y, z):
        self.messages.put("calibrate", x, y, z)

    def rangeMeasure(self, x, y, z):
        self.messages.put("range_measure", x, y, z)

    def setUpdateInterval(self, interval: float) -> None:
        self.update_interval = float(interval)

    def isStopRequested(self) -> None:
        return "stop_request" in self.state

    def isMoving(self) -> bool:
        return self.state.get("is_moving", False)

    def position(self) -> tuple[float, float, float]:
        return self.state.get("position", (0., 0., 0.))

    def calibration(self) -> tuple[int, int ,int]:
        return self.state.get("calibration", (0, 0, 0))

    def updateMoving(self, state: bool) -> None:
        is_moving = self.state.get("is_moving")
        self.state.update({"is_moving": bool(state)})
        if is_moving != state:
            if state:
                self.movementStarted.emit()
            else:
                self.movementFinished.emit()

    def updatePosition(self, position: Vector) -> None:
        x, y, z = position
        self.state.update({"position": (x, y, z)})
        self.positionChanged.emit(x, y, z)

    def updateCalibration(self, calibration: Vector) -> None:
        x, y, z = calibration
        self.state.update({"calibration": (int(x), int(y), int(z))})
        self.calibrationChanged.emit(int(x), int(y), int(z))

    def clear(self) -> None:
        self.state.clear()
        self.positionChanged.emit(float('nan'), float('nan'), float('nan'))

    # Event loop

    def eventLoop(self) -> None:
        while self.isRunning():
            try:
                self.handler.handleMessages()
            except Exception as exc:
                logging.exception(exc)
            time.sleep(1)  # throttle


class MessageHandler:

    def __init__(self, controller) -> None:
        self.controller = controller

    def handleMessages(self) -> None:
        msg = self.controller.messages.pop()
        if msg and msg.name == "connect":
            self.handleConnection()

    def handleConnection(self):
        try:
            self.controller.clear()
            appliance = self.controller.appliance()
            with contextlib.ExitStack() as es:
                resources = [es.enter_context(create_resource(res)) for res in appliance.resources]
                driver = appliance.driver(resources)
                self.controller.connected.emit()
                driver.configure()
                info = driver.identify()
                self.controller.infoChanged.emit(format(info))
                t0 = time.monotonic()
                while self.controller.isRunning():
                    self.handleStop(driver)
                    msg = self.controller.messages.pop()
                    if msg:
                        if msg.name == "disconnect":
                            break
                        if msg.name == "move_relative":
                            x, y, z = msg.args
                            self.moveRelative(driver, x, y, z)
                        elif msg.name == "move_absolute":
                            x, y, z = msg.args
                            self.moveAbsolute(driver, x, y, z)
                        elif msg.name == "calibrate":
                            x, y, z = msg.args
                            self.calibrate(driver, x, y, z)
                        elif msg.name == "range_measure":
                            x, y, z = msg.args
                            self.rangeMeasure(driver, x, y, z)
                        elif msg.name == "update":
                            self.updatePosition(driver)
                            self.updateCalibration(driver)
                    # Auto insert update request in regular intervals
                    elif time.monotonic() - t0 >= self.controller.update_interval:
                        t0 = time.monotonic()
                        self.controller.requestUpdate()
                    else:
                        time.sleep(0.250)  # throttle
        except Exception as exc:
            logging.exception(exc)
            self.controller.failed.emit(exc)
        finally:
            self.controller.clear()
            self.controller.disconnected.emit()

    def updatePosition(self, driver):
        pos = driver.position()
        self.controller.updatePosition(pos)

    def updateCalibration(self, driver):
        cal = driver.calibration_state()
        self.controller.updateCalibration(cal)

    def moveRelative(self, driver, x, y, z):
        self.controller.updateMoving(True)
        driver.move_relative(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handleStop(driver)
            pos = driver.position()
            self.controller.updatePosition(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        pos = driver.position()
        self.controller.updatePosition(pos)
        self.controller.updateMoving(False)

    def moveAbsolute(self, driver, x, y, z):
        self.controller.updateMoving(True)
        driver.move_absolute(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handleStop(driver)
            pos = driver.position()
            self.controller.updatePosition(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        pos = driver.position()
        self.controller.updatePosition(pos)
        self.controller.updateMoving(False)

    def calibrate(self, driver, x, y, z):
        self.controller.updateMoving(True)
        driver.calibrate(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handleStop(driver)
            pos = driver.position()
            self.controller.updatePosition(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        pos = driver.position()
        self.controller.updatePosition(pos)
        self.controller.updateMoving(False)

    def rangeMeasure(self, driver, x, y, z):
        self.controller.updateMoving(True)
        driver.range_measure(Vector(x, y, z))
        interval = poll_interval([0.010, 0.100, 0.500], 1.0)
        t0 = time.monotonic()
        while driver.is_moving():
            self.handleStop(driver)
            pos = driver.position()
            self.controller.updatePosition(pos)
            if time.monotonic() - t0 > TIMEOUT:
                raise TimeoutError()
            time.sleep(next(interval))
        self.controller.updateMoving(False)
        pos = driver.position()
        self.controller.updatePosition(pos)
        self.controller.updateMoving(False)

    def handleStop(self, driver):
        stopRequest = self.controller.state.pop("stop_request", None)
        if stopRequest:
            driver.abort()
