"""Turning a photograph into something the grid can show."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import gi

from ..library import measure
from ..net import fetch_url
from ..paths import THUMBS
from .style import GRID_H, GRID_W, THUMB_H, THUMB_W

gi.require_version("Gtk", "4.0")
from gi.repository import GdkPixbuf, Gio, GLib  # noqa: E402


def _crop(buf, wide: int, high: int):
    return buf.new_subpixbuf(
        (buf.get_width() - wide) // 2,
        (buf.get_height() - high) // 2,
        wide, high,
    )


def thumbnail(path: Path, wide: int = GRID_W, high: int = GRID_H):
    """Exactly wide x high, centre-cropped, cached on disk.

    Decoding one costs ~200ms because the JPEG is decoded in full before
    being scaled; reading the cached PNG costs ~2ms. Keyed by name and
    size, invalidated by mtime.

    Not scale-to-fit. GdkPixbuf's aspect-preserving scale returns whatever
    shape the source is, and a Gtk.Picture takes its *natural* size from
    the pixbuf it holds -- a size request is only a floor. Cropping makes
    the tile uniform by construction instead of asking the layout nicely.

    Decoded at 1x on purpose: the pixbuf's dimensions become the widget's
    natural size in logical units, so a 2x buffer would produce 2x-wide
    thumbnails rather than sharper ones.
    """
    cached = THUMBS / f"{path.name}-{wide}x{high}.png"
    try:
        if cached.stat().st_mtime >= path.stat().st_mtime:
            return GdkPixbuf.Pixbuf.new_from_file(str(cached))
    except (OSError, GLib.Error):
        pass

    try:
        _fmt, src_w, src_h = GdkPixbuf.Pixbuf.get_file_info(str(path))
        if not src_w or not src_h:
            return None
        scale = max(wide / src_w, high / src_h)
        buf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path),
            max(wide, math.ceil(src_w * scale)),
            max(high, math.ceil(src_h * scale)),
            True,
        )
        buf = _crop(buf, wide, high)
    except (GLib.Error, TypeError, ValueError):
        return None

    try:
        THUMBS.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_name(f".{path.name}-{wide}x{high}.new")
        buf.savev(str(tmp), "png", [], [])
        tmp.replace(cached)
    except (OSError, GLib.Error):
        pass                     # a cold cache is slow, not broken
    return buf


def remote_thumbnail(url: str, wide: int = THUMB_W, high: int = THUMB_H):
    """The same crop, for a photograph that is still only a URL."""
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    cached = THUMBS / f"remote-{digest}-{wide}x{high}.png"
    try:
        return GdkPixbuf.Pixbuf.new_from_file(str(cached))
    except (OSError, GLib.Error):
        pass

    try:
        data = fetch_url(url, timeout=30)
        stream = Gio.MemoryInputStream.new_from_data(data, None)
        full = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
        src_w, src_h = full.get_width(), full.get_height()
        if not src_w or not src_h:
            return None
        scale = max(wide / src_w, high / src_h)
        stream = Gio.MemoryInputStream.new_from_data(data, None)
        buf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
            stream,
            max(wide, math.ceil(src_w * scale)),
            max(high, math.ceil(src_h * scale)),
            True, None,
        )
        buf = _crop(buf, wide, high)
    except (GLib.Error, OSError, TypeError, ValueError):
        return None

    try:
        THUMBS.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_name(f".{cached.name}.new")
        buf.savev(str(tmp), "png", [], [])
        tmp.replace(cached)
    except (OSError, GLib.Error):
        pass
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
