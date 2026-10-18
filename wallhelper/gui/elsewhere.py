"""Today's pictures from the other sources, for when you want a change.

A short row of thumbs sits above the collection. MORE opens the full
gallery. Choosing one saves it into the collection and makes it the
wallpaper -- one action, because that is the only reason you are here.
"""

from __future__ import annotations

import threading

import gi

from ..config import config, gallery_sources
from ..net import FetchError, describe
from ..sources import adopt, list_source
from .style import GRID_H, GRID_W, LONG_TOAST_SECONDS, THUMB_H, THUMB_W
from .thumbs import remote_thumbnail

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

ROW_LIMIT = 8


class ElsewhereBar(Gtk.Box):
    def __init__(self, pointer, on_adopt, on_toast):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("elsewhere-row")
        self.pointer = pointer
        self.on_adopt = on_adopt
        self.on_toast = on_toast
        self.cands: list[dict] = []
        self.expanded = False

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
        """List every gallery source off the main loop, then paint."""
        names = gallery_sources()
        self.set_visible(bool(names))
        if not names:
            return

        def work():
            cfg = config()
            found: list[dict] = []
            for name in names:
                try:
                    cands = list_source(name, cfg.get(name) or {})
                except Exception:  # one bad source must not kill the row
                    continue
                for cand in cands:
                    cand["name"] = name
                found.extend(cands)
            GLib.idle_add(self._show, found)

        threading.Thread(target=work, daemon=True).start()

    def _show(self, cands):
        self.cands = cands
        while (child := self.row.get_first_child()) is not None:
            self.row.remove(child)
        while (child := self.full.get_first_child()) is not None:
            self.full.remove(child)

        for cand in cands[:ROW_LIMIT]:
            self.row.append(self.tile(cand, THUMB_W, THUMB_H))
        for cand in cands:
            self.full.append(self.tile(cand, GRID_W, GRID_H))
        self.more_btn.set_visible(len(cands) > ROW_LIMIT)
        return False

    def tile(self, cand: dict, wide: int, high: int) -> Gtk.Button:
        pic = Gtk.Picture(
            content_fit=Gtk.ContentFit.COVER,
            width_request=wide, height_request=high,
        )
        pic.add_css_class("thumb")
        button = Gtk.Button(
            child=pic, hexpand=False, vexpand=False,
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

    def _decode(self, cand, pic, wide, high):
        buf = remote_thumbnail(cand.get("image") or "", wide, high)
        if buf is not None:
            GLib.idle_add(pic.set_pixbuf, buf)

    def _pick(self, _button, cand: dict):
        name = cand.get("name") or ""
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
