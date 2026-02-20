"""
The plugin system dispatches application events to registered objects.

Plugins are ordinary Python objects. To participate, register an instance with
`PluginManager.register_plugin(plugin)`. Once registered, the plugin may receive
events dispatched via `PluginManager.notify(event, *args, **kwargs)`.

A plugin handles an event by defining a method named `on_<event>`. When
`notify()` is called, each registered plugin is checked for a matching
`on_<event>` method. If present, it is invoked with the provided arguments.

Example:

    manager = PluginManager()
    manager.register_plugin(MyPlugin())

    manager.notify("install", window)

    class MyPlugin:
        def on_install(self, window) -> None:
            ...

Hook conventions:

- Methods must be named `on_<event>`.
- Hooks receive the same `*args` and `**kwargs` passed to `notify`.
- Hooks are optional; only those defined are invoked.
- Hooks should not raise exceptions. Errors are logged and dispatch
  continues.

Hooks execute synchronously and in registration order. Handlers should remain
lightweight and avoid long-running or blocking work (else will block a GUI).

No base class is required. Any object that follows the `on_<event>` naming
convention can act as a plugin.
"""

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
