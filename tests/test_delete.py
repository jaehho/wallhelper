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
    """`gio trash`, `gio trash --restore` and `gio list`, with a folder
    for the Trash. A second file of the same name is stored as name.2.ext,
    as gio does."""

    def __init__(self, folder, refuses=False):
        self.folder = folder
        self.refuses = refuses
        self.held = []          # (name in the bin, where it came from, when)
        self.clock = 0
        self.calls = []

    def __call__(self, argv, **_kwargs):
        self.calls.append(argv[1:3] if argv[1] == "list" else argv[1:4])
        if argv[:3] == ["gio", "trash", "--restore"]:
            return self.restore(argv[3], argv)
        if argv[:2] == ["gio", "trash"]:
            return self.trash(Path(argv[2]), argv)
        if argv[:2] == ["gio", "list"]:
            lines = [
                f"trash:///{urllib.parse.quote(name)}\t3\t(regular)\t"
                f"trash::orig-path={was} trash::deletion-date={when}"
                for name, was, when in self.held
            ]
            return subprocess.CompletedProcess(
                argv, 0, "".join(line + "\n" for line in lines), "")
        msg = f"unexpected call: {argv}"
        raise AssertionError(msg)

    def trash(self, path, argv):
        if self.refuses:
            return subprocess.CompletedProcess(argv, 1, "", "no trash")
        name, number = path.name, 1
        while (self.folder / name).exists():
            number += 1
            name = f"{path.stem}.{number}{path.suffix}"
        shutil.move(path, self.folder / name)
        self.clock += 1
        self.held.append((name, path, f"2026-10-18T01:19:{self.clock:02d}"))
        return subprocess.CompletedProcess(argv, 0, "", "")

    def restore(self, uri, argv):
        name = urllib.parse.unquote(uri.removeprefix("trash:///"))
        for entry in self.held:
            if entry[0] == name:
                _name, was, _when = entry
                if was.exists():
                    return subprocess.CompletedProcess(
                        argv, 1, "", "File exists")
                shutil.move(self.folder / name, was)
                self.held.remove(entry)
                return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 1, "", "not in the Trash")


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


class Restoring(Setup):
    def test_a_deleted_photograph_comes_back_captioned(self):
        path = photograph("20260905-bing-a.png", title="Beach huts")
        library.delete_photo(path)
        self.assertFalse(path.exists())
        library.restore(path)
        self.assertTrue(path.is_file())
        self.assertEqual(library.label(path)["title"], "Beach huts")
        self.assertEqual(self.wastebasket.held, [])

    def test_the_latest_of_two_with_one_name_comes_back(self):
        path = photograph("20260905-bing-a.png")
        library.trash(path)
        path.write_bytes(png(8, 8))             # fetched again, same name
        library.trash(path)
        library.restore(path)
        self.assertEqual(library.measure(path), (8, 8))
        self.assertEqual(len(self.wastebasket.held), 1)

    def test_lists_the_trash_again_afterwards(self):
        # gvfs's view of the Trash goes stale for a restored name until
        # something lists it; see restore().
        path = photograph("20260905-bing-a.png")
        library.trash(path)
        self.wastebasket.calls.clear()
        library.restore(path)
        self.assertEqual([call[0] for call in self.wastebasket.calls],
                         ["list", "trash", "list"])

    def test_fails_when_the_trash_does_not_have_it(self):
        with self.assertRaises(OSError):
            library.restore(DIR / "20260905-bing-gone.png")

    def test_fails_when_gio_will_not_give_it_up(self):
        path = photograph("20260905-bing-a.png")
        library.trash(path)
        photograph("20260905-bing-a.png")        # the name is taken again
        with self.assertRaises(OSError):
            library.restore(path)


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

    def test_thumbnails_stay_when_the_folder_looks_empty(self):
        # An unmounted drive looks like this, and the cache would be
        # decoded all over again.
        photograph("20260905-bing-a.png").unlink()
        thumbnail_for("20260905-bing-a.png")
        library.prune()
        self.assertEqual(len(list(THUMBS.iterdir())), 1)

    def test_a_photograph_deleted_while_pruning_is_not_taken_for_gone(self):
        # prune lists the folder, then asks the Trash. A delete landing
        # between the two is missing from the Trash's answer, which was
        # given before it, and must not be missing from the folder's.
        photograph("20260905-bing-a.png", title="A")
        racing = photograph("20260906-bing-b.png", title="B")
        thumbnail_for(racing.name)

        def listing_before_the_delete():
            racing.unlink()
            return []

        with mock.patch.object(library, "in_trash",
                               side_effect=listing_before_the_delete):
            library.prune()
        self.assertEqual(ledger_names(),
                         ["20260905-bing-a.png", "20260906-bing-b.png"])
        self.assertTrue((THUMBS / f"{racing.name}-312x176.png").exists())


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

    def test_one_the_trash_refused_loses_both_at_the_next_prune(self):
        self.wastebasket.refuses = True
        _one, two, _three = self.photos()
        cached = thumbnail_for(two.name)
        gone = library.delete_photo(two)
        self.assertEqual(gone.how, library.UNLINKED)
        library.prune()
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
    """The window offers UNDO only for what the Trash has."""

    def delete(self, how):
        win = mock.Mock()
        win.current = DIR / "20260905-bing-a.png"
        gone = library.Deleted(win.current, "Beach huts", how)
        with mock.patch.object(window, "delete_photo", return_value=gone):
            window.Window.on_delete(win)
        return win, gone

    def test_trashed_offers_undo(self):
        win, gone = self.delete(library.TRASHED)
        win.offer_undo.assert_called_once_with(gone)
        win.toast.assert_not_called()

    def test_unlinked_has_nothing_to_undo_and_says_so(self):
        win, _gone = self.delete(library.UNLINKED)
        win.offer_undo.assert_not_called()
        self.assertNotIn("moved to Trash", win.toast.call_args.args[0])


class Undo(unittest.TestCase):
    def stand_in(self):
        win = mock.Mock()
        gone = library.Deleted(DIR / "20260905-bing-a.png", "Beach huts",
                               library.TRASHED)
        win.undoable = (mock.Mock(), gone)
        return win, gone

    def undo(self, win, **patches):
        with mock.patch.object(window, "restore", **patches) as restore:
            window.Window.on_undo(win)
        return restore

    def test_puts_the_photograph_back_on_the_wall(self):
        win, gone = self.stand_in()
        restore = self.undo(win)
        restore.assert_called_once_with(gone.path)
        win.on_pick.assert_called_once_with(None, gone.path)
        win.withdraw_undo.assert_called_once_with()

    def test_says_so_when_it_could_not(self):
        win, _gone = self.stand_in()
        self.undo(win, side_effect=OSError("File exists"))
        win.on_pick.assert_not_called()
        self.assertIn("still in the Trash", win.toast.call_args.args[0])

    def test_has_nothing_to_do_once_the_offer_has_lapsed(self):
        win, _gone = self.stand_in()
        win.undoable = None
        restore = self.undo(win)
        restore.assert_not_called()
        win.on_pick.assert_not_called()
