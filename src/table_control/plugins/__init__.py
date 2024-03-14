# Load custom plugins here

from .logger import LoggerPlugin

from .appliances.dummy import DummyPlugin
from .appliances.corvus import CorvusPlugin
from .appliances.hydra2x import Hydra2xPlugin


def register_plugins(app) -> None:
    app.registerPlugin(LoggerPlugin())

    app.registerPlugin(CorvusPlugin())
    app.registerPlugin(Hydra2xPlugin())
    app.registerPlugin(DummyPlugin())
