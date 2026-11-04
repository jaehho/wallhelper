"""The strip's rules that hold without a display: which word a tile
wears, how the wall keeps up with a held arrow, and when opening the
window goes and gets the morning's photograph (#24)."""

import unittest
from pathlib import Path
from unittest import mock

from tests import guard
from wallhelper import morning
from wallhelper.gui import plate, strip, window


def setUpModule():
    guard()


class Marks(unittest.TestCase):
    TODAY = "20261104-"

    def mark(self, name, *, before="", selected=""):
        return strip.mark_for(name, today=self.TODAY, before=before,
                              selected=selected)

    def test_the_mornings_photograph_says_today(self):
        self.assertEqual(self.mark("20261104-bing-a.jpg"), "TODAY")
        self.assertEqual(self.mark("20261103-bing-b.jpg"), "")

    def test_the_way_back_shows_once_the_selection_leaves_it(self):
        name = "20261101-bing-c.jpg"
        self.assertEqual(self.mark(name, before=name, selected=name), "")
        self.assertEqual(
            self.mark(name, before=name, selected="20261102-bing-d.jpg"),
            "BEFORE")

    def test_before_wins_over_today(self):
        # Opened on today's, then moved off it: the word that matters is
        # the way back.
        name = "20261104-bing-a.jpg"
        self.assertEqual(self.mark(name, before=name, selected="x"),
                         "BEFORE")


class MorningPlace(unittest.TestCase):
    def test_arriving_and_failed_say_different_things(self):
        self.assertEqual(strip.status_text(strip.Item(status=strip.ARRIVING)),
                         ("TODAY", "On its way"))
        failed = strip.Item(status=strip.FAILED,
                            message="bing \u2014 Unauthorized")
        self.assertEqual(strip.status_text(failed),
                         ("TODAY", "bing \u2014 Unauthorized"))

    def test_a_failure_with_no_reason_still_says_something(self):
        self.assertEqual(
            strip.status_text(strip.Item(status=strip.FAILED)),
            ("TODAY", "Did not come"))

    def test_only_a_photograph_has_a_file_name(self):
        self.assertEqual(strip.Item(Path("/p/a.jpg")).name, "a.jpg")
        self.assertEqual(strip.Item(status=strip.FAILED).name, ":failed")


class Due(unittest.TestCase):
    def test_opening_fetches_only_when_no_run_kept_one_today(self):
        kept = morning.Outcome(morning.TODAY, "bing", "", Path("/p/a.jpg"))
        self.assertTrue(window.morning_due(["bing"], None))
        self.assertFalse(window.morning_due(["bing"], kept))
        self.assertFalse(window.morning_due([], None))


class Pusher(unittest.TestCase):
    """A held arrow must not queue one hyprpaper push per tile."""

    def setUp(self):
        self.pushed: list[str] = []
        self.running: list = []      # pushes started and not yet landed
        self.landing: list = []      # (callback, image) waiting for idle
        self.wall = window.WallPusher(
            self.pushed.append, start=self.running.append,
            finish=lambda callback, image: self.landing.append(
                (callback, image)))

    def land_one(self):
        self.running.pop(0)()            # the push runs, off the main loop
        callback, image = self.landing.pop(0)
        callback(image)                  # and lands back on it

    def test_the_first_goes_at_once(self):
        self.wall.push("a")
        self.land_one()
        self.assertEqual(self.pushed, ["a"])

    def test_a_held_arrow_pushes_the_first_and_the_last(self):
        for name in "abcdef":
            self.wall.push(name)
        self.assertEqual(len(self.running), 1)
        self.land_one()
        self.land_one()
        self.assertEqual(self.pushed, ["a", "f"])
        self.assertEqual(self.running, [])

    def test_back_where_it_was_needs_no_second_push(self):
        self.wall.push("a")
        self.wall.push("b")
        self.wall.push("a")
        self.land_one()
        self.assertEqual(self.pushed, ["a"])
        self.assertEqual(self.running, [])

    def test_a_push_that_fails_still_lands(self):
        def broken(_image):
            msg = "hyprctl went away"
            raise OSError(msg)

        wall = window.WallPusher(broken, start=lambda work: work(),
                                 finish=lambda callback, image:
                                 callback(image))
        with self.assertRaises(OSError):
            wall.push("a")
        self.assertFalse(wall.busy)


class Caption(unittest.TestCase):
    def test_a_photograph_nobody_described_says_nothing(self):
        self.assertEqual(plate.facts_line({}, ""), ("", "", ""))

    def test_each_fact_is_tracked(self):
        info = {"place": "Beach huts, Southwold", "author": "Steven"}
        self.assertEqual(plate.facts_line(info, "3840 \u00d7 2160"),
                         ("BEACH HUTS, SOUTHWOLD", "3840 \u00d7 2160",
                          "\u00a9 STEVEN"))


class Opening(unittest.TestCase):
    """What opening the window does about the morning's photograph."""

    def stand_in(self):
        win = mock.Mock()
        win.fetching = False
        return win

    def check(self, win, *, usable=("bing",), kept=None, again=False):
        with mock.patch.object(window, "autofetch_sources",
                               return_value=list(usable)), \
             mock.patch.object(window, "todays", return_value=kept), \
             mock.patch.object(window, "_in_thread") as thread, \
             mock.patch.object(window.GLib, "timeout_add") as later:
            window.Window.check_morning(win, again=again)
        return thread, later

    def test_a_morning_with_its_photograph_asks_nobody(self):
        kept = morning.Outcome(morning.TODAY, "bing", "", Path("/p/a.jpg"))
        thread, _later = self.check(self.stand_in(), kept=kept)
        thread.assert_not_called()

    def test_a_morning_without_one_fetches_and_waits_to_say_so(self):
        win = self.stand_in()
        thread, later = self.check(win)
        thread.assert_called_once()
        self.assertTrue(win.fetching)
        self.assertEqual(later.call_args.args[0], window.ARRIVING_AFTER_MS)

    def test_trying_again_says_so_at_once(self):
        kept = morning.Outcome(morning.TODAY, "bing", "", Path("/p/a.jpg"))
        thread, later = self.check(self.stand_in(), kept=kept, again=True)
        thread.assert_called_once()
        self.assertEqual(later.call_args.args[0], 0)

    def test_one_fetch_at_a_time(self):
        win = self.stand_in()
        win.fetching = True
        thread, _later = self.check(win)
        thread.assert_not_called()

    def test_a_failure_takes_the_first_place(self):
        win = self.stand_in()
        run = morning.Outcome(morning.FAILED, "bing", "bing \u2014 timed out")
        window.Window._fetched(win, run)
        self.assertEqual(win.status.status, strip.FAILED)
        self.assertEqual(win.status.message, "bing \u2014 timed out")
        win.refresh.assert_called_once_with()

    def test_a_new_photograph_is_selected_and_its_place_goes(self):
        win = self.stand_in()
        photo = Path("/p/20261104-bing-a.jpg")
        window.Window._fetched(
            win, morning.Outcome(morning.SAVED, "bing", "", photo))
        self.assertIsNone(win.status)
        self.assertEqual(win.current, photo)
