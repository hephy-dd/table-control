import logging

import pytest

from table_control.core.pluginmanager import PluginManager


class RecorderPlugin:
    """Records calls it receives for assertions."""

    def __init__(self, calls: list[tuple]) -> None:
        self.calls = calls

    def on_ping(self, *args, **kwargs) -> None:
        self.calls.append(("RecorderPlugin", args, kwargs))


class NoHookPlugin:
    pass


class NonCallableHookPlugin:
    # NOTE: intentionally not callable
    on_ping = 123


class ExplodingPlugin:
    def __init__(self, calls: list[tuple]) -> None:
        self.calls = calls

    def on_ping(self, *args, **kwargs) -> None:
        self.calls.append(("ExplodingPlugin_before", args, kwargs))
        raise RuntimeError("boom")


class OrderingPlugin:
    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    def on_ping(self) -> None:
        self.calls.append(self.name)


def test_register_plugin_adds_plugin() -> None:
    mgr = PluginManager()
    plugin = object()

    mgr.register_plugin(plugin)

    assert plugin in mgr._plugins  # white-box: simple module, acceptable in tests


def test_register_plugin_is_idempotent_for_same_instance() -> None:
    mgr = PluginManager()
    plugin = object()

    mgr.register_plugin(plugin)
    mgr.register_plugin(plugin)

    assert mgr._plugins.count(plugin) == 1


def test_notify_calls_matching_hook_with_args_kwargs() -> None:
    mgr = PluginManager()
    calls: list[tuple] = []
    plugin = RecorderPlugin(calls)
    mgr.register_plugin(plugin)

    mgr.notify("ping", 1, 2, a=3)

    assert calls == [("RecorderPlugin", (1, 2), {"a": 3})]


def test_notify_skips_plugins_without_hook() -> None:
    mgr = PluginManager()
    calls: list[tuple] = []
    mgr.register_plugin(NoHookPlugin())
    mgr.register_plugin(RecorderPlugin(calls))

    mgr.notify("ping", "x")

    assert calls == [("RecorderPlugin", ("x",), {})]


def test_notify_warns_and_skips_non_callable_hook(caplog: pytest.LogCaptureFixture) -> None:
    mgr = PluginManager()
    mgr.register_plugin(NonCallableHookPlugin())

    caplog.set_level(logging.WARNING)

    mgr.notify("ping")

    # Uses your exact log message format, but keep it flexible.
    assert any(
        "non-callable hook" in rec.message and "on_ping" in rec.message
        for rec in caplog.records
    )


def test_notify_logs_exception_and_continues(caplog: pytest.LogCaptureFixture) -> None:
    mgr = PluginManager()
    calls: list[tuple] = []
    mgr.register_plugin(ExplodingPlugin(calls))
    mgr.register_plugin(RecorderPlugin(calls))

    caplog.set_level(logging.ERROR)

    mgr.notify("ping", 42, k="v")
