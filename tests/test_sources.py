"""Asking a source what it has, and taking a photograph from it.

The network is mocked throughout: these pin the resolution steps and the
filename the reply turns into, not whether any API is up today.
"""

import json
import struct
import time
import unittest
import urllib.error
import zlib
from pathlib import Path
from unittest import mock

from tests import guard
from wallhelper import sources
from wallhelper.library import credits
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


def save(_url, out: Path) -> bool:
    """What download would have done, without the network."""
    out.write_bytes(png(3840, 2160))
    return True


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
            return sources.fetch_source("test", spec)

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
                "url": "https://example.com/api", "image": "{path}"}))

    def test_a_spec_without_an_image_template_gives_nothing(self):
        self.assertIsNone(self.fetch({"url": "https://example.com"}, {}))

    def test_nothing_is_downloaded_when_no_entry_matches(self):
        with mock.patch.object(sources, "fetch_url",
                               return_value=b'{"data": []}'), \
             mock.patch.object(sources, "download") as taken:
            self.assertIsNone(sources.fetch_source("test", {
                "url": "https://example.com/api", "list": "data",
                "image": "{path}"}))
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
    def list(self, spec, reply):
        document = reply if isinstance(reply, bytes) \
            else json.dumps(reply).encode()
        with mock.patch.object(sources, "fetch_url",
                               return_value=document), \
             mock.patch.object(sources, "download", side_effect=save):
            return sources.list_source("test", spec)

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

    def test_min_width_rejects_a_small_photograph(self):
        def tiny(_url, out: Path) -> bool:
            out.write_bytes(png(800, 600))
            return True
        with mock.patch.object(sources, "download", side_effect=tiny):
            self.assertIsNone(sources.adopt(
                "test", {"min_width": 1920},
                {"image": "https://example.com/s.jpg", "ident": "s",
                 "date": "20261005"}))

    def test_a_collision_downloads_nothing_new(self):
        cand = {"image": "https://example.com/x.jpg", "ident": "x",
                "date": "20261005"}
        first = self.adopt({}, cand)
        with mock.patch.object(sources, "download") as taken:
            self.assertIsNone(sources.adopt("test", {}, cand))
            taken.assert_not_called()
        self.assertTrue(first.exists())
