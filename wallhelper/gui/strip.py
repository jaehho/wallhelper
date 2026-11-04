"""The strip: every photograph saved, newest first, in one row.

It sits on the bottom edge of an empty workspace, so the desktop above it
is the preview: moving the selection puts that photograph on the wall,
and closing keeps whatever is there (#24).

A Gtk.ListView, so a collection of thousands builds, and decodes, only
the tiles in view. Its first place can hold the morning's fetch instead
of a photograph: on its way, or why it did not come.
"""

from __future__ import annotations

import time
from pathlib import Path

import gi

from ..library import credits
from .style import GRID_H, GRID_W, TILE_GAP
from .thumbs import LOCAL_POOL, thumbnail

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

ARRIVING = "arriving"
FAILED = "failed"


class Item(GObject.Object):
    """One place in the strip: a photograph, or the morning's fetch.

    `status` is "" for a photograph, else ARRIVING or FAILED, and then
    `message` says what the fetch came to."""

    def __init__(self, path: Path | None = None, status: str = "",
                 message: str = ""):
        super().__init__()
        self.path = path
        self.status = status
        self.message = message

    @property
    def name(self) -> str:
        return self.path.name if self.path else f":{self.status}"


def mark_for(name: str, *, today: str, before: str, selected: str) -> str:
    """The word a tile wears, if any.

    TODAY on the morning's photograph. BEFORE on the one that was on the
    wall when the strip opened, while the selection is somewhere else: it
    is the way back, so it says so only when there is a way to go.
    """
    if name == before and name != selected:
        return "BEFORE"
    if today and name.startswith(today):
        return "TODAY"
    return ""


def status_text(item: Item) -> tuple[str, str]:
    """What the morning's place says: a word for the tile, a line under
    it."""
    if item.status == ARRIVING:
        return "TODAY", "On its way"
    return "TODAY", item.message or "Did not come"


class Tile(Gtk.Overlay):
    """A photograph cut to the tile, and the words it may carry."""

    def __init__(self):
        super().__init__()
        self.add_css_class("tile")
        self.item: Item | None = None
        self.picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.COVER, can_shrink=True,
            width_request=GRID_W, height_request=GRID_H,
        )
        self.picture.add_css_class("thumb")
        self.set_child(self.picture)

        self.mark = Gtk.Label(halign=Gtk.Align.START, valign=Gtk.Align.END,
                              visible=False)
        self.mark.add_css_class("tile-mark")
        self.add_overlay(self.mark)

        self.note = Gtk.Label(
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, wrap=True,
            justify=Gtk.Justification.CENTER, max_width_chars=26,
            visible=False,
        )
        self.note.add_css_class("tile-note")
        self.add_overlay(self.note)

    def show(self, buf, *, unreadable: bool = False):
        self.remove_css_class("said")
        self.picture.set_pixbuf(buf)
        self.note.set_text("UNREADABLE" if unreadable else "")
        self.note.set_visible(unreadable)

    def say(self, word: str, line: str):
        self.add_css_class("said")
        self.picture.set_pixbuf(None)
        self.set_mark(word)
        self.note.set_text(line)
        self.note.set_visible(bool(line))

    def set_mark(self, word: str):
        self.mark.set_text(word)
        self.mark.set_visible(bool(word))


class Strip(Gtk.ScrolledWindow):
    """on_select(item) runs when the selection moves, by key or by click,
    and not when the strip moves it itself (show). on_activate(item) is
    Enter or a double click; a click on the morning's place when it
    failed is one too."""

    def __init__(self, pointer, on_select, on_activate):
        super().__init__(
            hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
            vscrollbar_policy=Gtk.PolicyType.NEVER,
            hexpand=True, vexpand=True,
        )
        self.add_css_class("strip-scroll")
        self.pointer = pointer
        self.on_select = on_select
        self.on_activate = on_activate
        self.thumbs: dict[str, object] = {}   # name -> pixbuf, None = broken
        self.asked: set[str] = set()           # decodes on their way
        self.bound: dict[str, Tile] = {}       # name -> tile showing it
        self.today = ""
        self.before = ""
        self.quiet = False      # the strip moving its own selection

        self.store = Gio.ListStore(item_type=Item)
        self.selection = Gtk.SingleSelection(
            model=self.store, autoselect=False, can_unselect=False)
        self.selection.connect("selection-changed", self._changed)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        factory.connect("unbind", self._unbind)

        self.view = Gtk.ListView(
            model=self.selection, factory=factory,
            orientation=Gtk.Orientation.HORIZONTAL,
            single_click_activate=False,
        )
        self.view.add_css_class("strip")
        self.view.connect("activate", self._activated)
        self.set_child(self.view)

        # A mouse wheel turns up and down; the strip runs sideways.
        wheel = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL)
        wheel.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        wheel.connect("scroll", self._wheel)
        self.add_controller(wheel)

    # --- what is in it ----------------------------------------------------

    def show(self, files: list[Path], *, select: Path | None,
             status: Item | None = None, before: Path | None = None):
        """Fill the strip and put the selection on `select` (else the first
        photograph) without telling on_select: nothing moved by hand."""
        self.today = time.strftime("%Y%m%d-")
        self.before = before.name if before else ""
        items = ([status] if status else []) + [Item(path) for path in files]
        names = [item.name for item in items]
        self.quiet = True
        try:
            if names != self.names():
                self.store.splice(0, self.store.get_n_items(), items)
                live = set(names)
                for stale in [name for name in self.thumbs
                              if name not in live]:
                    del self.thumbs[stale]
            elif status is not None:
                # Same places, but what the morning's says may have
                # changed.
                self.store.splice(0, 1, [status])
        finally:
            self.quiet = False
        where = self.index_of(select.name if select else "")
        if where is None:
            where = 1 if status is not None and len(items) > 1 else 0
        if items:
            self.put(where, quiet=True)

    def names(self) -> list[str]:
        return [self.store.get_item(i).name
                for i in range(self.store.get_n_items())]

    def index_of(self, name: str) -> int | None:
        for i in range(self.store.get_n_items()):
            if self.store.get_item(i).name == name:
                return i
        return None

    def selected(self) -> Item | None:
        return self.selection.get_selected_item()

    def selected_index(self) -> int:
        return self.selection.get_selected()

    # --- moving -----------------------------------------------------------

    def put(self, index: int, *, quiet: bool = False):
        """Select, focus and centre the place at `index`, clamped."""
        count = self.store.get_n_items()
        if not count:
            return
        index = max(0, min(index, count - 1))
        info = Gtk.ScrollInfo()
        info.set_center_horizontal(True)
        self.quiet = quiet
        try:
            self.view.scroll_to(
                index, Gtk.ListScrollFlags.SELECT | Gtk.ListScrollFlags.FOCUS,
                info)
            # scroll_to does not select what is already selected, and a
            # fresh store may hold nothing selected yet.
            if self.selection.get_selected() != index:
                self.selection.set_selected(index)
        finally:
            self.quiet = False
        self._remark()

    def move(self, step: int):
        here = self.selection.get_selected()
        if here == Gtk.INVALID_LIST_POSITION:
            here = 0
        self.put(here + step)

    def focus_selected(self):
        """Give the selected place keyboard focus again, unmoved."""
        here = self.selection.get_selected()
        if here != Gtk.INVALID_LIST_POSITION:
            self.put(here, quiet=True)

    # --- the list view's side ----------------------------------------------

    def _changed(self, _selection, _position, _count):
        self._remark()
        if not self.quiet and (item := self.selected()) is not None:
            self.on_select(item)

    def _activated(self, _view, position):
        item = self.store.get_item(position)
        if item is not None:
            self.on_activate(item)

    def _setup(self, _factory, list_item):
        tile = Tile()
        click = Gtk.GestureClick()
        click.connect("released", self._clicked, tile)
        tile.add_controller(click)
        tile.set_cursor(self.pointer)
        list_item.set_child(tile)

    def _clicked(self, _gesture, _count, _x, _y, tile):
        if tile.item is not None and tile.item.status == FAILED:
            self.on_activate(tile.item)

    def _bind(self, _factory, list_item):
        tile, item = list_item.get_child(), list_item.get_item()
        tile.item = item
        if item.status:
            tile.say(*status_text(item))
            tile.set_tooltip_text(None)
            return
        name = item.name
        self.bound[name] = tile
        title = credits().get(name, ("", "", ""))[0]
        tile.set_tooltip_text(title or name)
        if name in self.thumbs:
            buf = self.thumbs[name]
            tile.show(buf, unreadable=buf is None)
        else:
            tile.show(None)
            if name not in self.asked:
                self.asked.add(name)
                LOCAL_POOL.submit(self._decode, item.path)
        tile.set_mark(self._mark(name))

    def _unbind(self, _factory, list_item):
        tile, item = list_item.get_child(), list_item.get_item()
        if item is not None and self.bound.get(item.name) is tile:
            del self.bound[item.name]
        tile.item = None

    def _decode(self, path: Path):
        buf = thumbnail(path, GRID_W, GRID_H)
        GLib.idle_add(self._decoded, path.name, buf)

    def _decoded(self, name: str, buf):
        self.asked.discard(name)
        self.thumbs[name] = buf
        tile = self.bound.get(name)
        if tile is not None and tile.item is not None \
                and tile.item.name == name:
            tile.show(buf, unreadable=buf is None)
        return False

    def _mark(self, name: str) -> str:
        item = self.selected()
        return mark_for(name, today=self.today, before=self.before,
                        selected=item.name if item else "")

    def _remark(self):
        for name, tile in self.bound.items():
            tile.set_mark(self._mark(name))

    def _wheel(self, controller, _dx, dy):
        adjustment = self.get_hadjustment()
        step = dy
        if controller.get_unit() == Gdk.ScrollUnit.WHEEL:
            step = dy * (GRID_W + TILE_GAP)
        adjustment.set_value(adjustment.get_value() + step)
        return True
