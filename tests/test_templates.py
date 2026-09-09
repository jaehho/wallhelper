"""The template language a source is written in."""

import unittest

from tests import guard
from wallhelper.sources import dig, fill


def setUpModule():
    guard()


REPLY = {
    "images": [{"urlbase": "/th?id=OHR.Lake", "title": "A reservoir",
                "copyright": "Lake Fyans (© tracielouise)"}],
    "image": {"title": "File:Tallinn_vanalinn.jpg",
              "description": {"text": "Old town"}},
    "count": 3,
}


class Dig(unittest.TestCase):
    def test_walks_a_dotted_path(self):
        self.assertEqual(dig(REPLY, "image.description.text"), "Old town")

    def test_indexes_a_list(self):
        self.assertEqual(dig(REPLY, "images.0.title"), "A reservoir")

    def test_dot_is_the_document(self):
        self.assertIs(dig(REPLY, "."), REPLY)
        self.assertIs(dig(REPLY, ""), REPLY)

    def test_missing_anything_is_none(self):
        for path in ("nope", "image.nope", "images.9.title",
                     "images.x.title", "count.deeper"):
            self.assertIsNone(dig(REPLY, path), path)


class Fill(unittest.TestCase):
    def test_substitutes_a_token(self):
        self.assertEqual(fill("{title}", REPLY["images"][0]), "A reservoir")

    def test_literal_text_survives(self):
        self.assertEqual(
            fill("https://www.bing.com{urlbase}_UHD.jpg", REPLY["images"][0]),
            "https://www.bing.com/th?id=OHR.Lake_UHD.jpg")

    def test_a_missing_path_empties_rather_than_raises(self):
        self.assertEqual(fill("[{nope}]", REPLY), "[]")

    def test_date_comes_from_the_clock(self):
        import time
        self.assertEqual(fill("{date:%Y}", {}), time.strftime("%Y"))

    def test_name_and_stem_filters(self):
        # Wikipedia hands back "File:Tallinn_vanalinn.jpg" as an identifier;
        # the filename wants "Tallinn_vanalinn".
        self.assertEqual(fill("{image.title|name|stem}", REPLY),
                         "Tallinn_vanalinn")

    def test_no_template_is_empty(self):
        self.assertEqual(fill(None, REPLY), "")
