import logging
from typing import Any

import pyvisa

__all__ = ["Resource"]


class Resource:

    def __init__(self, resource_name: str, visa_library: str | None = None, **options) -> None:
        self.resource_name: str = resource_name
        self.visa_library: str = visa_library or ""
        self.options: dict = options
        self.resource: Any = None

    def __enter__(self):
        try:
            rm = pyvisa.ResourceManager(self.visa_library)
            self.resource = rm.open_resource(self.resource_name, **self.options)
        except Exception as exc:
            raise RuntimeError(f"Failed to open resource {self.resource_name!r}") from exc
        logging.debug("opened resource: %r", self.resource_name)
        return self

    def __exit__(self, *exc):
        self.resource.close()
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


def create_resource(resource: dict[str, Any]) -> Resource:
    resource_name: str = resource.get("resource_name", "")
    visa_library: str = resource.get("visa_library", "@py")
    options: dict = resource.get("options", {})
    return Resource(resource_name, visa_library, **options)
