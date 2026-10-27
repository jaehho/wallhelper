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
        with mock.patch.object(style, "WAYBAR_COLORS", path):
            return style.palette()

    def test_a_missing_mocha_still_gives_a_full_one(self):
        # The window has to open on a machine that has no waybar theme.
        found = self.read(None)
        for key in ("crust", "base", "text", "overlay0", "overlay2",
                    "blue", "maroon"):
            self.assertRegex(found[key], r"^#[0-9a-fA-F]{6}$", key)

    def test_the_fallback_is_catppuccin_mocha(self):
        found = self.read(None)
        self.assertEqual(found["crust"], "#11111b")
        self.assertEqual(found["blue"], "#b4befe")

    def test_waybar_wins_where_it_speaks(self):
        text = "@define-color crust #222222;\n@define-color lavender #abcdef;\n"
        found = self.read(text)
        self.assertEqual(found["crust"], "#222222")
        # The stylesheet's "blue" is Mocha's lavender.
        self.assertEqual(found["blue"], "#abcdef")
        # A role waybar does not name keeps the fallback.
        self.assertEqual(found["maroon"], style.MOCHA["maroon"])

    def test_comments_and_blanks_are_skipped(self):
        found = self.read("# a comment\n\n@define-color lavender #aabbcc\n")
        self.assertEqual(found["blue"], "#aabbcc")

    def test_a_define_without_a_hex_is_not_a_colour(self):
        found = self.read("@define-color lavender url(foo);\n")
        self.assertEqual(found["blue"], style.MOCHA["blue"])


class Stylesheet(unittest.TestCase):
    def test_every_colour_the_stylesheet_asks_for_exists(self):
        # The stylesheet is one long f-string over the palette dict. A colour
        # name palette() does not define raises KeyError here, rather than at
        # the moment the window would have opened.
        css = style.stylesheet(style.palette())
        self.assertIn("window.wallhelper", css)
        self.assertNotIn("{C[", css)
