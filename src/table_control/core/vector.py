__all__ = ["Vector"]


class Vector:

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)

    def __iter__(self):
        return iter([self.x, self.y, self.z])
