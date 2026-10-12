"""The collection grid: everything saved, newest first.

Opening the window lands here, because the wallpaper is already on the
desktop. Clicking a tile is how you set it again.
"""

from __future__ import annotations

import threading
from pathlib import Path

import gi

from ..library import collection, credits
from .style import GRID_H, GRID_W
from .thumbs import thumbnail

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


class CollectionGrid(Gtk.Box):
    def __init__(self, pointer, on_pick):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0,
                         vexpand=True)
        self.pointer = pointer
        self.on_pick = on_pick
        self.files: list[Path] = []
        self.buttons: dict[str, Gtk.Button] = {}
        self.thumbs: dict[str, object] = {}
        self.names: list[str] = []
        self.current: Path | None = None

        self.empty = Gtk.Label(label="Nothing saved yet", xalign=0,
                               margin_start=22, margin_top=18)
        self.empty.add_css_class("plate-empty")
        self.append(self.empty)

        self.flow = Gtk.FlowBox(
            valign=Gtk.Align.START, max_children_per_line=8,
            min_children_per_line=2, row_spacing=12, column_spacing=12,
            homogeneous=True, selection_mode=Gtk.SelectionMode.NONE,
        )
        self.flow.add_css_class("grid-flow")
        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True, child=self.flow,
        )
        self.scroller = scroller
        self.append(scroller)

    def refresh(self, current: Path | None = None):
        self.files = collection()
        names = [path.name for path in self.files]
        self.empty.set_visible(not names)
        self.scroller.set_visible(bool(names))
        if names != self.names:
            self.build()
            self.names = names
        self.mark(current)

    def build(self):
        while (child := self.flow.get_first_child()) is not None:
            self.flow.remove(child)
        self.buttons.clear()

        live = {path.name for path in self.files}
        for stale in [name for name in self.thumbs if name not in live]:
            del self.thumbs[stale]

        meta = credits()
        pending = []
        for path in self.files:
            pic = Gtk.Picture(
                content_fit=Gtk.ContentFit.COVER,
                width_request=GRID_W, height_request=GRID_H,
            )
            pic.add_css_class("thumb")
            cached = self.thumbs.get(path.name)
            if cached is not None:
                pic.set_pixbuf(cached)
            else:
                pending.append((path, pic))
            button = Gtk.Button(
                child=pic, hexpand=False, vexpand=False,
                valign=Gtk.Align.START,
            )
            button.add_css_class("grid-tile")
            title = meta.get(path.name, ("", "", ""))[0]
            button.set_tooltip_text(title or path.name)
            button.connect("clicked", self.on_pick, path)
            button.set_cursor(self.pointer)
            self.flow.append(button)
            self.buttons[path.name] = button

        if pending:
            threading.Thread(
                target=self._decode, args=(pending,), daemon=True
            ).start()

    def mark(self, current: Path | None = None):
        if current is not None:
            self.current = current
        here = self.current.name if self.current else None
        for name, button in self.buttons.items():
            if name == here:
                button.add_css_class("current")
            else:
                button.remove_css_class("current")

    def _decode(self, items):
        for path, pic in items:
            buf = thumbnail(path, GRID_W, GRID_H)
            if buf is not None:
                self.thumbs[path.name] = buf
                GLib.idle_add(pic.set_pixbuf, buf)
