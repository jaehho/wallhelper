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
        self.assertEqual(cfg.config()["autofetch"], cfg.DEFAULTS["autofetch"])
        self.assertEqual(cfg.config()["gallery"], cfg.DEFAULTS["gallery"])

    def test_corrupt_file_means_defaults(self):
        CONFIG.write_text("{not json")
        self.assertEqual(cfg.config()["autofetch"], cfg.DEFAULTS["autofetch"])

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

    def test_the_name_lists_are_stored_when_they_differ(self):
        full = json.loads(json.dumps(cfg.DEFAULTS))
        full["gallery"] = ["apod"]
        self.assertEqual(cfg.trim(full), {"gallery": ["apod"]})

    def test_a_source_of_your_own_is_stored_whole(self):
        full = json.loads(json.dumps(cfg.DEFAULTS))
        full["mine"] = {"url": "https://example.com", "image": "{u}"}
        self.assertEqual(cfg.trim(full)["mine"], full["mine"])


class Named(unittest.TestCase):
    def setUp(self):
        CONFIG.unlink(missing_ok=True)

    def test_only_names_that_describe_a_source(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({
            "autofetch": ["bing", "ghost"],
            "gallery": ["apod", "ghost"],
        }))
        self.assertEqual(cfg.autofetch_sources(), ["bing"])
        self.assertEqual(cfg.gallery_sources(), ["apod"])


class Sections(unittest.TestCase):
    """Which section of the settings panel a source's row sits in."""

    def setUp(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.unlink(missing_ok=True)
        self.addCleanup(CONFIG.unlink, missing_ok=True)

    def test_a_fresh_config_splits_morning_from_elsewhere(self):
        morning, elsewhere = cfg.settings_lists(cfg.config())
        self.assertEqual(morning, ["bing"])
        self.assertEqual(elsewhere, ["apod", "wikipedia", "unsplash"])

    def test_switching_bing_off_leaves_its_row_under_morning(self):
        # One click on bing used to empty `autofetch`, which moved the row
        # to ELSEWHERE, where clicking it only ever filled `gallery`.
        # The panel re-reads the file after every click, so this does too.
        full = cfg.config()
        self.assertFalse(cfg.toggle_source(full, "bing", "autofetch"))
        cfg.save_config(full)

        again = cfg.config()
        self.assertEqual(again["autofetch"], [])
        morning, elsewhere = cfg.settings_lists(again)
        self.assertIn("bing", morning)
        self.assertNotIn("bing", elsewhere)

    def test_a_second_click_switches_bing_back_on(self):
        full = cfg.config()
        cfg.toggle_source(full, "bing", "autofetch")
        cfg.save_config(full)

        full = cfg.config()
        self.assertTrue(cfg.toggle_source(full, "bing", "autofetch"))
        cfg.save_config(full)
        self.assertEqual(cfg.autofetch_sources(), ["bing"])

    def test_a_morning_source_of_your_own_is_listed_under_morning(self):
        CONFIG.write_text(json.dumps({
            "autofetch": ["bing", "mine"],
            "mine": {"image": "{u}"},
        }))
        morning, elsewhere = cfg.settings_lists(cfg.config())
        self.assertEqual(morning, ["bing", "mine"])
        self.assertNotIn("mine", elsewhere)

    def test_a_defined_source_in_neither_list_is_offered_elsewhere(self):
        CONFIG.write_text(json.dumps({"mine": {"image": "{u}"}}))
        morning, elsewhere = cfg.settings_lists(cfg.config())
        self.assertNotIn("mine", morning)
        self.assertIn("mine", elsewhere)

    def test_a_name_with_no_source_behind_it_is_skipped(self):
        CONFIG.write_text(json.dumps({
            "autofetch": ["bing", "ghost"], "gallery": ["ghost"],
        }))
        morning, elsewhere = cfg.settings_lists(cfg.config())
        self.assertEqual(morning, ["bing"])
        self.assertNotIn("ghost", elsewhere)


class Edit(unittest.TestCase):
    def setUp(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.unlink(missing_ok=True)
        self.addCleanup(CONFIG.unlink, missing_ok=True)

    def test_a_missing_file_is_made_empty_and_valid(self):
        cfg.ensure_config()
        self.assertEqual(json.loads(CONFIG.read_text()), {})
        self.assertEqual(cfg.config()["autofetch"], cfg.DEFAULTS["autofetch"])

    def test_the_file_you_wrote_is_left_exactly_as_it_was(self):
        text = '{ "autofetch": [],\n  "mine": {"image": "{u}"} }\n'
        CONFIG.write_text(text)
        cfg.ensure_config()
        self.assertEqual(CONFIG.read_text(), text)


class Migrate(unittest.TestCase):
    def setUp(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.unlink(missing_ok=True)

    def test_old_sources_becomes_autofetch_and_gallery(self):
        CONFIG.write_text(json.dumps({
            "sources": ["bing", "wallhaven", "apod"],
            "wallhaven": cfg._OLD_WALLHAVEN,
        }))
        cfg.migrate()
        stored = json.loads(CONFIG.read_text() or "{}")
        merged = cfg.config()
        self.assertEqual(merged["autofetch"], ["bing"])
        self.assertEqual(merged["gallery"],
                         ["apod", "wikipedia", "unsplash"])
        self.assertNotIn("sources", stored)
        self.assertNotIn("wallhaven", stored)
        self.assertEqual(cfg.autofetch_sources(), ["bing"])

    def test_a_rewritten_wallhaven_body_is_kept(self):
        custom = {**cfg._OLD_WALLHAVEN, "url": "https://example.com/q"}
        CONFIG.write_text(json.dumps({
            "sources": ["bing", "wallhaven"],
            "wallhaven": custom,
        }))
        cfg.migrate()
        stored = json.loads(CONFIG.read_text())
        self.assertEqual(stored.get("wallhaven"), custom)
        self.assertEqual(cfg.autofetch_sources(), ["bing"])
        self.assertNotIn("wallhaven", cfg.gallery_sources())


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
