"""The key list: the one overlay left, for a key forgotten weeks later.

Nothing on screen points at it; ? and Ctrl+? open it (app-contract), and
any key or a click puts it away. A band across the strip rather than a
card: the window is a strip, and a column of nine rows would not fit.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

SHORTCUTS = (
    ("\u2190 \u2192", "h l", "Move along"),
    ("D", "Backspace", "Delete"),
    ("U", "Ctrl+Z", "Undo the delete"),
    ("O", "", "Open the source page"),
    ("Esc", "Enter", "Done"),
    ("?", "Ctrl+?", "These keys"),
    ("Ctrl+W", "Ctrl+Q", "Close"),
)


def keys_sheet(on_close):
    band = Gtk.FlowBox(
        selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
        max_children_per_line=len(SHORTCUTS), min_children_per_line=2,
        column_spacing=34, row_spacing=10,
        halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
        hexpand=True, vexpand=True, can_focus=False,
    )
    band.add_css_class("keys")
    for keys, alt, action in SHORTCUTS:
        pair = Gtk.Box(spacing=10)
        key = Gtk.Label(label=keys)
        key.add_css_class("key")
        pair.append(key)
        if alt:
            other = Gtk.Label(label=alt)
            other.add_css_class("key")
            other.add_css_class("key-alt")
            pair.append(other)
        what = Gtk.Label(label=action)
        what.add_css_class("key-action")
        pair.append(what)
        band.append(pair)

    backdrop = Gtk.Box(hexpand=True, vexpand=True)
    backdrop.add_css_class("backdrop")
    backdrop.append(band)
    dismiss = Gtk.GestureClick()
    dismiss.connect("pressed", lambda *_a: on_close())
    backdrop.add_controller(dismiss)

    # can_target=False is the whole ballgame. A Gtk.Overlay child keeps
    # its allocation whether or not the revealer shows it, so while
    # hidden it still sat over the window swallowing every click.
    return Gtk.Revealer(
        transition_type=Gtk.RevealerTransitionType.CROSSFADE,
        transition_duration=160, hexpand=True, vexpand=True,
        halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
        reveal_child=False, child=backdrop, can_target=False,
    )
