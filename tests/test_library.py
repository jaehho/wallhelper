"""Reading a photo off disk, and what the folder used to hold."""

import struct
import unittest
import zlib

from tests import guard
from wallhelper import library
from wallhelper.paths import CREDITS, CURRENT, DIR


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


class MigrateCollection(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        kept = DIR / "kept"
        liked = DIR / "liked"
        for folder in (kept, liked):
            if folder.is_dir():
                for path in folder.glob("*.*"):
                    path.unlink()
                folder.rmdir()
        for path in DIR.glob("*.*"):
            if path.is_file() and not path.name.startswith("."):
                path.unlink()
        CREDITS.unlink(missing_ok=True)
        CURRENT.unlink(missing_ok=True)
        self.kept = kept

    def make(self, name, also_in_dir=False):
        self.kept.mkdir(parents=True, exist_ok=True)
        path = self.kept / name
        path.write_bytes(png(4, 4))
        if also_in_dir:
            (DIR / name).hardlink_to(path)
        return path

    def test_a_hardlink_twin_loses_the_kept_name_only(self):
        path = self.make("20260905-bing-x.png", also_in_dir=True)
        inode = path.stat().st_ino
        library.migrate_collection()
        self.assertEqual((DIR / "20260905-bing-x.png").stat().st_ino, inode)
        self.assertFalse(self.kept.exists())

    def test_a_kept_only_file_moves_into_the_folder(self):
        self.make("20260905-bing-only.png")
        moved = library.migrate_collection()
        self.assertEqual(moved, ["20260905-bing-only.png"])
        self.assertTrue((DIR / "20260905-bing-only.png").is_file())
        self.assertFalse(self.kept.exists())

    def test_a_name_clash_keeps_both_bytes(self):
        kept = self.make("20260905-bing-clash.png")
        kept_size = kept.stat().st_size
        other = DIR / "20260905-bing-clash.png"
        other.write_bytes(png(9, 9))
        library.migrate_collection()
        self.assertTrue(other.is_file())
        moved = DIR / "20260905-bing-clash-kept.png"
        self.assertTrue(moved.is_file())
        self.assertEqual(moved.stat().st_size, kept_size)

    def test_liked_is_the_older_name_for_kept(self):
        liked = DIR / "liked"
        liked.mkdir(parents=True, exist_ok=True)
        (liked / "20260905-bing-old.png").write_bytes(png(4, 4))
        library.migrate_collection()
        self.assertTrue((DIR / "20260905-bing-old.png").is_file())
        self.assertFalse(liked.exists())

    def test_current_is_repointed_off_kept(self):
        path = self.make("20260905-bing-cur.png", also_in_dir=True)
        CURRENT.symlink_to(path)
        library.migrate_collection()
        self.assertEqual(CURRENT.resolve(), (DIR / "20260905-bing-cur.png")
                         .resolve())

    def test_collection_is_just_the_folder(self):
        self.make("20260905-bing-a.png", also_in_dir=True)
        self.make("20260904-bing-b.png")
        library.migrate_collection()
        names = [p.name for p in library.collection()]
        self.assertEqual(names,
                         ["20260905-bing-a.png", "20260904-bing-b.png"])
