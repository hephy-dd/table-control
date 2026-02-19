import logging

logger = logging.getLogger(__name__)


class PluginManager:
    """Simple synchronous plugin dispatcher."""
    def __init__(self) -> None:
        self._plugins: list[object] = []

    def register_plugin(self, plugin: object) -> None:
        """Register a plugin instance if not already registered."""
        if any(p is plugin for p in self._plugins):
            return
        self._plugins.append(plugin)

    def notify(self, event: str, /, *args, **kwargs) -> None:
        """Invoke `on_{event}` on each registered plugin that implement it."""
        hook_name = f"on_{event}"
        for plugin in self._plugins:
            plugin_name = type(plugin).__name__
            handler = getattr(plugin, hook_name, None)
            if handler is None:
                continue
            if not callable(handler):
                logger.warning(
                    "Plugin %r has non-callable hook %s", plugin_name, hook_name
                )
                continue
            try:
                handler(*args, **kwargs)
            except Exception:
                logger.exception(
                    "Plugin %r failed in %s(*%r, **%r)",
                    plugin_name,
                    hook_name,
                    args,
                    kwargs,
                )
