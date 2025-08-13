from abc import ABC, abstractmethod
from typing import Iterable

from .resource import Resource
from .vector import Vector

__all__ = ["Driver"]


class Driver(ABC):

    def __init__(self, resources: Iterable[Resource]) -> None:
        self.resources: list[Resource] = [resource for resource in resources]

    @abstractmethod
    def identify(self) -> list[str]:
        ...

    @abstractmethod
    def configure(self) -> None:
        ...

    @abstractmethod
    def abort(self) -> None:
        ...

    @abstractmethod
    def calibration_state(self) -> Vector:
        ...

    @abstractmethod
    def position(self) -> Vector:
        ...

    @abstractmethod
    def is_moving(self) -> bool:
        ...

    @abstractmethod
    def move_relative(self, delta: Vector) -> None:
        ...

    @abstractmethod
    def move_absolute(self, position: Vector) -> None:
        ...

    @abstractmethod
    def calibrate(self, axes: Vector) -> None:
        ...

    @abstractmethod
    def range_measure(self, axes: Vector) -> None:
        ...

    @abstractmethod
    def enable_joystick(self, value: bool) -> None:
        ...
