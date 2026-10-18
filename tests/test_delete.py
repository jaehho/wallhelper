"""Deleting a photograph keeps what a restore would need, and tells the
truth about where the photograph went.

gio is stood in for by a wastebasket that is a folder, so the real
trash(), in_trash() and parse_trash() run end to end; nothing here
reaches the desktop's Trash or hyprpaper.
"""

import shutil
import subprocess
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from tests import guard
from tests.test_library import png
from wallhelper import library
from wallhelper.gui import window
from wallhelper.paths import CREDITS, CURRENT, DIR, THUMBS


def setUpModule():
    guard()


class Wastebasket:
    """`gio trash` and `gio list`, with a folder for the Trash."""

    def __init__(self, folder, refuses=False):
        self.folder = folder
        self.refuses = refuses
        self.held = []          # (name in the bin, where it came from)

    def __call__(self, argv, **_kwargs):
        if argv[:2] == ["gio", "trash"]:
            return self.trash(Path(argv[2]), argv)
        if argv[:2] == ["gio", "list"]:
            lines = [
                f"trash:///{urllib.parse.quote(name)}\t3\t(regular)\t"
                f"trash::orig-path={was} "
                "trash::deletion-date=2026-10-18T01:19:06"
                for name, was in self.held
            ]
            return subprocess.CompletedProcess(
                argv, 0, "".join(line + "\n" for line in lines), "")
        msg = f"unexpected call: {argv}"
        raise AssertionError(msg)

    def trash(self, path, argv):
        if self.refuses:
            return subprocess.CompletedProcess(argv, 1, b"", b"no trash")
        shutil.move(path, self.folder / path.name)
        self.held.append((path.name, path))
        return subprocess.CompletedProcess(argv, 0, b"", b"")


def fresh_collection():
    DIR.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    for folder in (DIR, THUMBS):
        for path in folder.iterdir():
            if path.is_file() or path.is_symlink():
                path.unlink()


def photograph(name, title=None):
    path = DIR / name
    path.write_bytes(png(4, 4))
    if title:
        with CREDITS.open("a") as ledger:
            ledger.write(f"{name}\t{title}\t(c) someone\thttps://x.test\n")
    return path


def thumbnail_for(name, size="312x176"):
    cached = THUMBS / f"{name}-{size}.png"
    cached.write_bytes(png(4, 4))
    return cached


def ledger_names():
    return [line.split("\t")[0] for line in CREDITS.read_text().splitlines()]


class Setup(unittest.TestCase):
    def setUp(self):
        fresh_collection()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.wastebasket = Wastebasket(Path(folder.name))
        run = mock.patch.object(library.subprocess, "run",
                                self.wastebasket)
        run.start()
        self.addCleanup(run.stop)
        push = mock.patch.object(library, "push_wallpaper")
        push.start()
        self.addCleanup(push.stop)


class Trashing(Setup):
    def test_says_so_when_the_wastebasket_took_it(self):
        path = photograph("20260905-bing-a.png")
        self.assertEqual(library.trash(path), library.TRASHED)
        self.assertFalse(path.exists())

    def test_says_so_when_the_wastebasket_refused_and_it_was_unlinked(self):
        self.wastebasket.refuses = True
        path = photograph("20260905-bing-a.png")
        self.assertEqual(library.trash(path), library.UNLINKED)
        self.assertFalse(path.exists())

    def test_says_so_when_there_is_no_gio_at_all(self):
        path = photograph("20260905-bing-a.png")
        with mock.patch.object(library.subprocess, "run",
                               side_effect=FileNotFoundError):
            self.assertEqual(library.trash(path), library.UNLINKED)
        self.assertFalse(path.exists())

    def test_fails_when_nothing_could_remove_it(self):
        self.wastebasket.refuses = True
        path = photograph("20260905-bing-a.png")
        with mock.patch.object(Path, "unlink", side_effect=PermissionError), \
                self.assertRaises(OSError):
            library.trash(path)


class ParseTrash(unittest.TestCase):
    # As `gio list -u -a trash::orig-path,trash::deletion-date trash:///`
    # printed it, tabs and all.
    LINE = ("trash:///a%20b.jpg\t2\t(regular)\t"
            "trash::orig-path=/srv/photos/a b.jpg "
            "trash::deletion-date=2026-10-18T01:19:06")

    def test_reads_where_an_entry_came_from_and_when(self):
        self.assertEqual(
            library.parse_trash(self.LINE + "\n"),
            [library.Trashed("trash:///a%20b.jpg",
                             Path("/srv/photos/a b.jpg"),
                             "2026-10-18T01:19:06")],
        )

    def test_skips_a_line_that_does_not_say(self):
        self.assertEqual(
            library.parse_trash("trash:///x\t2\t(regular)\t\n"), [])


class CacheOwner(unittest.TestCase):
    def test_a_thumbnail_belongs_to_the_photograph_it_was_cut_from(self):
        self.assertEqual(
            library.cache_owner("20260905-bing-a.jpg-312x176.png"),
            "20260905-bing-a.jpg")
        self.assertEqual(library.cache_owner("Holiday.JPG-96x54.png"),
                         "Holiday.JPG")

    def test_a_remote_thumbnail_or_a_temp_file_belongs_to_none(self):
        for name in ("remote-0123456789abcdef-312x176.png",
                     ".a.jpg-312x176.new", "a.jpg-312x176.png.new",
                     "notes.txt"):
            with self.subTest(name=name):
                self.assertIsNone(library.cache_owner(name))


class Prune(Setup):
    def test_a_line_outlives_the_file_while_the_trash_holds_it(self):
        photograph("20260905-bing-a.png", title="A")
        gone = photograph("20260906-bing-b.png", title="B")
        library.trash(gone)
        library.prune()
        self.assertEqual(ledger_names(),
                         ["20260905-bing-a.png", "20260906-bing-b.png"])

    def test_a_line_goes_once_the_trash_no_longer_holds_it_either(self):
        photograph("20260905-bing-a.png", title="A")
        gone = photograph("20260906-bing-b.png", title="B")
        library.trash(gone)
        self.wastebasket.held.clear()        # Trash emptied
        library.prune()
        self.assertEqual(ledger_names(), ["20260905-bing-a.png"])

    def test_a_file_removed_outside_wallhelper_is_dropped(self):
        photograph("20260905-bing-a.png", title="A")
        photograph("20260906-bing-b.png", title="B").unlink()
        library.prune()
        self.assertEqual(ledger_names(), ["20260905-bing-a.png"])

    def test_thumbnails_follow_the_photograph(self):
        photograph("20260905-bing-a.png")
        thumbnail_for("20260905-bing-a.png")
        thumbnail_for("20260905-bing-a.png", "96x54")
        trashed = photograph("20260906-bing-b.png")
        thumbnail_for("20260906-bing-b.png")
        library.trash(trashed)
        removed = photograph("20260907-bing-c.png")
        mine = [thumbnail_for("20260907-bing-c.png"),
                thumbnail_for("20260907-bing-c.png", "96x54")]
        remote = THUMBS / "remote-0123456789abcdef-312x176.png"
        remote.write_bytes(png(4, 4))
        removed.unlink()
        library.prune()
        self.assertEqual(
            sorted(path.name for path in THUMBS.iterdir()),
            ["20260905-bing-a.png-312x176.png",
             "20260905-bing-a.png-96x54.png",
             "20260906-bing-b.png-312x176.png",
             remote.name])
        self.assertFalse(any(path.exists() for path in mine))

    def test_nothing_goes_when_the_trash_cannot_be_read(self):
        photograph("20260905-bing-a.png", title="A")
        photograph("20260906-bing-b.png", title="B").unlink()
        thumbnail_for("20260906-bing-b.png")
        with mock.patch.object(library, "in_trash", side_effect=OSError):
            library.prune()
        self.assertEqual(ledger_names(),
                         ["20260905-bing-a.png", "20260906-bing-b.png"])
        self.assertTrue((THUMBS / "20260906-bing-b.png-312x176.png").exists())

    def test_nothing_goes_when_the_folder_looks_empty(self):
        # An unmounted drive looks like this, and a caption is not coming
        # back.
        photograph("20260905-bing-a.png", title="A").unlink()
        library.prune()
        self.assertEqual(ledger_names(), ["20260905-bing-a.png"])


class Deleting(Setup):
    def photos(self):
        return [photograph(f"2026091{n}-bing-{n}.png", title=f"T{n}")
                for n in (1, 2, 3)]

    def test_a_trashed_photo_keeps_its_caption_and_thumbnail(self):
        _one, two, _three = self.photos()
        cached = thumbnail_for(two.name)
        gone = library.delete_photo(two)
        self.assertEqual(gone.how, library.TRASHED)
        self.assertEqual(gone.title, "T2")
        self.assertIn(two.name, ledger_names())
        self.assertTrue(cached.exists())

    def test_one_the_trash_refused_takes_both_with_it(self):
        self.wastebasket.refuses = True
        _one, two, _three = self.photos()
        cached = thumbnail_for(two.name)
        gone = library.delete_photo(two)
        self.assertEqual(gone.how, library.UNLINKED)
        self.assertNotIn(two.name, ledger_names())
        self.assertFalse(cached.exists())

    def test_the_wall_moves_to_the_neighbour_along_the_grid(self):
        one, two, three = self.photos()
        library.delete_photo(two)              # newest first: 3, 2, 1
        self.assertEqual(CURRENT.resolve(), one.resolve())
        library.delete_photo(one)
        self.assertEqual(CURRENT.resolve(), three.resolve())

    def test_a_photograph_outside_the_collection_is_left_alone(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        path = Path(outside.name) / "original.png"
        path.write_bytes(png(4, 4))
        with self.assertRaises(ValueError):
            library.delete_photo(path)
        self.assertTrue(path.exists())
        self.assertEqual(self.wastebasket.held, [])


class Toast(unittest.TestCase):
    """The window says Trash only when the Trash has it."""

    def delete(self, how):
        win = mock.Mock()
        win.current = DIR / "20260905-bing-a.png"
        gone = library.Deleted(win.current, "Beach huts", how)
        with mock.patch.object(window, "delete_photo", return_value=gone):
            window.Window.on_delete(win)
        return win.toast.call_args.args[0]

    def test_trashed(self):
        self.assertIn("Trash", self.delete(library.TRASHED))
        self.assertNotIn("refused", self.delete(library.TRASHED))

    def test_unlinked(self):
        said = self.delete(library.UNLINKED)
        self.assertNotIn("moved to Trash", said)
        self.assertIn("for good", said)
