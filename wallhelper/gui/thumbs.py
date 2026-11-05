"""Turning a photograph into something the strip can show."""

from __future__ import annotations

import math
import queue
import threading
from collections.abc import Callable
from pathlib import Path

import gi

from ..library import measure
from ..paths import THUMBS
from .style import GRID_H, GRID_W

gi.require_version("Gtk", "4.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402

POOL_THREADS = 4


class Pool:
    """A few threads working through a queue, oldest job first.

    Not a ThreadPoolExecutor: at exit that finishes everything queued,
    so closing the window on 3000 cold thumbnails would leave the
    process decoding for minutes. Daemon threads stop with it. (#18)
    """

    def __init__(self, size: int = POOL_THREADS):
        self.size = size
        self.jobs: queue.SimpleQueue = queue.SimpleQueue()
        self.started = False

    def submit(self, job: Callable, *args) -> None:
        if not self.started:
            self.started = True
            for _ in range(self.size):
                threading.Thread(target=self._work, daemon=True).start()
        self.jobs.put((job, args))

    def _work(self) -> None:
        while True:
            job, args = self.jobs.get()
            try:
                job(*args)
            except Exception:    # one bad tile must not cost a thread
                continue


LOCAL_POOL = Pool()


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
