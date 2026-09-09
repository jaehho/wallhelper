"""The palette the window borrows, and the stylesheet built from it."""

import unittest
from unittest import mock

from tests import guard
from wallhelper.gui import style


def setUpModule():
    guard()


class Palette(unittest.TestCase):
    def read(self, text=None):
        path = mock.MagicMock()
        if text is None:
            path.read_text.side_effect = OSError
        else:
            path.read_text.return_value = text
        with mock.patch.object(style, "PALETTE", path):
            return style.palette()

    def test_a_missing_palette_still_gives_a_full_one(self):
        # The window has to open on a machine that has no theme file.
        found = self.read(None)
        for key in ("crust", "base", "text", "overlay0", "overlay2",
                    "blue", "maroon"):
            self.assertRegex(found[key], r"^#[0-9a-fA-F]{6}$", key)

    def test_the_desktop_wins(self):
        self.assertEqual(self.read("blue=aabbcc\n")["blue"], "#aabbcc")

    def test_comments_and_blanks_are_skipped(self):
        found = self.read("# a comment\n\nblue=aabbcc\n")
        self.assertEqual(found["blue"], "#aabbcc")

    def test_a_line_with_no_equals_is_not_a_colour(self):
        self.assertNotIn("nonsense", self.read("nonsense\n"))


class Stylesheet(unittest.TestCase):
    def test_every_colour_the_stylesheet_asks_for_exists(self):
        # The stylesheet is one long f-string over the palette dict. A colour
        # name palette() does not define raises KeyError here, rather than at
        # the moment the window would have opened.
        css = style.stylesheet(style.palette())
        self.assertIn("window.wallhelper", css)
        self.assertNotIn("{C[", css)

    def test_a_short_palette_is_an_error_and_not_a_blank_window(self):
        with self.assertRaises(KeyError):
            style.stylesheet({"crust": "#000000"})
