"""Asking a source what it has, and taking a photograph from it.

The network is mocked throughout: these pin the resolution steps and the
filename the reply turns into, not whether any API is up today.
"""

import http.client
import json
import struct
import time
import unittest
import urllib.error
import zlib
from pathlib import Path
from typing import ClassVar
from unittest import mock

from tests import guard
from wallhelper import sources
from wallhelper.library import credits
from wallhelper.net import FetchError
from wallhelper.paths import CREDITS, DIR


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


def save(_url, out: Path) -> None:
    """What download would have done, without the network."""
    out.write_bytes(png(3840, 2160))


class Source(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        for path in DIR.glob("*.*"):
            path.unlink()
        CREDITS.unlink(missing_ok=True)

    def fetch(self, spec, reply):
        """Run one source against a canned JSON reply."""
        document = reply if isinstance(reply, bytes) \
            else json.dumps(reply).encode()
        with mock.patch.object(sources, "fetch_url",
                               return_value=document), \
             mock.patch.object(sources, "download", side_effect=save):
            return sources.fetch_source("test", spec).path

    def probe(self, spec, reply=None, error=None):
        document = reply if isinstance(reply, bytes) \
            else json.dumps(reply).encode()
        with mock.patch.object(sources, "fetch_url",
                               return_value=document,
                               side_effect=error), \
             mock.patch.object(sources, "download", side_effect=save):
            return sources.probe_source("test", spec)


class Fetch(Source):
    def test_the_filename_comes_from_the_date_the_id_and_the_suffix(self):
        out = self.fetch({
            "url": "https://example.com/api",
            "image": "https://example.com{path}",
            "id": "{id}",
            "title": "{title}",
            "credit": "{credit}",
            "link": "{link}",
            "date": "{taken}",
        }, {"taken": "2026-10-05", "path": "/img/photo.jpg",
            "id": "abc 123", "title": "A title", "credit": "Someone",
            "link": "https://example.com/page"})
        self.assertEqual(out.name, "20261005-test-abc-123.jpg")
        # The photographer rides along in .credits, not in the filename.
        self.assertEqual(credits()[out.name][0], "A title")

    def test_a_dashed_date_is_read_back_as_eight_digits(self):
        # stamp() cannot read a filename with punctuation in the date, and
        # APIs hand the date over dashed.
        out = self.fetch({"url": "https://example.com/api",
                          "image": "https://example.com/p.jpg",
                          "date": "{when}"},
                         {"when": "2026-10-05"})
        self.assertTrue(out.name.startswith("20261005-test-"))

    def test_a_title_that_slugifies_to_nothing_falls_to_the_url(self):
        # A Japanese title is not empty, but nothing survives slugify, and
        # two of those in a day would land on the same filename.
        out = self.fetch({"image": "https://example.com/pics/today.jpg",
                          "title": "{title}"},
                         {"title": "日本語のタイトル"})
        self.assertEqual(out.name,
                         f"{time.strftime('%Y%m%d')}-test-today.jpg")

    def test_require_skips_entries_that_do_not_match(self):
        out = self.fetch({
            "url": "https://example.com/api",
            "list": "data",
            "image": "https://example.com{path}",
            "id": "{id}",
            "require": {"media_type": "image"},
        }, {"data": [
            {"media_type": "video", "path": "/v.mp4", "id": "v"},
            {"media_type": "image", "path": "/i.jpg", "id": "chosen"},
        ]})
        self.assertEqual(out.name[-16:], "-test-chosen.jpg")

    def test_a_source_without_a_list_reads_the_document_itself(self):
        out = self.fetch({"url": "https://example.com/api",
                          "image": "https://example.com{path}",
                          "id": "{id}"},
                         {"path": "/x.png", "id": "solo"})
        self.assertEqual(out.name,
                         f"{time.strftime('%Y%m%d')}-test-solo.png")

    def test_a_reply_that_is_not_json_gives_nothing(self):
        self.assertIsNone(self.fetch({"url": "https://example.com/api",
                                      "image": "{path}"},
                                     b"<html>not json</html>"))

    def test_an_unreachable_source_gives_nothing(self):
        with mock.patch.object(
                sources, "fetch_url",
                side_effect=urllib.error.URLError("no route")), \
             mock.patch.object(sources, "download", side_effect=save):
            self.assertIsNone(sources.fetch_source("test", {
                "url": "https://example.com/api", "image": "{path}"}).path)

    def test_a_spec_without_an_image_template_gives_nothing(self):
        self.assertIsNone(self.fetch({"url": "https://example.com"}, {}))

    def test_nothing_is_downloaded_when_no_entry_matches(self):
        with mock.patch.object(sources, "fetch_url",
                               return_value=b'{"data": []}'), \
             mock.patch.object(sources, "download") as taken:
            self.assertIsNone(sources.fetch_source("test", {
                "url": "https://example.com/api", "list": "data",
                "image": "{path}"}).path)
            taken.assert_not_called()


class Probe(Source):
    def test_a_spec_without_an_image_template_says_so(self):
        self.assertEqual(self.probe({"url": "https://example.com"}),
                         (False, "no image template"))

    def test_an_unreachable_source_says_why(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api",
                        "image": "{path}"},
                       error=urllib.error.URLError("no route to host")),
            (False, "no route to host"))

    def test_a_reply_that_is_not_json_says_so(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api", "image": "{path}"},
                       reply=b"<html>"),
            (False, "the reply is not JSON"))

    def test_a_missing_list_says_where_it_looked(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api", "list": "data",
                        "image": "{path}"},
                       reply={"images": []}),
            (False, "nothing to pick from at data"))

    def test_an_empty_list_is_the_same_complaint(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api", "list": "data",
                        "image": "{path}"},
                       reply={"data": []}),
            (False, "nothing to pick from at data"))

    def test_a_source_with_a_photograph_says_whose_it_is(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api",
                        "image": "{path}", "title": "{title}",
                        "credit": "{credit}"},
                       reply={"path": "https://example.com/x.jpg",
                              "title": "A title", "credit": "Someone"}),
            (True, "A title"))

    def test_the_credit_stands_in_when_there_is_no_title(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api",
                        "image": "{path}", "credit": "{credit}"},
                       reply={"path": "https://example.com/x.jpg",
                              "credit": "Someone"}),
            (True, "Someone"))

    def test_a_choice_of_entries_is_said_how_many(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api", "list": "data",
                        "image": "{path}", "title": "{t}"},
                       reply={"data": [
                           {"path": "https://example.com/1.jpg", "t": "One"},
                           {"path": "https://example.com/2.jpg",
                            "t": "Two"}]}),
            (True, "One · 2 to choose from"))

    def test_an_empty_image_template_says_no_photograph(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api",
                        "image": "{path}"},
                       reply={"other": "thing"}),
            (False, "no photograph in the reply ({path})"))

    def test_something_that_is_not_a_url_says_so(self):
        self.assertEqual(
            self.probe({"url": "https://example.com/api",
                        "image": "{path}"},
                       reply={"path": "not-a-url.jpg"}),
            (False, "not a URL: not-a-url.jpg"))

    def test_a_source_with_no_url_reads_a_literal_image(self):
        # A url template that fills to nothing means the document is empty,
        # but a literal image template needs no document at all.
        self.assertEqual(
            self.probe({"image": "https://example.com/x.jpg",
                        "title": "A fixed one"}),
            (True, "A fixed one"))

    def test_nothing_about_the_probe_downloads(self):
        with mock.patch.object(sources, "fetch_url",
                               return_value=b'{"path": "/x.jpg"}'), \
             mock.patch.object(sources, "download") as taken:
            sources.probe_source("test", {"image": "{path}"})
            taken.assert_not_called()


class ListSource(Source):
    def listing(self, spec, reply=None, error=None):
        document = reply if isinstance(reply, bytes) \
            else json.dumps(reply).encode()
        with mock.patch.object(sources, "fetch_url",
                               return_value=document,
                               side_effect=error), \
             mock.patch.object(sources, "download", side_effect=save):
            return sources.list_source("test", spec)

    def list(self, spec, reply):
        return self.listing(spec, reply).candidates

    def test_every_usable_entry_comes_back(self):
        out = self.list({
            "url": "https://example.com/api",
            "list": "data",
            "image": "https://example.com{path}",
            "id": "{id}",
            "title": "{title}",
        }, {"data": [
            {"path": "/a.jpg", "id": "a", "title": "One"},
            {"path": "/b.jpg", "id": "b", "title": "Two"},
        ]})
        self.assertEqual([c["ident"] for c in out], ["a", "b"])
        self.assertEqual([c["title"] for c in out], ["One", "Two"])

    def test_require_filters_the_list(self):
        out = self.list({
            "url": "https://example.com/api",
            "list": "data",
            "image": "{path}",
            "id": "{id}",
            "require": {"media_type": "image"},
        }, {"data": [
            {"path": "/v.jpg", "id": "v", "media_type": "video"},
            {"path": "/i.jpg", "id": "i", "media_type": "image"},
        ]})
        self.assertEqual([c["ident"] for c in out], ["i"])

    def test_replace_runs_over_the_image_url(self):
        out = self.list({
            "url": "https://example.com/api",
            "image": "{path}",
            "id": "{id}",
            "replace": [r"/[0-9]+px-", "/3840px-"],
        }, {"path": "https://example.com/960px-a.jpg", "id": "a"})
        self.assertEqual(out[0]["image"], "https://example.com/3840px-a.jpg")

    def test_credit_text_filter_is_applied(self):
        out = self.list({
            "url": "https://example.com/api",
            "image": "{path}",
            "id": "{id}",
            "credit": "{credit|text}",
        }, {"path": "https://example.com/a.jpg", "id": "a",
            "credit": "<b>Someone</b>"})
        self.assertEqual(out[0]["credit"], "Someone")

    def test_a_source_that_answers_has_no_complaint(self):
        self.assertEqual(
            self.listing({"url": "https://example.com/api", "image": "{p}"},
                         {"p": "https://e.com/a.jpg"}).complaint, "")

    def test_a_source_that_cannot_be_reached_says_why(self):
        got = self.listing(
            {"url": "https://example.com/api", "image": "{p}"},
            error=urllib.error.URLError("Unauthorized"))
        self.assertEqual(got, ([], "Unauthorized"))

    def test_a_timeout_says_so(self):
        got = self.listing({"url": "https://example.com/api", "image": "{p}"},
                           error=TimeoutError("timed out"))
        self.assertEqual(got.complaint, "timed out")

    def test_a_reply_cut_short_says_so(self):
        got = self.listing({"url": "https://example.com/api", "image": "{p}"},
                           error=http.client.IncompleteRead(b"{"))
        self.assertEqual(got.complaint, "the transfer was cut short")

    def test_a_reply_that_is_not_json_says_so(self):
        got = self.listing({"url": "https://example.com/api", "image": "{p}"},
                           b"<html>")
        self.assertEqual(got.complaint, "the reply is not JSON")

    def test_nothing_matching_require_says_so(self):
        got = self.listing({"url": "https://example.com/api",
                            "list": "data", "image": "{p}",
                            "require": {"media_type": "image"}},
                           {"data": [{"p": "/v", "media_type": "video"}]})
        self.assertEqual(got, ([], "nothing to offer today"))

    def test_a_source_waiting_on_its_key_is_not_asked(self):
        spec = {"url": "https://api.example.com/x?client_id=PASTE_KEY",
                "image": "{p}", "key": {"into": "PASTE_KEY"}}
        with mock.patch.object(sources, "fetch_url") as asked:
            got = sources.list_source("test", spec)
        asked.assert_not_called()
        self.assertEqual(got, ([], "needs a key"))

    def test_a_source_given_its_key_is_asked(self):
        spec = {"url": "https://api.example.com/x?client_id=abc123",
                "image": "{p}", "key": {"into": "PASTE_KEY"}}
        got = self.listing(spec, {"p": "https://e.com/a.jpg"})
        self.assertEqual(len(got.candidates), 1)

    def test_the_timeout_reaches_the_request(self):
        with mock.patch.object(sources, "fetch_url",
                               return_value=b"{}") as asked:
            sources.list_source(
                "test", {"url": "https://e.com", "image": "{p}"}, timeout=8)
        self.assertEqual(asked.call_args.kwargs["timeout"], 8)

    def test_listing_never_downloads(self):
        with mock.patch.object(sources, "fetch_url",
                               return_value=b'{"path": "/x.jpg", "id": "x"}'), \
             mock.patch.object(sources, "download") as taken:
            sources.list_source("test", {"image": "{path}", "id": "{id}"})
            taken.assert_not_called()


class Adopt(Source):
    def adopt(self, spec, cand):
        with mock.patch.object(sources, "download", side_effect=save):
            return sources.adopt("test", spec, cand)

    def test_the_filename_follows_the_same_rules_as_a_fetch(self):
        out = self.adopt({}, {"image": "https://example.com/pics/today.jpg",
                              "ident": "abc-123", "date": "2026-10-05"})
        self.assertEqual(out.name, "20261005-test-abc-123.jpg")

    def test_the_photographer_rides_along_in_credits(self):
        out = self.adopt({}, {"image": "https://example.com/x.jpg",
                              "ident": "x", "date": "20261005",
                              "title": "A title", "credit": "Someone",
                              "link": "https://example.com/page"})
        self.assertEqual(credits()[out.name], ("A title", "Someone",
                                               "https://example.com/page"))

    def test_min_width_rejects_a_small_photograph_and_says_how_small(self):
        def tiny(_url, out: Path) -> None:
            out.write_bytes(png(800, 600))
        with mock.patch.object(sources, "download", side_effect=tiny), \
             self.assertRaisesRegex(FetchError, "too small: 800 px"):
            sources.adopt(
                "test", {"min_width": 1920},
                {"image": "https://example.com/s.jpg", "ident": "s",
                 "date": "20261005"})
        # Nothing of it is left in the collection, or in the ledger.
        self.assertEqual(list(DIR.glob("*.jpg")), [])
        self.assertEqual(credits(), {})

    def test_a_collision_downloads_nothing_new(self):
        cand = {"image": "https://example.com/x.jpg", "ident": "x",
                "date": "20261005"}
        first = self.adopt({}, cand)
        with mock.patch.object(sources, "download") as taken, \
             self.assertRaisesRegex(FetchError, "already in the collection"):
            sources.adopt("test", {}, cand)
        taken.assert_not_called()
        self.assertTrue(first.exists())

    def test_a_download_that_fails_says_why(self):
        with mock.patch.object(sources, "download",
                               side_effect=FetchError("Unauthorized")), \
             self.assertRaisesRegex(FetchError, "Unauthorized"):
            sources.adopt("test", {}, {
                "image": "https://example.com/x.jpg", "ident": "x"})

    def test_a_walk_over_candidates_goes_on_past_a_failed_one(self):
        # fetch_source tries the next candidate; the reason is for a click.
        answers = iter([FetchError("Not Found"), None])

        def flaky(_url, out: Path) -> None:
            if (answer := next(answers)) is not None:
                raise answer
            save(_url, out)
        spec = {"image": "{p}", "list": ".", "id": "{id}"}
        with mock.patch.object(
                sources, "fetch_url",
                return_value=json.dumps([{"p": "https://e.com/a.jpg",
                                          "id": "a"},
                                         {"p": "https://e.com/b.jpg",
                                          "id": "b"}]).encode()), \
             mock.patch.object(sources, "download", side_effect=flaky):
            out = sources.fetch_source(
                "test", {**spec, "url": "https://e.com"})
        self.assertIsNotNone(out.path)


class Refusal(unittest.TestCase):
    def test_a_source_with_no_demands_refuses_nothing(self):
        self.assertEqual(sources.refusal({}, (10, 10000)), "")
        self.assertEqual(sources.refusal({}, None), "")

    def test_under_the_floor_says_how_wide_it_was(self):
        spec = {"min_width": 1920}
        self.assertEqual(sources.refusal(spec, (1600, 900)),
                         "too small: 1600 px")
        self.assertEqual(sources.refusal(spec, (1920, 1080)), "")

    def test_a_portrait_and_a_square_are_not_wide_enough(self):
        spec = {"min_aspect": 1.3}
        self.assertEqual(sources.refusal(spec, (2160, 3840)),
                         "not wide enough: 2160 \u00d7 3840")
        self.assertEqual(sources.refusal(spec, (1600, 1600)),
                         "not wide enough: 1600 \u00d7 1600")

    def test_four_by_three_and_wider_pass(self):
        spec = {"min_aspect": 1.3}
        for size in ((1600, 1200), (1920, 1080), (5000, 1000)):
            self.assertEqual(sources.refusal(spec, size), "")

    def test_the_floor_is_read_first(self):
        self.assertEqual(
            sources.refusal({"min_width": 1920, "min_aspect": 1.3},
                            (900, 1600)),
            "too small: 900 px")

    def test_a_size_nobody_could_read_is_refused_when_one_is_demanded(self):
        self.assertEqual(sources.refusal({"min_width": 1920}, None),
                         "can't tell its size")

    def test_a_demand_that_is_not_a_number_is_no_demand(self):
        self.assertEqual(
            sources.refusal({"min_width": "wide", "min_aspect": None},
                            (10, 10)), "")


class Offer(Source):
    """The gallery's list: what list_source finds, less what adopt would
    refuse for its size. Sizes are canned; the head fetch is tested in
    test_net."""

    SPEC: ClassVar[dict] = {
        "url": "https://example.com/api", "list": ".", "image": "{p}",
        "min_width": 1920, "min_aspect": 1.3}

    def offer(self, spec, sizes):
        reply = json.dumps([{"p": url} for url in sizes]).encode()

        def size_of(url, _timeout):
            answer = sizes[url]
            if isinstance(answer, Exception):
                raise answer
            return answer
        with mock.patch.object(sources, "fetch_url", return_value=reply), \
             mock.patch.object(sources, "remote_size",
                               side_effect=size_of) as asked:
            return sources.offer_source("test", spec), asked

    def test_small_and_portrait_and_square_are_not_offered(self):
        got, _asked = self.offer(self.SPEC, {
            "https://e.com/ok.jpg": (2560, 1440),
            "https://e.com/small.jpg": (1600, 900),
            "https://e.com/tall.jpg": (2160, 3840),
            "https://e.com/square.jpg": (2000, 2000),
        })
        self.assertEqual([c["image"] for c in got.candidates],
                         ["https://e.com/ok.jpg"])
        self.assertEqual(got.complaint, "")

    def test_order_is_the_sources_order(self):
        got, _asked = self.offer(self.SPEC, {
            f"https://e.com/{n}.jpg": (2560, 1440) for n in "cab"})
        self.assertEqual([c["image"][-5] for c in got.candidates],
                         ["c", "a", "b"])

    def test_nothing_fitting_says_why_for_the_first(self):
        got, _asked = self.offer(self.SPEC, {
            "https://e.com/small.jpg": (1600, 900),
            "https://e.com/tall.jpg": (2160, 3840),
        })
        self.assertEqual(got, ([], "nothing fits today (too small: 1600 px)"))

    def test_a_url_that_does_not_answer_is_still_offered(self):
        # Not knowing is not a reason; the click will say what is wrong.
        got, _asked = self.offer(self.SPEC, {
            "https://e.com/slow.jpg": FetchError("timed out"),
            "https://e.com/small.jpg": (1600, 900),
        })
        self.assertEqual([c["image"] for c in got.candidates],
                         ["https://e.com/slow.jpg"])

    def test_a_size_that_cannot_be_read_is_not_offered(self):
        # adopt would refuse it for the same reason after downloading it.
        got, _asked = self.offer(self.SPEC, {"https://e.com/odd.webp": None})
        self.assertEqual(got.candidates, [])

    def test_a_source_that_asks_for_no_size_costs_no_requests(self):
        got, asked = self.offer({**self.SPEC, "min_width": 0,
                                 "min_aspect": 0},
                                {"https://e.com/a.jpg": (10, 10)})
        asked.assert_not_called()
        self.assertEqual(len(got.candidates), 1)

    def test_a_source_that_failed_to_list_is_passed_through(self):
        with mock.patch.object(
                sources, "fetch_url",
                side_effect=urllib.error.URLError("timed out")):
            got = sources.offer_source("test", self.SPEC)
        self.assertEqual(got, ([], "timed out"))


class AdoptShape(Source):
    def test_a_square_is_refused_where_the_source_wants_wide_ones(self):
        def square(_url, out: Path) -> None:
            out.write_bytes(png(1600, 1600))
        with mock.patch.object(sources, "download", side_effect=square), \
             self.assertRaisesRegex(FetchError, "not wide enough"):
            sources.adopt("test", {"min_aspect": 1.3}, {
                "image": "https://example.com/s.jpg", "ident": "s",
                "date": "20261005"})
        self.assertEqual(list(DIR.glob("*.jpg")), [])


class Target(Source):
    CAND: ClassVar[dict] = {"image": "https://example.com/pics/a.jpg",
                            "ident": "abc", "date": "2026-10-05"}

    def test_it_is_the_file_adopt_writes(self):
        with mock.patch.object(sources, "download", side_effect=save):
            kept = sources.adopt("test", {}, self.CAND)
        self.assertEqual(sources.target("test", self.CAND), kept)

    def test_the_same_candidate_is_always_the_same_file(self):
        self.assertEqual(sources.target("test", self.CAND),
                         DIR / "20261005-test-abc.jpg")
        self.assertEqual(sources.target("test", dict(self.CAND)),
                         sources.target("test", self.CAND))

    def test_another_source_is_another_file(self):
        self.assertNotEqual(sources.target("one", self.CAND),
                            sources.target("two", self.CAND))

    def test_the_suffix_comes_from_the_url_path_not_its_query(self):
        cand = {**self.CAND, "image": "https://e.com/a.png?width=3840.jpg"}
        self.assertEqual(sources.target("test", cand).suffix, ".png")
