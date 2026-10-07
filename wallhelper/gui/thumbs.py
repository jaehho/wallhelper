"""Turning a photograph on disk into something the strip can show."""

from __future__ import annotations

import math
from pathlib import Path

import gi

from ..library import measure
from ..paths import THUMBS
from .style import THUMB_H, THUMB_W

gi.require_version("Gtk", "4.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402


def thumbnail(path: Path):
    """Exactly THUMB_W x THUMB_H, centre-cropped, cached on disk.

    Decoding one costs ~200ms because the JPEG is decoded in full before
    being scaled; reading the cached PNG costs ~2ms. With twenty photos
    that is the difference between the strip appearing and the strip
    arriving. Keyed by name and invalidated by mtime.

    Not scale-to-fit. GdkPixbuf's aspect-preserving scale returns whatever
    shape the source is, and a Gtk.Picture takes its *natural* size from
    the pixbuf it holds -- a size request is only a floor. The strip
    scrolls horizontally, so there is always room for natural size, and a
    portrait photo came out a narrow sliver next to an oversized wide one.
    Cropping makes the row uniform by construction instead of asking the
    layout nicely.

    Decoded at 1x on purpose: the pixbuf's dimensions become the widget's
    natural size in logical units, so a 2x buffer would produce 2x-wide
    thumbnails rather than sharper ones.
    """
    cached = THUMBS / f"{path.name}.png"
    try:
        if cached.stat().st_mtime >= path.stat().st_mtime:
            return GdkPixbuf.Pixbuf.new_from_file(str(cached))
    except (OSError, GLib.Error):
        pass

    try:
        _fmt, src_w, src_h = GdkPixbuf.Pixbuf.get_file_info(str(path))
        if not src_w or not src_h:
            return None
        scale = max(THUMB_W / src_w, THUMB_H / src_h)
        buf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path),
            max(THUMB_W, math.ceil(src_w * scale)),
            max(THUMB_H, math.ceil(src_h * scale)),
            True,
        )
        buf = buf.new_subpixbuf(
            (buf.get_width() - THUMB_W) // 2,
            (buf.get_height() - THUMB_H) // 2,
            THUMB_W, THUMB_H,
        )
    except (GLib.Error, TypeError, ValueError):
        return None

    try:
        THUMBS.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_name(f".{path.name}.new")
        buf.savev(str(tmp), "png", [], [])
        tmp.replace(cached)
    except (OSError, GLib.Error):
        pass                     # a cold cache is slow, not broken
    return buf


def dimensions(path: Path) -> str:
    size = measure(path)
    if size is None:
        try:
            # An unrecognized file answers (-1, -1), not (0, 0): the
            # dimension caption would read '-1 \u00d7 -1' over a broken photo.
            _fmt, width, height = GdkPixbuf.Pixbuf.get_file_info(str(path))
            size = (width, height) if width > 0 and height > 0 else None
        except (GLib.Error, TypeError, ValueError):
            size = None
    return f"{size[0]} \u00d7 {size[1]}" if size else ""

# A day's cycle, which is what there is to explain. Not a feature tour:
# the only genuinely surprising behaviour is that not keeping a photograph
