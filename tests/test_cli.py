"""`set` and `delete` act on the collection, and on nothing else.

.current is what hyprpaper reads at boot, and `delete` trashes whatever
is on screen. A text file, or a copy in ~/Downloads, must never get that
far. Nothing here reaches the desktop: the push to hyprpaper, the
notification and the wastebasket are all stood in for.
"""

import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import guard
from tests.test_library import png
from wallhelper import cli, library
from wallhelper.paths import CURRENT, DIR


def setUpModule():
    guard()


def run(command):
    """The command's exit code and what it said on stderr."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(
            io.StringIO()):
        code = command(argparse.Namespace())
    return code, err.getvalue()


class Outside(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        for path in DIR.glob("*"):
            if path.is_file() or path.is_symlink():
                path.unlink()
        self.photo = DIR / "20260905-bing-in.png"
        self.photo.write_bytes(png(4, 4))
        downloads = tempfile.TemporaryDirectory()
        self.addCleanup(downloads.cleanup)
        self.downloads = Path(downloads.name)
        self.push = mock.patch.object(library, "push_wallpaper").start()
        self.notify = mock.patch.object(cli, "notify").start()
        self.addCleanup(mock.patch.stopall)

    def set_image(self, path):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            return cli.cmd_set(argparse.Namespace(image=str(path))), \
                err.getvalue()

    def test_set_takes_a_photo_from_the_collection(self):
        code, _ = self.set_image(self.photo)
        self.assertEqual(code, 0)
        self.assertEqual(CURRENT.resolve(), self.photo.resolve())
        self.push.assert_called_once()

    def test_set_refuses_a_text_file(self):
        notes = self.downloads / "notes.txt"
        notes.write_text("not a photograph")
        code, said = self.set_image(notes)
        self.assertEqual(code, 1)
        self.assertIn("not an image", said)
        self.assertFalse(CURRENT.is_symlink())
        self.push.assert_not_called()

    def test_set_refuses_text_wearing_an_image_suffix(self):
        fake = DIR / "20260906-bing-fake.jpg"
        fake.write_text("not a photograph")
        code, said = self.set_image(fake)
        self.assertEqual(code, 1)
        self.assertIn("not an image", said)
        self.assertFalse(CURRENT.is_symlink())

    def test_set_refuses_an_image_outside_the_collection(self):
        outside = self.downloads / "original.png"
        outside.write_bytes(png(4, 4))
        code, said = self.set_image(outside)
        self.assertEqual(code, 1)
        self.assertIn("outside the collection", said)
        self.assertFalse(CURRENT.is_symlink())
        self.push.assert_not_called()

    def test_delete_leaves_what_is_on_screen_alone_when_it_is_outside(self):
        outside = self.downloads / "original.png"
        outside.write_bytes(png(4, 4))
        with mock.patch.object(cli, "current_image", return_value=outside), \
                mock.patch.object(library.subprocess, "run") as wastebasket:
            code, said = run(cli.cmd_delete)
        self.assertEqual(code, 1)
        self.assertIn("outside the collection", said)
        self.assertTrue(outside.is_file())
        wastebasket.assert_not_called()

    def test_delete_does_not_follow_a_link_out_of_the_collection(self):
        outside = self.downloads / "original.png"
        outside.write_bytes(png(4, 4))
        link = DIR / "20260907-bing-link.png"
        link.symlink_to(outside)
        with mock.patch.object(cli, "current_image", return_value=link), \
                mock.patch.object(library.subprocess, "run") as wastebasket:
            code, _ = run(cli.cmd_delete)
        self.assertEqual(code, 1)
        self.assertTrue(outside.is_file())
        wastebasket.assert_not_called()


class Info(unittest.TestCase):
    """`info` says what there is, and omits what there isn't.

    A photograph with no recorded place should not print 'unknown' in
    its place -- principle 5 is to leave the line out.
    """

    def info(self, **fields):
        filled = {"file": "a.jpg", "title": "", "place": "", "date": "",
                  "source": "bing", "author": "", "url": ""}
        filled.update(fields)
        out = io.StringIO()
        with mock.patch.object(cli, "current_image",
                               return_value=Path("/x/a.jpg")), \
                mock.patch.object(cli, "label", return_value=filled), \
                contextlib.redirect_stdout(out):
            code = cli.cmd_info(argparse.Namespace(notify=False))
        return code, out.getvalue()

    def test_a_field_with_something_in_it_is_printed(self):
        code, said = self.info(title="Follow the trail")
        self.assertEqual(code, 0)
        self.assertIn("title", said)
        self.assertIn("Follow the trail", said)

    def test_an_empty_field_is_omitted_rather_than_unknown(self):
        code, said = self.info()
        self.assertEqual(code, 0)
        self.assertNotIn("unknown", said)
        self.assertNotIn("title:", said)
        self.assertNotIn("place:", said)
        self.assertIn("source:", said)
