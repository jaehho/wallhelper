"""The window side, starting with the one thing in it that is pure
formatting: the caption a photograph's dimensions become.

thumbs imports GTK, but nothing here opens a display -- the header
readers are the same ones the strip uses, no window attached.
"""

import struct
import threading
import unittest
import zlib

from tests import guard
from wallhelper.gui import thumbs
from wallhelper.paths import DIR


def setUpModule():
    guard()


def png(width: int, height: int) -> bytes:
    """The smallest PNG that still has an honest IHDR."""
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload)))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00" * (width * 3 + 1) * height))
            + chunk(b"IEND", b""))


def bmp(width: int, height: int) -> bytes:
    """A header GdkPixbuf can measure but library.measure cannot: the fast
    path only reads PNG and JPEG, so this is the fallback being tested."""
    dib = struct.pack("<IiiHH6I", 40, width, height, 1, 24, 0, 0, 0, 0, 0, 0)
    return (b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + len(dib))
            + dib)


class Dimensions(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)

    def test_the_header_answers_without_decoding_the_photo(self):
        path = DIR / "measured.png"
        path.write_bytes(png(3840, 2160))
        self.assertEqual(thumbs.dimensions(path), "3840 \u00d7 2160")

    def test_a_format_the_fast_path_skips_still_measures(self):
        path = DIR / "measured.bmp"
        path.write_bytes(bmp(320, 240))
        self.assertEqual(thumbs.dimensions(path), "320 \u00d7 240")

    def test_something_that_is_not_an_image_has_no_dimensions(self):
        path = DIR / "notes.txt"
        path.write_bytes(b"nope")
        self.assertEqual(thumbs.dimensions(path), "")


class Unreadable(unittest.TestCase):
    def test_a_corrupt_photograph_has_no_thumbnail(self):
        DIR.mkdir(parents=True, exist_ok=True)
        path = DIR / "corrupt.jpg"
        path.write_bytes(b"\xff\xd8 this was a photograph once")
        self.addCleanup(path.unlink)
        self.assertIsNone(thumbs.thumbnail(path))


class PoolOrder(unittest.TestCase):
    def test_jobs_run_oldest_first_and_survive_a_failure(self):
        pool = thumbs.Pool(size=1)
        ran = []
        finished = threading.Event()

        def explode():
            raise ValueError("boom")

        pool.submit(ran.append, "newest")
        pool.submit(explode)
        pool.submit(ran.append, "older")
        pool.submit(finished.set)
        self.assertTrue(finished.wait(5))
        self.assertEqual(ran, ["newest", "older"])
