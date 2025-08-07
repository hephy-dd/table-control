# Load custom plugins here

from .logger import LoggerPlugin
from .scpi_socket import SCPISocketPlugin
from .legacy_socket import LegacySocketPlugin

from .appliances.dummy import DummyPlugin
from .appliances.corvus import CorvusPlugin
from .appliances.hydra2x import Hydra2xPlugin


def register_plugins(app) -> None:
    app.register_plugin(LoggerPlugin())
    app.register_plugin(SCPISocketPlugin())
    app.register_plugin(LegacySocketPlugin())

    app.register_plugin(CorvusPlugin())
    app.register_plugin(Hydra2xPlugin())
    app.register_plugin(DummyPlugin())
