"""The shipped sources' replies, recorded once from the live APIs and
trimmed to the fields their templates read, pinned against the filenames
fetch_source derives from them.

Every filename bug so far was found against a live reply -- APOD handing
the date over dashed, Wikipedia namespacing the title with 'File:', a
title that slugifies to nothing -- so these are recorded, not invented.
Recorded 2026-10-07 through wallhelper's own fetch_url, arrays cut to
their first entry; the day half of bing's and apod's names comes from the
reply, wikipedia's and wallhaven's from the clock. Unsplash is absent:
its API answers only with an access key, and none is pasted into the
config on the machine that recorded these.
"""

import time
import unittest
from pathlib import Path
from unittest import mock

from tests import guard
from tests.test_sources import save
from wallhelper import sources
from wallhelper.config import DEFAULTS
from wallhelper.paths import CREDITS, DIR

FIXTURES = Path(__file__).parent / "fixtures"


def setUpModule():
    guard()


class Shipped(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        for path in DIR.glob("*.*"):
            path.unlink()
        CREDITS.unlink(missing_ok=True)

    def derive(self, fixture, name, spec):
        """What filename the recorded reply for one source turns into."""
        document = FIXTURES.joinpath(f"{fixture}.json").read_bytes()
        with mock.patch.object(sources, "fetch_url",
                               return_value=document), \
             mock.patch.object(sources, "download", side_effect=save):
            out = sources.fetch_source(name, spec)
        self.assertIsNotNone(out, f"{fixture} resolved to no photograph")
        return out.name

    def test_bing_names_the_file_for_the_day_and_the_title(self):
        self.assertEqual(self.derive("bing", "bing", DEFAULTS["bing"]),
                         "20261007-bing-Puzzled-Follow-the-trail.jpg")

    def test_apods_dashed_date_is_still_eight_digits(self):
        # stamp() reads the date back out of the name, and it cannot
        # parse one with dashes in it.
        self.assertEqual(self.derive("apod", "apod", DEFAULTS["apod"]),
                         "20261007-apod-NASA-Science.png")

    def test_wikipedias_file_prefix_is_not_the_name(self):
        # '{image.title|name|stem}' trims the namespace, and the id
        # truncates at slugify's limit rather than mid-filename.
        self.assertEqual(
            self.derive("wikipedia", "wikipedia", DEFAULTS["wikipedia"]),
            f"{time.strftime('%Y%m%d')}-wikipedia-"
            "Rain-Quail-in-Bhigwan-August-2025-by-Tisha-M.jpg")

    def test_wallhaven_names_the_file_for_its_id(self):
        self.assertEqual(
            self.derive("wallhaven", "wallhaven", DEFAULTS["wallhaven"]),
            f"{time.strftime('%Y%m%d')}-wallhaven-jel1jq.jpg")

    def test_a_title_that_slugifies_to_nothing_falls_to_the_url(self):
        # The same bing source on the JP market: the title is not empty,
        # but nothing of it survives slugify, and the name comes from
        # the image URL's stem instead.
        spec = {**DEFAULTS["bing"],
                "url": "https://www.bing.com/HPImageArchive.aspx"
                       "?format=js&idx=0&n=1&mkt=ja-JP"}
        self.assertEqual(self.derive("bing-ja", "bing", spec),
                         f"{time.strftime('%Y%m%d')}-bing-th.jpg")
