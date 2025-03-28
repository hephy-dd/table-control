import logging
from typing import Iterable

logger = logging.getLogger(__name__)


class PluginManager:

    def __init__(self) -> None:
        self.plugins: list = []

    def register_plugin(self, plugin) -> None:
        if plugin not in self.plugins:
            self.plugins.append(plugin)

    def dispatch(self, name, args: Iterable | None = None) -> None:
        for plugin in self.plugins:
            if hasattr(plugin, name):
                try:
                    getattr(plugin, name)(*(args or ()))
                except Exception as exc:
                    logger.exception(exc)
