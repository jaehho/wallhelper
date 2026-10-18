"""Today's pictures from the other sources, for when you want a change.

A short row of thumbs sits above the collection. MORE opens the full
gallery. Choosing one saves it into the collection and makes it the
wallpaper -- one action, because that is the only reason you are here. A
tile already in the collection says SAVED, and choosing it only sets it.

Each source is asked on its own thread and paints when it answers, so a
slow one holds back nobody; one that has nothing to show says why in a
line under the row, in place of the silence a bare label would be.
"""

from __future__ import annotations

import threading

import gi

from ..config import config, gallery_sources
from ..net import FetchError, describe
from ..sources import Listing, adopt, offer_source, target
from .style import GRID_H, GRID_W, LONG_TOAST_SECONDS, THUMB_H, THUMB_W
from .thumbs import remote_thumbnail

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

ROW_LIMIT = 8
SOURCE_TIMEOUT_S = 8      # a source slower than this is a source down


class ElsewhereBar(Gtk.Box):
    def __init__(self, pointer, on_adopt, on_toast, on_set):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("elsewhere-row")
        self.pointer = pointer
        self.on_adopt = on_adopt
        self.on_toast = on_toast
        self.on_set = on_set
        self.cands: list[dict] = []
        self.expanded = False
        self.generation = 0        # a reload invalidates the one before
        self.answers: dict[int, tuple[str, Listing]] = {}
        # Built once per candidate and size: painting again, as the next
        # source answers, must not start the downloads over.
        self.tiles: dict[tuple[str, str, int], Gtk.Button] = {}
        self.marks: list[tuple[dict, Gtk.Label]] = []     # SAVED, per tile

        head = Gtk.Box(spacing=14, valign=Gtk.Align.CENTER)
        self.append(head)
        label = Gtk.Label(label="ELSEWHERE", xalign=0)
        label.add_css_class("elsewhere-label")
        head.append(label)

        self.row = Gtk.Box(spacing=8, hexpand=True)
        head.append(self.row)

        self.more_btn = Gtk.Button(
            label="MORE", valign=Gtk.Align.CENTER,
            tooltip_text="Show every candidate from the other sources  (E)",
        )
        self.more_btn.add_css_class("plate-action")
        self.more_btn.set_cursor(self.pointer)
        self.more_btn.connect("clicked", lambda _b: self.toggle())
        head.append(self.more_btn)

        # One muted line per source that has nothing to show, and why.
        self.notes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                             spacing=2, margin_top=4, visible=False)
        self.append(self.notes)

        self.full = Gtk.FlowBox(
            valign=Gtk.Align.START, max_children_per_line=6,
            min_children_per_line=2, row_spacing=12, column_spacing=12,
            homogeneous=True, selection_mode=Gtk.SelectionMode.NONE,
            margin_top=8,
        )
        self.full_scroller = Gtk.ScrolledWindow(
            max_content_height=320, propagate_natural_height=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            child=self.full, visible=False,
        )
        self.append(self.full_scroller)

    def toggle(self):
        self.expanded = not self.expanded
        self.full_scroller.set_visible(self.expanded)
        self.more_btn.set_label("LESS" if self.expanded else "MORE")

    def reload(self):
        """Ask every gallery source at once, off the main loop, and paint
        each one as it answers. What was on show stays until the first
        new answer, so a reload after saving does not blank the row."""
        names = gallery_sources()
        self.set_visible(bool(names))
        self.generation += 1
        self.answers = {}
        self.tiles = {}
        self.marks = []
        if not names:
            self._show()
            return

        cfg = config()
        for position, name in enumerate(names):
            threading.Thread(
                target=self._ask,
                args=(self.generation, position, name, cfg.get(name) or {}),
                daemon=True,
            ).start()

    def _ask(self, generation, position, name, spec):
        try:
            listing = offer_source(name, spec, timeout=SOURCE_TIMEOUT_S)
        except Exception as err:     # one bad source must not stop the rest
            listing = Listing([], describe(err))
        GLib.idle_add(self._arrive, generation, position, name, listing)

    def _arrive(self, generation, position, name, listing):
        if generation == self.generation:      # not a reload ago
            for cand in listing.candidates:
                cand["name"] = name
            self.answers[position] = (name, listing)
            self._show()
        return False

    def _show(self):
        """Paint what has answered, in the order the sources are listed."""
        answered = [self.answers[spot] for spot in sorted(self.answers)]
        self.cands = [cand for _name, listing in answered
                      for cand in listing.candidates]
        for box in (self.row, self.full, self.notes):
            while (child := box.get_first_child()) is not None:
                box.remove(child)

        for cand in self.cands[:ROW_LIMIT]:
            self.row.append(self.tile(cand, THUMB_W, THUMB_H))
        for cand in self.cands:
            self.full.append(self.tile(cand, GRID_W, GRID_H))
        self.more_btn.set_visible(len(self.cands) > ROW_LIMIT)

        for name, listing in answered:
            if listing.complaint:
                note = Gtk.Label(label=f"{name.upper()} — {listing.complaint}",
                                 xalign=0)
                note.add_css_class("elsewhere-note")
                self.notes.append(note)
        self.notes.set_visible(self.notes.get_first_child() is not None)

    def tile(self, cand: dict, wide: int, high: int) -> Gtk.Button:
        key = (cand["name"], cand["image"], wide)
        if key not in self.tiles:
            self.tiles[key] = self._new_tile(cand, wide, high)
        return self.tiles[key]

    def _new_tile(self, cand: dict, wide: int, high: int) -> Gtk.Button:
        pic = Gtk.Picture(
            content_fit=Gtk.ContentFit.COVER,
            width_request=wide, height_request=high,
        )
        pic.add_css_class("thumb")
        mark = Gtk.Label(label="SAVED", halign=Gtk.Align.START,
                         valign=Gtk.Align.END, can_target=False)
        mark.add_css_class("thumb-mark")
        self.marks.append((cand, mark))
        mark.set_visible(self.has(cand))
        face = Gtk.Overlay(child=pic)
        face.add_overlay(mark)
        button = Gtk.Button(
            child=face, hexpand=False, vexpand=False,
            valign=Gtk.Align.START,
        )
        button.add_css_class("grid-tile")
        tip = cand.get("title") or cand.get("name") or ""
        button.set_tooltip_text(tip)
        button.set_cursor(self.pointer)
        button.connect("clicked", self._pick, cand)
        threading.Thread(
            target=self._decode, args=(cand, pic, wide, high), daemon=True
        ).start()
        return button

    def has(self, cand: dict) -> bool:
        """Whether the collection already holds this candidate."""
        return target(cand.get("name") or "", cand).exists()

    def refresh_marks(self):
        """SAVED follows the folder, which a delete or an undo changes
        without asking the sources anything."""
        for cand, mark in self.marks:
            mark.set_visible(self.has(cand))

    def _decode(self, cand, pic, wide, high):
        buf = remote_thumbnail(cand.get("image") or "", wide, high)
        if buf is not None:
            GLib.idle_add(pic.set_pixbuf, buf)

    def _pick(self, _button, cand: dict):
        name = cand.get("name") or ""
        if self.has(cand):
            self.on_set(target(name, cand))
            return
        spec = config().get(name) or {}
        self.on_toast("Saving…")

        def work():
            path, why = None, ""
            try:
                path = adopt(name, spec, cand)
            except FetchError as err:
                why = str(err)
            except Exception as err:   # a thread that dies says nothing
                why = describe(err)
            GLib.idle_add(self._done, name, path, why, cand)

        threading.Thread(target=work, daemon=True).start()

    def _done(self, name, path, why, cand):
        if path is None:
            self.on_toast(f"{name} — {why}", timeout=LONG_TOAST_SECONDS,
                          priority=Adw.ToastPriority.HIGH)
        else:
            self.on_adopt(path, cand)
        return False
