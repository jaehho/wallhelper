"""The Elsewhere full grid is built when it is opened, not when the row is.

`_show` paints the 8-tile row as sources answer. The expanded grid is
filled from the same candidates only once MORE (or E) is pressed, so a
window open for seconds does not decode tiles nobody asked to see. No
display is opened: the methods only read bar state and call tile(), so a
stand-in for the widget tree will do.
"""

import unittest
from unittest import mock

from tests import guard
from wallhelper.gui import elsewhere
from wallhelper.gui.elsewhere import (
    GRID_H,
    GRID_W,
    ROW_LIMIT,
    THUMB_H,
    THUMB_W,
)


def setUpModule():
    guard()


def candidate(i: int) -> dict:
    return {"name": "apod", "image": f"https://example/{i}.jpg",
            "title": f"Photo {i}"}


class Box:
    """Just enough of a Gtk.Box to hold children in a list."""

    def __init__(self):
        self.children = []
        self.visible = True

    def get_first_child(self):
        return self.children[0] if self.children else None

    def remove(self, child):
        self.children.remove(child)

    def append(self, child):
        self.children.append(child)

    def set_visible(self, shown):
        self.visible = shown


class StandIn:
    """ElsewhereBar with its widget tree swapped for lists, so _show and
    _fill_full can run without a display. tile() records what it was
    asked to build and returns a stub, which is the point of the test."""

    def __init__(self, n=ROW_LIMIT + 4):
        self.answers = {0: ("apod", elsewhere.Listing(
            [candidate(i) for i in range(n)], ""))}
        self.cands = []
        self.row = Box()
        self.full = Box()
        self.notes = Box()
        self.full_scroller = Box()
        self.more_btn = mock.Mock()
        self.expanded = False
        self.tiles = {}
        self.marks = []
        self.built = []

    def tile(self, cand, wide, high):
        self.built.append((cand["image"], wide, high))
        return mock.Mock(name=cand["image"])

    def _fill_full(self):
        elsewhere.ElsewhereBar._fill_full(self)


class FullGrid(unittest.TestCase):
    def bar(self, n=ROW_LIMIT + 4):
        return StandIn(n)

    def test_show_builds_only_the_row(self):
        bar = self.bar()
        elsewhere.ElsewhereBar._show(bar)
        self.assertEqual(len(bar.row.children), ROW_LIMIT)
        self.assertEqual(bar.full.children, [])
        self.assertEqual(bar.built,
                         [(candidate(i)["image"], THUMB_W, THUMB_H)
                          for i in range(ROW_LIMIT)])

    def test_expanding_builds_the_full_grid(self):
        bar = self.bar()
        elsewhere.ElsewhereBar._show(bar)
        bar.built.clear()
        bar.expanded = True
        elsewhere.ElsewhereBar._fill_full(bar)
        self.assertEqual(len(bar.full.children), ROW_LIMIT + 4)
        self.assertEqual(bar.built,
                         [(candidate(i)["image"], GRID_W, GRID_H)
                          for i in range(ROW_LIMIT + 4)])

    def test_toggle_fills_the_grid_the_first_time_it_is_opened(self):
        bar = self.bar()
        elsewhere.ElsewhereBar._show(bar)
        bar.built.clear()
        bar.expanded = False
        elsewhere.ElsewhereBar.toggle(bar)
        self.assertTrue(bar.expanded)
        self.assertEqual(len(bar.full.children), ROW_LIMIT + 4)

    def test_a_second_show_while_open_refills_the_grid(self):
        # A source answering late must still reach the expanded grid.
        bar = self.bar()
        bar.expanded = True
        elsewhere.ElsewhereBar._show(bar)
        self.assertEqual(len(bar.full.children), ROW_LIMIT + 4)
        self.assertEqual(len(bar.row.children), ROW_LIMIT)

    def test_tiles_are_cached_across_a_collapse(self):
        bar = self.bar()
        # Use the real tile() so its per-(source, url, size) cache is
        # what is being checked, not the stub's memory.
        created = []
        bar.tile = lambda cand, wide, high: elsewhere.ElsewhereBar.tile(
            bar, cand, wide, high)
        bar._new_tile = lambda cand, wide, high: (
            created.append((cand["image"], wide, high))
            or mock.Mock(name=cand["image"]))
        elsewhere.ElsewhereBar._show(bar)
        bar.expanded = True
        elsewhere.ElsewhereBar._fill_full(bar)
        first = len(created)
        bar.full.children.clear()
        elsewhere.ElsewhereBar._fill_full(bar)
        # Nothing new decoded: the rebuild got the cached widgets back.
        self.assertEqual(len(created), first)
        self.assertEqual(len(bar.full.children), ROW_LIMIT + 4)

    def test_the_row_never_offers_more_than_the_limit(self):
        bar = self.bar(n=3)
        elsewhere.ElsewhereBar._show(bar)
        self.assertEqual(len(bar.row.children), 3)
        bar.more_btn.set_visible.assert_called_with(False)
