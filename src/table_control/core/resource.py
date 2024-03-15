import logging
from typing import Optional

import pyvisa

__all__ = ["Resource"]


class Resource:

    def __init__(self, resource_name: str, visa_library: Optional[str] = None, **options) -> None:
        self.resource_name: str = resource_name
        self.visa_library: str = visa_library or ""
        self.options: dict = options
        self.resource: Optional = None

    def __enter__(self):
        try:
            rm = pyvisa.ResourceManager(self.visa_library)
            self.resource = rm.open_resource(self.resource_name, **self.options)
        except Exception as exc:
            raise RuntimeError(f"Failed to open resource {self.resource_name!r}") from exc
        logging.info("opened resource: %r", self.resource_name)
        return self

    def __exit__(self, *exc):
        self.resource.close()
        self.resource = None
        logging.info("closed resource: %r", self.resource_name)
        return False

    def write(self, message: str) -> int:
        logging.info("write: %r: %r", self.resource_name, message)
        try:
            return self.resource.write(message)
        except Exception as exc:
            raise RuntimeError(f"Failed to write to resource {self.resource_name!r}") from exc

    def query(self, message: str) -> str:
        logging.info("write: %r: %r", self.resource_name, message)
        try:
            result = self.resource.query(message)
        except Exception as exc:
            raise RuntimeError(f"Failed to query from resource {self.resource_name!r}") from exc
        logging.info("read: %r: %r", self.resource_name, result)
        return result
