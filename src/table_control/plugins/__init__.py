# Load custom plugins here

from .logger import LoggerPlugin
from .scpi_socket import SCPISocketPlugin

from .appliances.dummy import DummyPlugin
from .appliances.corvus import CorvusPlugin
from .appliances.hydra2x import Hydra2xPlugin


def register_plugins(app) -> None:
    app.registerPlugin(LoggerPlugin())
    app.registerPlugin(SCPISocketPlugin())

    app.registerPlugin(CorvusPlugin())
    app.registerPlugin(Hydra2xPlugin())
    app.registerPlugin(DummyPlugin())
