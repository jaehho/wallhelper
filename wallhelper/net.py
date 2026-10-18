"""Fetching bytes off the internet, with the two manners that matter: a User-
Agent that does not get us blocked, and a download that never leaves a
half-written file where a photograph should be."""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Plain token on purpose: some CDNs 403 any User-Agent carrying a
# parenthesized URL, which silently kills the source behind it.
UA = "wallhelper/1.0"

# Everything a URL is allowed to spell with, so that quoting touches only
# what could not have been sent anyway. The '%' is in it: an escape that is
# already there stays one escape.
_URL_SAFE = "%:/?#[]@!$&'()*+,;=~"
_BLURB_LIMIT = 70
# What a request can fail with. URLError and TimeoutError are OSErrors
# already; ValueError is a URL that cannot be sent.
_FAILURES = (urllib.error.URLError, OSError, TimeoutError, ValueError)


class FetchError(Exception):
    """Nothing usable came back. str() is why, in one line a toast or a
    panel can show: what the other end said, or what was wrong with it."""


def describe(problem: Exception) -> str:
    """One line for a failed request, in the other end's words where it had
    any: 'Unauthorized', 'timed out', 'Name or service not known'."""
    text = str(getattr(problem, "reason", problem))
    text = re.sub(r"^\[Errno -?\d+\]\s*", "", text)
    return (text or type(problem).__name__)[:_BLURB_LIMIT]


def ascii_url(url: str) -> str:
    """The URL with every non-ASCII character of its path, query and
    fragment percent-encoded as UTF-8, which is what a server reads.

    http.client writes the request line as ASCII and raises on anything
    else, and APIs hand us filenames like '..._Jesličky_01_1500px.png'. The
    host is left alone: http.client sends a non-ASCII one as IDNA itself.
    """
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parts._replace(
        path=urllib.parse.quote(parts.path, safe=_URL_SAFE),
        query=urllib.parse.quote(parts.query, safe=_URL_SAFE),
        fragment=urllib.parse.quote(parts.fragment, safe=_URL_SAFE),
    ))


def fetch_url(url: str, timeout: int = 30,
              headers: dict | None = None,
              limit: int | None = None) -> bytes:
    """The reply body, or only its first `limit` bytes."""
    sent = {"User-Agent": UA}
    if isinstance(headers, dict):
        sent.update({str(k): str(v) for k, v in headers.items()})
    req = urllib.request.Request(ascii_url(url), headers=sent)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(limit)


def fetch_head(url: str, limit: int, timeout: int) -> bytes:
    """The first `limit` bytes of a file, which is where an image keeps its
    size. Asks for just those, and stops reading at them either way.
    FetchError, saying why, when they do not come."""
    try:
        return fetch_url(url, timeout=timeout, limit=limit,
                         headers={"Range": f"bytes=0-{limit - 1}"})
    except _FAILURES as err:
        raise FetchError(describe(err)) from err


def download(url: str, dest: Path) -> None:
    """Via a tempfile, so a truncated transfer never lands in the folder.
    FetchError, saying why, when nothing was kept."""
    tmp = dest.with_name(f".fetch-{os.getpid()}")
    try:
        data = fetch_url(url, timeout=120)
        if not data:
            msg = "the reply was empty"
            raise FetchError(msg)
        # Trust the bytes, not the extension.
        if data[:2] not in (b"\xff\xd8", b"\x89P", b"RI", b"BM"):
            msg = "the reply is not an image"
            raise FetchError(msg)
        tmp.write_bytes(data)
        tmp.chmod(0o644)           # mktemp-style 0600 would be odd here
        tmp.replace(dest)
    except _FAILURES as err:
        raise FetchError(describe(err)) from err
    finally:
        tmp.unlink(missing_ok=True)
