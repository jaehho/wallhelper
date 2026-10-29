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

    def test_a_missing_waybar_theme_still_gives_a_full_one(self):
        # The window has to open on a machine that has no waybar theme.
        found = self.read(None)
        for key in style.EVERFOREST:
            self.assertRegex(found[key], r"^#[0-9a-fA-F]{6}$", key)

    def test_the_fallback_is_everforest(self):
        found = self.read(None)
        self.assertEqual(found["bg_dim"], "#232a2e")
        self.assertEqual(found["green"], "#a7c080")

    def test_waybar_wins_where_it_speaks(self):
        text = "@define-color bg_dim #222222;\n@define-color green #abcdef;\n"
        found = self.read(text)
        self.assertEqual(found["bg_dim"], "#222222")
        self.assertEqual(found["green"], "#abcdef")
        # A name waybar does not define keeps the fallback.
        self.assertEqual(found["red"], style.EVERFOREST["red"])

    def test_comments_and_blanks_are_skipped(self):
        found = self.read("# a comment\n\n@define-color green #aabbcc\n")
        self.assertEqual(found["green"], "#aabbcc")

    def test_a_define_without_a_hex_is_not_a_colour(self):
        found = self.read("@define-color green url(foo);\n")
        self.assertEqual(found["green"], style.EVERFOREST["green"])


class Stylesheet(unittest.TestCase):
    def test_every_colour_the_stylesheet_asks_for_exists(self):
        # The stylesheet is one long f-string over the palette dict. A colour
        # name palette() does not define raises KeyError here, rather than at
        # the moment the window would have opened.
        css = style.stylesheet(style.palette())
        self.assertIn("window.wallhelper", css)
        self.assertNotIn("{C[", css)
