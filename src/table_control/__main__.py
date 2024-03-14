import argparse
import logging

from . import __version__
from .gui.application import Application
from .plugins import register_plugins


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(level=logging.INFO)

    app = Application()

    register_plugins(app)

    app.bootstrap()


if __name__ == "__main__":
    main()
