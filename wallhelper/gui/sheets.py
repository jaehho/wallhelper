"""The two overlays that only have something to say.

Neither holds any state: both are built once, shown, and dismissed by any key
or a click on the backdrop. Both fill the window so their backdrop can dim it,
which is why both hand back a revealer whose can_target the window switches --
see show_panel, and the comment in shortcuts_sheet about what that fixed.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

GUIDE = (
    ("EACH MORNING",
     "Bing's photograph for the day arrives and becomes your wallpaper. "
     "It is saved automatically."),
    ("THE COLLECTION",
     "Everything fetched is kept. Choose one to set it again, or delete "
     "the ones you no longer want."),
    ("ELSEWHERE",
     "Today's pictures from the other sources. Choosing one saves it "
     "and makes it the wallpaper."),
)

SHORTCUTS = (
    ("D", "", "Delete from the collection"),
    ("U", "", "Undo the delete, while its message is up"),
    ("O", "", "Open the source page"),
    ("E", "", "Expand or collapse Elsewhere"),
    ("F", "", "Fetch the morning photo now"),
    (",", "", "Settings"),
    ("?", "", "This list"),
    ("G", "", "Show the welcome guide"),
    ("Esc", "", "Close"),
)


def guide_sheet(pointer, on_close):
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0,
                   halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    card.add_css_class("guide")
    card.set_size_request(620, -1)

    thesis = Gtk.Label(label="One photograph a day.", xalign=0)
    thesis.add_css_class("guide-thesis")
    card.append(thesis)

    sub = Gtk.Label(
        label="Bing in the morning, and the ones you saved.",
        xalign=0, wrap=True, margin_top=10, max_width_chars=52,
    )
    sub.add_css_class("guide-sub")
    card.append(sub)

    rule = Gtk.Box(margin_top=26, margin_bottom=4)
    rule.add_css_class("hairline")
    card.append(rule)

    for when, what in GUIDE:
        row = Gtk.Box(spacing=26, margin_top=22)
        moment = Gtk.Label(label=when, xalign=0,
                           valign=Gtk.Align.START, wrap=True)
        moment.add_css_class("guide-when")
        moment.set_size_request(150, -1)
        row.append(moment)
        body = Gtk.Label(label=what, xalign=0, wrap=True, hexpand=True,
                         max_width_chars=48)
        body.add_css_class("guide-body")
        row.append(body)
        card.append(row)

    foot = Gtk.Box(spacing=12, margin_top=32)
    hint = Gtk.Label(
        label="SETTINGS is where you switch sources on and off. "
              "? lists every shortcut.",
        xalign=0, wrap=True, hexpand=True, valign=Gtk.Align.CENTER,
        max_width_chars=46,
    )
    hint.add_css_class("guide-foot")
    foot.append(hint)
    start = Gtk.Button(label="START", valign=Gtk.Align.CENTER,
                       tooltip_text="Close the guide  (Esc)")
    start.add_css_class("plate-action")
    start.set_cursor(pointer)
    start.connect("clicked", lambda _b: on_close())
    foot.append(start)
    card.append(foot)

    backdrop = Gtk.Box(hexpand=True, vexpand=True)
    backdrop.add_css_class("backdrop")
    backdrop.append(card)
    dismiss = Gtk.GestureClick()
    dismiss.connect("pressed", lambda *_a: on_close())
    backdrop.add_controller(dismiss)

    return Gtk.Revealer(
        transition_type=Gtk.RevealerTransitionType.CROSSFADE,
        transition_duration=200, hexpand=True, vexpand=True,
        halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
        reveal_child=False, child=backdrop, can_target=False,
    )


def shortcuts_sheet(on_close):
    grid = Gtk.Grid(row_spacing=13, column_spacing=30,
                    halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    grid.add_css_class("shortcuts")
    for line, (keys, alt, action) in enumerate(SHORTCUTS):
        key = Gtk.Label(label=keys, xalign=1)
        key.add_css_class("key")
        grid.attach(key, 0, line, 1, 1)
        other = Gtk.Label(label=alt, xalign=1)
        other.add_css_class("key")
        other.add_css_class("key-alt")
        grid.attach(other, 1, line, 1, 1)
        what = Gtk.Label(label=action, xalign=0)
        what.add_css_class("key-action")
        grid.attach(what, 2, line, 1, 1)

    backdrop = Gtk.Box(hexpand=True, vexpand=True)
    backdrop.add_css_class("backdrop")
    backdrop.append(grid)
    grid.set_hexpand(True)
    grid.set_vexpand(True)
    dismiss = Gtk.GestureClick()
    dismiss.connect("pressed", lambda *_a: on_close())
    backdrop.add_controller(dismiss)

    # can_target=False is the whole ballgame. This revealer fills
    # the overlay so its backdrop can dim everything, and a Gtk.Overlay
    # child keeps its allocation whether or not the revealer is showing
    # its child -- so while hidden it still sat on top of the window
    # swallowing every click. Keys were unaffected, which is why this
    # looked like a settings bug rather than a dead window.
    return Gtk.Revealer(
        transition_type=Gtk.RevealerTransitionType.CROSSFADE,
        transition_duration=160, hexpand=True, vexpand=True,
        halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
        reveal_child=False, child=backdrop, can_target=False,
    )
