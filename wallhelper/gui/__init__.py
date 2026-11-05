"""The window, in the pieces it is made of.

    style     palette, faces, and the stylesheet built from them
    thumbs    a photograph on disk to something the strip can show
    strip     every photograph saved, in one row, and the morning's place
    plate     the caption over it
    sheets    the key list: the one overlay, with no state
    window    the caption and the strip, and the wall following them
    app       the Adw.Application, and the entry point

GTK's version has to be pinned before anything imports from gi.repository, and
importing any submodule imports this package first, so this is the one place
guaranteed to run in time.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

__all__ = ["cmd_gui"]


def __getattr__(name):
    """cmd_gui on demand, so importing a submodule for its pure parts --
    style.palette in the tests, say -- does not drag in libadwaita, a window
    class and a display connection to do it."""
    if name == "cmd_gui":
        # late import: pull libadwaita only when the GUI entry point is asked for
        from .app import cmd_gui  # noqa: PLC0415
        return cmd_gui
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
