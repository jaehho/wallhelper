"""Merging, ordering, and storing only what you changed."""

import json
import unittest

from tests import guard
from wallhelper import config as cfg
from wallhelper.paths import CONFIG


def setUpModule():
    guard()



class Merge(unittest.TestCase):
    def setUp(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.unlink(missing_ok=True)

    def test_no_file_means_defaults(self):
        self.assertEqual(cfg.config()["sources"], cfg.DEFAULTS["sources"])

    def test_corrupt_file_means_defaults(self):
        CONFIG.write_text("{not json")
        self.assertEqual(cfg.config()["sources"], cfg.DEFAULTS["sources"])

    def test_a_delta_merges_over_one_source(self):
        CONFIG.write_text(json.dumps({"bing": {"link": "https://example.com"}}))
        bing = cfg.config()["bing"]
        self.assertEqual(bing["link"], "https://example.com")
        self.assertEqual(bing["image"], cfg.DEFAULTS["bing"]["image"])

    def test_a_key_you_invented_is_kept(self):
        CONFIG.write_text(json.dumps({"mine": {"image": "{u}"}}))
        self.assertEqual(cfg.config()["mine"], {"image": "{u}"})


class Trim(unittest.TestCase):
    def test_unchanged_sources_are_not_stored(self):
        self.assertEqual(cfg.trim(cfg.DEFAULTS), {})

    def test_only_the_changed_key_is_stored(self):
        full = json.loads(json.dumps(cfg.DEFAULTS))
        full["bing"]["link"] = "https://example.com"
        self.assertEqual(cfg.trim(full),
                         {"bing": {"link": "https://example.com"}})

    def test_the_source_list_is_stored_when_it_differs(self):
        full = json.loads(json.dumps(cfg.DEFAULTS))
        full["sources"] = ["bing"]
        self.assertEqual(cfg.trim(full), {"sources": ["bing"]})

    def test_a_source_of_your_own_is_stored_whole(self):
        full = json.loads(json.dumps(cfg.DEFAULTS))
        full["mine"] = {"url": "https://example.com", "image": "{u}"}
        self.assertEqual(cfg.trim(full)["mine"], full["mine"])


class Enabled(unittest.TestCase):
    def setUp(self):
        CONFIG.unlink(missing_ok=True)

    def test_only_names_that_describe_a_source(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"sources": ["bing", "ghost"]}))
        self.assertEqual(cfg.enabled(), ["bing"])


class Keys(unittest.TestCase):
    def test_a_placeholder_is_reported(self):
        self.assertEqual(cfg.needs_setup(cfg.DEFAULTS["unsplash"]),
                         "PASTE_YOUR_ACCESS_KEY")

    def test_a_ready_source_needs_nothing(self):
        self.assertEqual(cfg.needs_setup(cfg.DEFAULTS["bing"]), "")

    def test_applying_a_key_clears_the_placeholder(self):
        spec = cfg.apply_key(cfg.DEFAULTS["unsplash"],
                             "PASTE_YOUR_ACCESS_KEY", "abc123")
        self.assertIn("client_id=abc123", spec["url"])
        self.assertEqual(cfg.needs_setup(spec), "")

    def test_applying_a_key_does_not_mutate_the_default(self):
        cfg.apply_key(cfg.DEFAULTS["unsplash"], "PASTE_YOUR_ACCESS_KEY", "x")
        self.assertIn("PASTE_YOUR_ACCESS_KEY",
                      cfg.DEFAULTS["unsplash"]["url"])
