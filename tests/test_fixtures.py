"""The shipped source's replies, recorded once from the live API and
trimmed to the fields its template reads, pinned against the filenames
fetch_source derives from them.

Filename bugs have been found against live replies -- a date handed over
dashed, a title namespaced with 'File:', a title that slugifies to
nothing -- so these are recorded, not invented. Recorded 2026-10-11
through wallhelper's own fetch_url, arrays cut to their first entry. The
day half of bing's names comes from the reply. APOD, Wikipedia and
Unsplash had recordings here until #23 took them out.
"""

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
        """What filename the recorded reply for one source turns into.

        randrange is pinned to the first entry so a multi-entry reply
        names the same file every run.
        """
        document = FIXTURES.joinpath(f"{fixture}.json").read_bytes()
        with mock.patch.object(sources, "fetch_url",
                               return_value=document), \
             mock.patch.object(sources, "download", side_effect=save), \
             mock.patch.object(sources.random, "randrange", return_value=0):
            out = sources.fetch_source(name, spec).path
        self.assertIsNotNone(out, f"{fixture} resolved to no photograph")
        return out.name

    def test_bing_names_the_file_for_the_day_and_the_title(self):
        self.assertEqual(self.derive("bing", "bing", DEFAULTS["bing"]),
                         "20261007-bing-Puzzled-Follow-the-trail.jpg")

    def test_a_title_that_slugifies_to_nothing_falls_to_the_url(self):
        # The same bing source on the JP market: the title is not empty,
        # but nothing of it survives slugify, and the name comes from
        # the image URL's stem instead.
        spec = {**DEFAULTS["bing"],
                "url": "https://www.bing.com/HPImageArchive.aspx"
                       "?format=js&idx=0&n=1&mkt=ja-JP"}
        self.assertEqual(self.derive("bing-ja", "bing", spec),
                         "20261007-bing-th.jpg")
