"""The caption for whatever is selected: a wall label, not a form.

Title first, then where it was taken, then an accession line. Actions are
DELETE and OPEN SOURCE. Setting a photograph is choosing it in the grid;
there is no second signal on this bar.
"""

from __future__ import annotations

from pathlib import Path

import gi

from ..library import label
from .style import tracked

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402


class Plate(Gtk.Box):
    def __init__(self, pointer, on_delete, on_source):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("plate")
        self.pointer = pointer
        self.on_delete = on_delete
        self.on_source = on_source
        self.url = ""
        self.build()

    def build(self):
        self.title = Gtk.Label(
            xalign=0, ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True,
        )
        self.title.add_css_class("plate-title")
        self.append(self.title)

        self.place = Gtk.Label(
            xalign=0, ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True, margin_top=9,
        )
        self.place.add_css_class("plate-place")
        self.append(self.place)

        row = Gtk.Box(spacing=0, margin_top=12)
        self.append(row)

        facts = Gtk.Box(spacing=0, hexpand=True)
        row.append(facts)

        self.size = Gtk.Label(xalign=0)
        self.size.add_css_class("plate-row")
        facts.append(self.size)

        self.source = Gtk.Button(
            label="", tooltip_text="Open the source page")
        self.source.add_css_class("plate-action")
        self.source.add_css_class("plate-link")
        self.source.connect("clicked", self.on_source)
        self.source.set_cursor(self.pointer)
        facts.append(self.source)

        self.author = Gtk.Label(
            xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True,
        )
        self.author.add_css_class("plate-row")
        facts.append(self.author)

        self.delete_btn = Gtk.Button(
            label="DELETE", margin_start=24,
            tooltip_text="Move this photograph to the Trash  (D)",
        )
        self.delete_btn.add_css_class("plate-action")
        self.delete_btn.add_css_class("danger")
        self.delete_btn.connect("clicked", self.on_delete)
        self.delete_btn.set_cursor(self.pointer)
        row.append(self.delete_btn)

    def refresh(self, path: Path | None, size: str = ""):
        """No title line rather than a placeholder one. A photograph
        nobody titled has nothing to say here, and the plate shrinks."""
        info = label(path) if path else {}

        title = info.get("title", "")
        if path is None:
            title = "No photograph selected"
        self.title.set_text(title)
        self.title.set_visible(bool(title))

        src, url = info.get("source", ""), info.get("url", "")
        named = bool(src and url)

        place = info.get("place", "")
        if path is not None and not (place or title or named):
            place = Path(info.get("file") or path).stem
        self.place.set_text(tracked(place))
        self.place.set_visible(bool(place))
        self.place.set_margin_top(9 if title else 0)

        self.size.set_text(size)
        self.size.set_visible(bool(size))

        self.source.set_label(tracked(src))
        self.source.set_visible(named)
        self.source.set_margin_start(18 if size else 0)
        self.url = url

        author = info.get("author", "")
        self.author.set_text(tracked(f"© {author}") if author else "")
        self.author.set_visible(bool(author))
        self.author.set_margin_start(18 if (size or named) else 0)

        self.delete_btn.set_sensitive(path is not None)
