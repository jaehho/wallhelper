"""The caption over the strip: a wall label, not a form.

Title first, then where it was taken and the accession line. The only
words to press are DELETE and DONE; the source's name is the link to its
page. Setting a photograph is moving to it in the strip, so nothing here
says SET.
"""

from __future__ import annotations

from pathlib import Path

import gi

from ..library import label
from .style import tracked

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402


def facts_line(info: dict[str, str], size: str) -> tuple[str, str, str]:
    """The place, the dimensions and the photographer, each tracked, any
    of them empty. A photograph nobody described says nothing rather
    than a placeholder."""
    author = info.get("author", "")
    return (tracked(info.get("place", "")), size,
            tracked(f"\u00a9 {author}") if author else "")


class Plate(Gtk.Box):
    def __init__(self, pointer, on_delete, on_source, on_done):
        super().__init__(spacing=0)
        self.add_css_class("plate")
        self.pointer = pointer
        self.url = ""

        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0,
                        hexpand=True, valign=Gtk.Align.CENTER)
        self.append(words)

        self.title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                               single_line_mode=True)
        self.title.add_css_class("plate-title")
        words.append(self.title)

        row = Gtk.Box(spacing=18, margin_top=6)
        words.append(row)
        # Only the last fact gives way. A label that may shorten is
        # measured a letter short with the tracking on, so place and size,
        # which are short, never shorten.
        self.place = self._fact(row, "plate-place", expand=False)
        self.size = self._fact(row, "plate-row", expand=False)
        self.source = Gtk.Button(label="",
                                 tooltip_text="Open the source page  (O)")
        self.source.add_css_class("plate-action")
        self.source.add_css_class("plate-link")
        self._quiet(self.source, on_source)
        row.append(self.source)
        self.author = self._fact(row, "plate-row", expand=True)

        actions = Gtk.Box(spacing=26, valign=Gtk.Align.END)
        self.append(actions)
        self.delete_btn = Gtk.Button(
            label="DELETE", tooltip_text="Move it to the Trash  (D)")
        self.delete_btn.add_css_class("plate-action")
        self.delete_btn.add_css_class("danger")
        self._quiet(self.delete_btn, on_delete)
        actions.append(self.delete_btn)
        done = Gtk.Button(label="DONE",
                          tooltip_text="Keep this one and close  (Esc)")
        done.add_css_class("plate-action")
        self._quiet(done, on_done)
        actions.append(done)

    def _fact(self, row, css, *, expand):
        fact = Gtk.Label(xalign=0, single_line_mode=True, hexpand=expand)
        if expand:
            fact.set_ellipsize(Pango.EllipsizeMode.END)
        fact.add_css_class(css)
        row.append(fact)
        return fact

    def _quiet(self, button, handler):
        """A button the pointer presses and focus never lands on, so the
        arrows always belong to the strip. Every one has a key."""
        button.set_focusable(False)
        button.set_focus_on_click(False)
        button.set_cursor(self.pointer)
        button.connect("clicked", lambda _b: handler())

    def refresh(self, path: Path | None, size: str = ""):
        """A title line only when there is a title: a photograph nobody
        titled shows its place or its file name instead."""
        info = label(path) if path else {}
        title = info.get("title", "")
        src, url = info.get("source", ""), info.get("url", "")
        place, size, author = facts_line(info, size)
        if path is not None and not (title or place):
            title = Path(info.get("file") or path).stem
        self._set(self.title, title)
        self._set(self.place, place)
        self._set(self.size, size)
        self._set(self.author, author)
        self.source.set_label(tracked(src))
        self.source.set_visible(bool(src and url))
        self.url = url
        self.delete_btn.set_sensitive(path is not None)

    def say(self, title: str, line: str):
        """The morning's place is selected: what came of the fetch."""
        self._set(self.title, title)
        self._set(self.place, tracked(line))
        for fact in (self.size, self.author):
            self._set(fact, "")
        self.source.set_visible(False)
        self.url = ""
        self.delete_btn.set_sensitive(False)

    @staticmethod
    def _set(widget, text):
        widget.set_text(text)
        widget.set_visible(bool(text))
