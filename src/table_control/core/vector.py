from dataclasses import dataclass
from typing import Iterator

__all__ = ["Vector", "VectorMask"]


@dataclass(frozen=False, slots=True)
class Vector:
    x: float
    y: float
    z: float

    def __iter__(self) -> Iterator[float]:
        return iter([self.x, self.y, self.z])


@dataclass(frozen=False, slots=True)
class VectorMask:
    x: bool
    y: bool
    z: bool

    def __iter__(self) -> Iterator[float]:
        return iter([self.x, self.y, self.z])
