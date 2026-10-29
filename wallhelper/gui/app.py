"""The application object, and the entry point the CLI reaches for."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from .window import Window  # noqa: E402

# The chords every window answers: action, accelerator. GTK runs
# application accelerators in the capture phase, before a focused text
# field or the window's own key handler sees the key, so these work from
# the settings fields too. window.close is GTK's own; Ctrl+W and Ctrl+Q
# come to the same thing here, since nothing runs after the window -- the
# morning fetch is a timer.
ACCELS = (
    ("window.close", "<Control>w"),
    ("app.quit", "<Control>q"),
    ("win.shortcuts", "<Control>question"),
)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="dev.jaeho.Wallhelper")
        leave = Gio.SimpleAction(name="quit")
        leave.connect("activate", lambda *_a: self.quit())
        self.add_action(leave)
        for action, accel in ACCELS:
            self.set_accels_for_action(action, [accel])

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
