# Load custom plugins here

from .andromeda import AndromedaPlugin
from .corvus import CorvusPlugin
from .dummy import DummyPlugin
from .hydra2x import Hydra2xPlugin
from .legacy_socket import LegacySocketPlugin
from .logger import LoggerPlugin
from .scpi_socket import SCPISocketPlugin


def register_plugins(app) -> None:
    app.register_plugin(LoggerPlugin())
    app.register_plugin(SCPISocketPlugin())
    app.register_plugin(LegacySocketPlugin())

    app.register_plugin(CorvusPlugin())
    app.register_plugin(Hydra2xPlugin())
    app.register_plugin(AndromedaPlugin())
    app.register_plugin(DummyPlugin())
