"""Reading a photo off disk, and deciding what goes."""

import struct
import unittest
import zlib

from paperboy import library
from paperboy.paths import CREDITS, DIR, KEPT
from tests import guard


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


class Slugify(unittest.TestCase):
    def test_folds_accents(self):
        self.assertEqual(library.slugify("Café Déjà vu"), "Cafe-Deja-vu")

    def test_non_latin_gives_nothing_to_build_on(self):
        # The caller has to fall through to another candidate rather than
        # naming every Japanese-titled photo the same thing.
        self.assertEqual(library.slugify("日本語"), "")

    def test_truncates(self):
        self.assertLessEqual(len(library.slugify("a" * 200)), 44)


class Stamp(unittest.TestCase):
    def test_reads_the_date_and_source_out_of_a_filename(self):
        self.assertEqual(library.stamp("20260906-bing-A-reservoir.jpg"),
                         ("2026·09·06", "bing"))

    def test_a_hand_dropped_file_claims_nothing(self):
        self.assertEqual(library.stamp("holiday.jpg"), ("", ""))


class Measure(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)

    def test_reads_png_dimensions_from_the_header(self):
        path = DIR / "shot.png"
        path.write_bytes(png(1920, 1080))
        self.assertEqual(library.measure(path), (1920, 1080))

    def test_a_file_that_is_not_an_image_measures_nothing(self):
        path = DIR / "notes.png"
        path.write_bytes(b"nope")
        self.assertIsNone(library.measure(path))


class Sweep(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        KEPT.mkdir(parents=True, exist_ok=True)
        for path in list(DIR.glob("*.png")) + list(KEPT.glob("*.png")):
            path.unlink()
        CREDITS.unlink(missing_ok=True)

    def make(self, name, credited=True, kept=False):
        path = DIR / name
        path.write_bytes(png(4, 4))
        if credited:
            library.remember(name, "A title", "Someone", "https://example.com")
        if kept:
            (KEPT / name).hardlink_to(path)
        return path

    def test_an_unkept_download_goes(self):
        self.make("20260905-bing-old.png")
        self.assertEqual(library.sweep(), ["20260905-bing-old.png"])

    def test_a_kept_photo_stays(self):
        self.make("20260905-bing-keeper.png", kept=True)
        self.make("20260904-bing-other.png")
        self.assertEqual(library.sweep(), ["20260904-bing-other.png"])

    def test_a_file_we_did_not_download_is_never_touched(self):
        # The version this replaced deleted by age alone and wiped a
        # hand-built library on its first run.
        self.make("20260905-bing-ours.png")
        self.make("holiday.png", credited=False)
        self.assertEqual(library.sweep(), ["20260905-bing-ours.png"])
        self.assertTrue((DIR / "holiday.png").exists())

    def test_the_spared_one_survives(self):
        keep = self.make("20260906-bing-today.png")
        self.make("20260905-bing-yesterday.png")
        self.assertEqual(library.sweep(spare=keep),
                         ["20260905-bing-yesterday.png"])

    def test_sweeping_forgets_the_credit_too(self):
        self.make("20260905-bing-old.png")
        library.sweep()
        self.assertNotIn("20260905-bing-old.png", library.credits())
