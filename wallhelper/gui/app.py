"""The application object, and the entry point the CLI reaches for."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw  # noqa: E402

from .window import Window  # noqa: E402


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="dev.jaeho.Wallhelper")

    def do_activate(self):
        (self.props.active_window or Window(self)).present()


def cmd_gui(_args) -> int:
    """Importing this package pulls in GTK, libadwaita and a display
    connection, which is why the CLI imports it inside the gui subcommand and
    nowhere else: fetch and set run from a timer and a keybind.

    The window calls the commands directly rather than shelling out to itself,
    so there is one implementation of every behaviour and the CLI and the
    window cannot drift apart.
    """
    return App().run(None)
