import logging
from typing import Iterable

logger = logging.getLogger(__name__)


class PluginManager:

    def __init__(self) -> None:
        self.plugins: list[object] = []

    def register_plugin(self, plugin: object) -> None:
        if plugin not in self.plugins:
            self.plugins.append(plugin)

    def dispatch(self, event: str, args: Iterable | None = None) -> None:
        for plugin in self.plugins:
            handler = getattr(plugin, event, None)
            if callable(handler):
                try:
                    handler(*args)
                except Exception as exc:
                    logger.exception(exc)
