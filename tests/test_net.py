"""The two network manners, against a server on the loopback.

Mocking urlopen would pass on the bug these pin: http.client is what
refuses a non-ASCII request line, so the request has to reach it.
"""

import contextlib
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests import guard
from tests.test_sources import png
from wallhelper.net import FetchError, ascii_url, download, fetch_url
from wallhelper.paths import DIR


def setUpModule():
    guard()


@contextlib.contextmanager
def serving(replies: dict[str, tuple[int, bytes]]):
    """A server answering by decoded path; yields (base URL, paths asked
    for, as they arrived on the wire)."""
    asked: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            asked.append(self.path)
            status, body = replies.get(urllib.parse.unquote(self.path),
                                       (404, b""))
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", asked
    finally:
        server.shutdown()
        server.server_close()


class AsciiUrl(unittest.TestCase):
    def test_non_ascii_is_percent_encoded_as_utf8(self):
        self.assertEqual(
            ascii_url("https://a.example/x/Jesličky_01.png?q=č#č"),
            "https://a.example/x/Jesli%C4%8Dky_01.png?q=%C4%8D#%C4%8D")

    def test_what_is_already_escaped_is_left_alone(self):
        url = "https://a.example/a%20b/%C4%8D.png?x=1&y=%2F&z=a+b"
        self.assertEqual(ascii_url(url), url)

    def test_a_space_is_escaped_rather_than_refused(self):
        self.assertEqual(ascii_url("https://a.example/a b.png"),
                         "https://a.example/a%20b.png")


class Fetch(unittest.TestCase):
    def test_a_non_ascii_path_reaches_the_server_as_utf8(self):
        name = "/2026_10_10_PZ_Jesličky_01_1500px.png"
        with serving({name: (200, b"bytes")}) as (base, asked):
            self.assertEqual(fetch_url(base + name), b"bytes")
        self.assertEqual(asked, ["/2026_10_10_PZ_Jesli%C4%8Dky_01_1500px.png"])


class Download(unittest.TestCase):
    def setUp(self):
        DIR.mkdir(parents=True, exist_ok=True)
        self.dest = DIR / "fetched.png"
        self.dest.unlink(missing_ok=True)

    def test_a_non_ascii_url_downloads(self):
        name = "/Jesličky.png"
        with serving({name: (200, png(8, 8))}) as (base, _asked):
            download(base + name, self.dest)
        self.assertTrue(self.dest.read_bytes().startswith(b"\x89PNG"))

    def test_the_servers_words_are_the_reason(self):
        with serving({"/key.png": (401, b"")}) as (base, _asked), \
             self.assertRaisesRegex(FetchError, "Unauthorized"):
            download(base + "/key.png", self.dest)
        self.assertFalse(self.dest.exists())

    def test_something_that_is_not_an_image_is_refused_and_not_kept(self):
        with serving({"/page.png": (200, b"<html>")}) as (base, _asked), \
             self.assertRaisesRegex(FetchError, "not an image"):
            download(base + "/page.png", self.dest)
        self.assertFalse(self.dest.exists())
        self.assertEqual([p.name for p in Path(DIR).glob(".fetch-*")], [])

    def test_an_empty_reply_is_refused(self):
        with serving({"/e.png": (200, b"")}) as (base, _asked), \
             self.assertRaisesRegex(FetchError, "empty"):
            download(base + "/e.png", self.dest)

    def test_a_url_that_is_not_one_is_a_reason_not_a_crash(self):
        with self.assertRaises(FetchError):
            download("not a url", self.dest)
