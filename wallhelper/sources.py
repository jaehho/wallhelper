"""A source is data, not code.

Fetch one JSON document, optionally pick an entry out of an array inside it,
and fill a handful of templates from that entry. Every shipped source is
written in this language, which means adding one is a config edit and the
window can offer to test it.
"""

from __future__ import annotations

import contextlib
import html
import io
import json
import random
import re
import time
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import NamedTuple

from .config import needs_setup
from .library import measure, measure_stream, remember, slugify
from .net import FetchError, describe, download, fetch_head, fetch_url
from .paths import DIR

_REPLACE_PAIR_LEN = 2
_YYYYMMDD_LEN = 8
# Where a JPEG keeps its size is after the metadata in front of it, which
# the photographs these sources serve do not stretch past a few dozen KB.
_HEAD_BYTES = 256 * 1024
_SIZING_THREADS = 8


def dig(data, path: str):
    """Walk dotted JSON: 'images.0.urlbase'. Missing anything means None.

    "." is the document itself, which is how a source reads an API that
    returns a bare array rather than an object wrapping one.
    """
    if not path or path == ".":
        return data
    for part in str(path).split("."):
        if isinstance(data, list):
            try:
                data = data[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(data, dict):
            if part not in data:
                return None
            data = data[part]
        else:
            return None
    return data


TOKEN = re.compile(r"\{([^{}]+)\}")


def fill(template, data) -> str:
    """Substitute {some.path} out of the JSON, and {date:%Y-%m-%d} out of the
    clock. A string with no braces is returned unchanged, which is how a
    literal URL or a fixed credit line works.

    A path may be followed by filters: {a.b|name|stem|text}. Values pulled
    out of APIs are so often filenames, namespaced titles
    ('File:Tallinn ....jpg'), or HTML that trimming them needed to be sayable
    in the template rather than in here.
    """
    if not template:
        return ""

    def one(match):
        key, *filters = match.group(1).split("|")
        if key.startswith("date:"):
            text = time.strftime(key[5:])
        else:
            found = dig(data, key)
            text = "" if found is None else str(found)
        for raw in filters:
            step = raw.strip()
            if step == "name":       # after the last / or :
                text = re.split(r"[/:]", text)[-1]
            elif step == "stem":     # without the extension
                text = Path(text).stem
            elif step == "text":     # HTML credit -> plain words
                text = html.unescape(re.sub(r"<[^>]+>", "", text))
                text = re.sub(r"\s+", " ", text).strip()
        return text

    return TOKEN.sub(one, str(template)).strip()


def _resolve(spec: dict, timeout: int = 30) -> tuple[list | None, str]:
    """The one resolution path both the probe and the fetch walk: validate
    the spec, fetch the JSON document, dig the list out of it.

    Answers (entries, complaint). Entries is None when the source cannot be
    resolved, and the complaint is the line the CHECK button shows -- a
    fetch ignores it and just tries the next source.
    """
    if not isinstance(spec, dict) or not spec.get("image"):
        return None, "no image template"

    document: object = {}
    url = fill(spec.get("url"), {})
    if url:
        try:
            reply = fetch_url(url, timeout=timeout,
                              headers=spec.get("headers"))
        except (urllib.error.URLError, OSError, TimeoutError,
                ValueError) as problem:
            return None, describe(problem)
        try:
            document = json.loads(reply)
        except ValueError:
            return None, "the reply is not JSON"

    if spec.get("list"):
        found = dig(document, spec["list"])
        if not isinstance(found, list) or not found:
            return None, f"nothing to pick from at {spec['list']}"
        return found, ""
    return [document], ""


class Listing(NamedTuple):
    """What one source has to offer today."""

    candidates: list[dict]
    complaint: str     # why there are none, in a line; "" when there are


def list_source(_name: str, spec: dict, timeout: int = 30) -> Listing:
    """Every usable entry from one source today. Nothing is downloaded.

    Each candidate is filled -- image, title, credit, link, date, ident --
    after `require` and `replace` have been applied, so the gallery never
    offers a thumb it could not later adopt. A source with nothing to offer
    says why in the complaint.

    A source still holding its key placeholder is not asked: the request
    would carry the placeholder to the API as if it were a key.
    """
    if needs_setup(spec):
        return Listing([], "needs a key")
    entries, complaint = _resolve(spec, timeout)
    if entries is None:
        return Listing([], complaint)

    demands = spec.get("require")
    demands = demands if isinstance(demands, dict) else {}
    out = []
    for entry in entries:
        if any(str(dig(entry, key)) != str(want)
               for key, want in demands.items()):
            continue

        src = fill(spec["image"], entry)
        if not src:
            continue
        swap = spec.get("replace")
        if isinstance(swap, (list, tuple)) and len(swap) == _REPLACE_PAIR_LEN:
            with contextlib.suppress(re.error):
                src = re.sub(str(swap[0]), str(swap[1]), src)

        title = fill(spec.get("title"), entry)
        # Try each in turn rather than taking the first non-empty one: a title
        # written in Japanese is not empty but slugifies to nothing, and two
        # of those in a day would land on the same filename.
        ident = ""
        for candidate in (fill(spec.get("id"), entry), title,
                          Path(urllib.parse.urlparse(src).path).stem):
            ident = slugify(candidate)
            if ident:
                break
        out.append({
            "image": src,
            "title": title,
            "credit": fill(spec.get("credit"), entry),
            "link": fill(spec.get("link"), entry),
            "date": fill(spec.get("date"), entry),
            "ident": ident,
        })
    return Listing(out, "" if out else "nothing to offer today")


def _floor(spec: dict, key: str) -> float:
    """A numeric demand of the source, 0 when it makes none."""
    try:
        return float(spec.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def refusal(spec: dict, size: tuple[int, int] | None) -> str:
    """Why a photograph of this size is not worth keeping from this source,
    in a few words, or "" when it is.

    One too small to cover the screen is worse than none (`min_width`), and
    so is one whose shape `cover` would crop to a strip: a square or a
    portrait on a landscape screen (`min_aspect`, width over height).
    """
    narrowest, squarest = _floor(spec, "min_width"), _floor(spec, "min_aspect")
    if not (narrowest or squarest):
        return ""
    if size is None:
        return "can't tell its size"
    width, height = size
    if width < narrowest:
        return f"too small: {width} px"
    if width < squarest * height:
        return f"not wide enough: {width} \u00d7 {height}"
    return ""


def remote_size(url: str, timeout: int) -> tuple[int, int] | None:
    """Width and height of the photograph at a URL, read from its first
    bytes alone; None when those do not say. FetchError when they never
    came."""
    return measure_stream(io.BytesIO(fetch_head(url, _HEAD_BYTES, timeout)))


def _refusal_at(spec: dict, url: str, timeout: int) -> str:
    try:
        return refusal(spec, remote_size(url, timeout))
    except FetchError:
        # Not knowing is not a reason: the tile and the click will say
        # what is wrong with a URL that does not answer.
        return ""


def offer_source(name: str, spec: dict, timeout: int = 30) -> Listing:
    """What the gallery shows from one source: list_source, less every
    candidate that adopt would refuse for its size once downloaded.

    Only the first bytes of each are fetched to find out, and only when the
    source states a size it needs, so a source without one costs nothing
    more than its listing.
    """
    listing = list_source(name, spec, timeout)
    if not listing.candidates or not (
            _floor(spec, "min_width") or _floor(spec, "min_aspect")):
        return listing

    with ThreadPoolExecutor(max_workers=_SIZING_THREADS) as pool:
        refusals = list(pool.map(
            partial(_refusal_at, spec, timeout=timeout),
            [cand["image"] for cand in listing.candidates]))
    fitting = [cand for cand, why in zip(listing.candidates, refusals,
                                         strict=True) if not why]
    if fitting:
        return Listing(fitting, "")
    return Listing([], f"nothing fits today ({refusals[0]})")


def adopt(name: str, spec: dict, cand: dict) -> Path:
    """Download one candidate into the collection and remember who made it.

    Same filename rules as the daily fetch: {day}-{name}-{ident}{suffix},
    with the day read back out of the candidate's own date. FetchError,
    saying why, when it was not kept.
    """
    src = cand.get("image") or ""
    if not src:
        msg = "no image to fetch"
        raise FetchError(msg)
    ident = cand.get("ident") or time.strftime("%H%M%S")
    day = re.sub(r"\D", "", str(cand.get("date") or ""))
    if len(day) != _YYYYMMDD_LEN:
        day = time.strftime("%Y%m%d")
    suffix = Path(urllib.parse.urlparse(src).path).suffix or ".jpg"
    out = DIR / f"{day}-{name}-{ident}{suffix}"
    if out.exists():
        msg = "already in the collection"
        raise FetchError(msg)
    download(src, out)

    complaint = refusal(spec, measure(out))
    if complaint:
        out.unlink(missing_ok=True)
        raise FetchError(complaint)

    remember(out.name, cand.get("title") or "", cand.get("credit") or "",
             cand.get("link") or "")
    return out


def fetch_source(name: str, spec: dict) -> Path | None:
    """Run one source described entirely by config: list, pick one, keep it.

    That covers every shipped one and, more to the point, the next one --
    adding a source is writing an object, not editing this file.
    """
    cands = list_source(name, spec).candidates
    if not cands:
        return None

    # Start somewhere random and walk, so a folder full of past picks doesn't
    # make a list source give up on its first collision.
    start = random.randrange(len(cands))
    for step in range(len(cands)):
        cand = cands[(start + step) % len(cands)]
        with contextlib.suppress(FetchError):
            return adopt(name, spec, cand)
    return None


def probe_source(_name: str, spec: dict) -> tuple[bool, str]:
    """Ask a source what it has today, without downloading it.

    Answers (worked, one line you can read). A source can fail in a dozen
    quiet ways -- an expired key, a moved JSON path, a day with a video
    instead of a photograph -- and all of them look identical from outside:
    the wallpaper just doesn't change. This makes them say so.

    The resolution is _resolve, the same path a fetch walks; only what
    happens with the answer differs -- a probe reads it, a fetch keeps it.
    """
    entries, complaint = _resolve(spec, timeout=20)
    if entries is None:
        return False, complaint

    entry = entries[0]
    src = fill(spec["image"], entry)
    if not src:
        return False, f"no photograph in the reply ({spec['image']})"
    if not src.startswith("http"):
        return False, f"not a URL: {src[:50]}"
    detail = fill(spec.get("title"), entry) or fill(spec.get("credit"), entry)
    detail = detail[:48]
    if len(entries) > 1:
        more = f"{len(entries)} to choose from"
        detail = f"{detail} \u00b7 {more}" if detail else more
    return True, detail or "has a photograph today"


def host(url) -> str:
    """A source you wrote yourself has no blurb, so it gets its host."""
    try:
        return urllib.parse.urlparse(str(url)).netloc or "a source of your own"
    except ValueError:
        return "a source of your own"
