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
        rm = pyvisa.ResourceManager(self.visa_library)
        self.resource = rm.open_resource(self.resource_name, **self.options)
        logging.info("opened resource: %r", self.resource_name)
        return self

    def __exit__(self, *exc):
        self.resource.close()
        self.resource = None
        logging.info("closed resource: %r", self.resource_name)
        return False

    def write(self, message: str) -> int:
        logging.info("write: %r: %r", self.resource_name, message)
        return self.resource.write(message)

    def query(self, message: str) -> str:
        logging.info("write: %r: %r", self.resource_name, message)
        result = self.resource.query(message)
        logging.info("read: %r: %r", self.resource_name, result)
        return result
