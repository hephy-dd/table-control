import logging
from dataclasses import dataclass
from typing import Any

import pyvisa

__all__ = ["ResourceConfig", "Resource"]


@dataclass
class ResourceConfig:
    visa_library: str | None
    resource_name: str
    baud_rate: int | None
    termination: str
    timeout: float


class Resource:

    def __init__(self, config: ResourceConfig) -> None:
        self.visa_library = config.visa_library
        self.resource_name = config.resource_name
        self.baud_rate = config.baud_rate
        self.termination = config.termination
        self.timeout = config.timeout
        self.resource: Any = None

    def __enter__(self):
        try:
            if self.visa_library is not None:
                rm = pyvisa.ResourceManager(self.visa_library)
            else:
                rm = pyvisa.ResourceManager()
            resource = rm.open_resource(self.resource_name)

            if self.baud_rate is not None:
                if hasattr(resource, "baud_rate"):
                    resource.baud_rate = int(self.baud_rate)
            resource.read_termination = self.termination
            resource.write_termination = self.termination
            resource.timeout = int(max(0, self.timeout) * 1000)  # milleseconds
            self.resource = resource
        except Exception as exc:
            raise RuntimeError(f"Failed to open resource {self.resource_name!r}") from exc
        else:
            logging.debug("opened resource: %r", self.resource_name)
        return self

    def __exit__(self, *exc):
        try:
            self.resource.close()
        finally:
            self.resource = None
            logging.debug("closed resource: %r", self.resource_name)
        return False

    def write(self, message: str) -> int:
        logging.debug("write: %r: %r", self.resource_name, message)
        try:
            return self.resource.write(message)
        except Exception as exc:
            raise RuntimeError(f"Failed to write to resource {self.resource_name!r}") from exc

    def query(self, message: str) -> str:
        logging.debug("write: %r: %r", self.resource_name, message)
        try:
            result = self.resource.query(message)
        except Exception as exc:
            raise RuntimeError(f"Failed to query from resource {self.resource_name!r}") from exc
        logging.debug("read: %r: %r", self.resource_name, result)
        return result
