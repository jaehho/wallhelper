"""The morning fetch: once a day, from the morning sources only, and it
says what came of it.

Bing's reply is canned and the downloads are stood in for. These pin the
decisions made around the network -- when a run asks, what an answer
means, what is left behind for the panel -- not whether Bing is up.
"""

import argparse
import contextlib
import io
import json
import time
import unittest
import urllib.error
from unittest import mock

from tests import guard
from tests.test_library import png
from tests.test_sources import save
from wallhelper import cli, morning, sources
from wallhelper.library import images
from wallhelper.morning import FAILED, HELD, SAVED, TODAY, UNSET, Outcome
from wallhelper.paths import CREDITS, DIR, LAST_FETCH


def setUpModule():
    guard()


def day(ago: int = 0) -> str:
    return time.strftime("%Y%m%d", time.localtime(time.time() - ago * 86400))


def bing(startdate: str) -> bytes:
    """What the public API serves, trimmed to the fields the shipped
    source reads."""
    return json.dumps({"images": [{
        "startdate": startdate, "urlbase": "/th?id=OHR.Trail",
        "title": "Follow the trail", "copyright": "A trail (© Someone)",
        "copyrightlink": "https://www.bing.com/search?q=trail",
    }]}).encode()


class Morning(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        for path in DIR.glob("*.*"):
            path.unlink()
        CREDITS.unlink(missing_ok=True)
        LAST_FETCH.unlink(missing_ok=True)
        self.reply = bing(day())
        self.ask = mock.patch.object(
            sources, "fetch_url",
            side_effect=lambda *_a, **_k: self.reply).start()
        self.download = mock.patch.object(
            sources, "download", side_effect=save).start()
        self.wall = mock.patch.object(morning, "set_wallpaper").start()
        self.addCleanup(mock.patch.stopall)

    def photos(self):
        return sorted(path.name for path in images(DIR))


class Guard(Morning):
    def test_a_pick_from_elsewhere_dated_today_does_not_close_the_day(self):
        (DIR / f"{day()}-wikipedia-Somewhere.png").write_bytes(png(4, 4))
        run = morning.fetch_morning()
        self.assertEqual(run.kind, SAVED)
        self.assertEqual(self.photos(), [
            f"{day()}-bing-Follow-the-trail.jpg",
            f"{day()}-wikipedia-Somewhere.png"])
        self.ask.assert_called_once()

    def test_a_second_run_the_same_day_asks_nobody(self):
        first = morning.fetch_morning()
        second = morning.fetch_morning()
        self.assertEqual((first.kind, second.kind), (SAVED, TODAY))
        self.assertEqual(second.photo, first.photo)
        self.ask.assert_called_once()
        self.download.assert_called_once()

    def test_a_second_run_leaves_the_record_of_the_first(self):
        morning.fetch_morning()
        before = LAST_FETCH.read_text()
        morning.fetch_morning()
        self.assertEqual(LAST_FETCH.read_text(), before)

    def test_a_photograph_deleted_since_is_fetched_again(self):
        first = morning.fetch_morning()
        first.photo.unlink()
        self.assertEqual(morning.fetch_morning().kind, SAVED)
        self.assertEqual(self.download.call_count, 2)

    def test_the_rollover_brings_the_new_day_after_the_old_one(self):
        # Bing still serving yesterday's at one in the morning, and today's
        # by nine: the first run's photograph is not "today's".
        self.reply = bing(day(1))
        early = morning.fetch_morning()
        self.reply = bing(day())
        later = morning.fetch_morning()
        self.assertEqual((early.kind, later.kind), (SAVED, SAVED))
        self.assertEqual(len(self.photos()), 2)

    def test_a_source_no_longer_in_the_morning_list_closes_nothing(self):
        photo = DIR / f"{day()}-apod-Stars.jpg"
        photo.write_bytes(png(4, 4))
        morning.record(Outcome(SAVED, "apod", "apod", photo))
        self.assertIsNone(morning.todays(["bing"]))
        self.assertIsNotNone(morning.todays(["apod"]))


class Rollover(Morning):
    def test_a_photograph_the_source_serves_again_is_not_a_failure(self):
        # The file is named for Bing's startdate, not for the local day, so
        # the second run cannot tell from the folder alone.
        self.reply = bing(day(1))
        first = morning.fetch_morning()
        second = morning.fetch_morning()
        self.assertEqual((first.kind, second.kind), (SAVED, HELD))
        self.assertTrue(second.ok)
        self.assertEqual(second.photo, first.photo)
        self.assertEqual(len(self.photos()), 1)
        self.download.assert_called_once()

    def test_a_held_photograph_does_not_take_over_the_wall(self):
        self.reply = bing(day(1))
        morning.fetch_morning()
        self.wall.reset_mock()
        morning.fetch_morning()
        self.wall.assert_not_called()

    def test_a_held_photograph_is_recorded_as_such(self):
        self.reply = bing(day(1))
        morning.fetch_morning()
        morning.fetch_morning()
        last = morning.last_run()
        self.assertEqual((last.kind, last.source), (HELD, "bing"))


class Record(Morning):
    def test_a_saved_photograph_is_recorded(self):
        run = morning.fetch_morning()
        last = morning.last_run()
        self.assertEqual((last.kind, last.source, last.photo),
                         (SAVED, "bing", run.photo))
        self.assertEqual(last.when[:10], time.strftime("%Y-%m-%d"))

    def test_a_failure_is_recorded_with_the_source_and_its_words(self):
        self.ask.side_effect = urllib.error.URLError("Unauthorized")
        run = morning.fetch_morning()
        self.assertEqual((run.kind, run.ok), (FAILED, False))
        last = morning.last_run()
        self.assertEqual((last.kind, last.source), (FAILED, "bing"))
        self.assertEqual(last.message, "bing — Unauthorized")
        self.assertIsNone(last.photo)

    def test_the_next_success_replaces_the_failure(self):
        self.ask.side_effect = urllib.error.URLError("no route")
        morning.fetch_morning()
        self.ask.side_effect = lambda *_a, **_k: self.reply
        morning.fetch_morning()
        self.assertEqual(morning.last_run().kind, SAVED)

    def test_a_morning_with_no_source_is_recorded(self):
        with mock.patch.object(morning, "autofetch_sources",
                               return_value=[]):
            run = morning.fetch_morning()
        self.assertEqual(run.kind, UNSET)
        self.assertEqual(morning.last_run().kind, UNSET)
        self.ask.assert_not_called()

    def test_a_state_directory_that_cannot_be_written_fails_nothing(self):
        # Its parent is a file, so neither reading nor writing can work.
        blocker = DIR / "blocked.txt"
        blocker.write_text("")
        with mock.patch.object(morning, "LAST_FETCH",
                               blocker / "last-fetch.json"):
            run = morning.fetch_morning()
        self.assertEqual(run.kind, SAVED)

    def test_a_record_that_cannot_be_believed_is_no_record(self):
        good = {"when": "2026-10-18T01:00:00", "kind": SAVED,
                "source": "bing", "message": "bing", "photo": ""}
        LAST_FETCH.parent.mkdir(parents=True, exist_ok=True)
        for text in ("", "not json", "[]", json.dumps({**good, "kind": "?"}),
                     json.dumps({**good, "when": ""}),
                     json.dumps({**good, "source": 3})):
            LAST_FETCH.write_text(text)
            self.assertIsNone(morning.last_run(), text)
        LAST_FETCH.write_text(json.dumps(good))
        self.assertIsNotNone(morning.last_run())
        LAST_FETCH.unlink()
        self.assertIsNone(morning.last_run())


class Command(Morning):
    def run_fetch(self, wait=False):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            code = cli.cmd_fetch(argparse.Namespace(wait=wait))
        return code, err.getvalue()

    def setUp(self):
        super().setUp()
        self.notify = mock.patch.object(cli, "notify").start()
        self.sleep = mock.patch.object(cli.time, "sleep").start()

    def test_a_photograph_already_held_exits_clean(self):
        self.reply = bing(day(1))
        self.assertEqual(self.run_fetch()[0], 0)
        self.assertEqual(self.run_fetch()[0], 0)

    def test_a_failure_says_which_source_and_exits_non_zero(self):
        (DIR / "20260901-bing-old.jpg").write_bytes(png(4, 4))
        self.ask.side_effect = urllib.error.URLError("Unauthorized")
        code, said = self.run_fetch()
        self.assertEqual(code, 1)
        self.assertIn("bing — Unauthorized", said)
        # Something is still on the wall, so this is not worth a toast.
        self.notify.assert_not_called()

    def test_an_empty_collection_is_what_escalates(self):
        self.ask.side_effect = urllib.error.URLError("no route")
        self.assertEqual(self.run_fetch()[0], 1)
        self.notify.assert_called_once()
        self.assertTrue(self.notify.call_args.kwargs["urgent"])

    def test_the_timer_waits_for_a_source_that_does_not_answer(self):
        answers = [Outcome(FAILED, "bing", "bing — no route"),
                   Outcome(FAILED, "bing", "bing — no route"),
                   Outcome(SAVED, "bing", "bing -> x.jpg")]
        with mock.patch.object(cli, "fetch_morning", side_effect=answers):
            code, _ = self.run_fetch(wait=True)
        self.assertEqual(code, 0)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list],
                         [30, 60])

    def test_the_timer_does_not_wait_for_what_waiting_cannot_change(self):
        for kind in (HELD, TODAY, UNSET):
            with self.subTest(kind=kind), mock.patch.object(
                    cli, "fetch_morning",
                    return_value=Outcome(kind, "bing", "")):
                self.run_fetch(wait=True)
        self.sleep.assert_not_called()

    def test_without_the_timers_wait_a_failure_is_not_retried(self):
        self.ask.side_effect = urllib.error.URLError("no route")
        self.run_fetch()
        self.sleep.assert_not_called()
        self.ask.assert_called_once()
