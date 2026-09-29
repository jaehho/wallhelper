"""A source is data, not code.

Fetch one JSON document, optionally pick an entry out of an array inside it,
and fill a handful of templates from that entry. Every shipped source is
written in this language, which means adding one is a config edit and the
window can offer to test it.
"""

from __future__ import annotations

import contextlib
import json
import random
import re
import time
import urllib.error
import urllib.parse
from pathlib import Path

from .library import measure, remember, slugify
from .net import download, fetch_url
from .paths import DIR

_REPLACE_PAIR_LEN = 2
_YYYYMMDD_LEN = 8


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

    A path may be followed by filters: {a.b|name|stem}. Values pulled out of
    APIs are so often filenames or namespaced titles ('File:Tallinn ....jpg')
    that trimming them needed to be sayable in the template rather than in
    here.
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
        return text

    return TOKEN.sub(one, str(template)).strip()


def fetch_source(name: str, spec: dict) -> Path | None:  # noqa: PLR0912 — one entry per config key
    """Run one source described entirely by config.

    Every source is data now: fetch a JSON document, optionally pick an entry
    out of a list inside it, then fill a handful of templates from that entry.
    That covers the five shipped ones and, more to the point, the next one --
    adding a source is writing an object, not editing this file.
    """
    if not isinstance(spec, dict) or not spec.get("image"):
        return None

    document = {}
    url = fill(spec.get("url"), {})
    if url:
        try:
            document = json.loads(fetch_url(url, headers=spec.get("headers")))
        except (urllib.error.URLError, OSError, TimeoutError,
                json.JSONDecodeError, ValueError):
            return None

    entries = [document]
    if spec.get("list"):
        found = dig(document, spec["list"])
        if not isinstance(found, list) or not found:
            return None
        entries = found

    demands = spec.get("require")
    demands = demands if isinstance(demands, dict) else {}
    try:
        floor = int(spec.get("min_width") or 0)
    except (TypeError, ValueError):
        floor = 0

    # Start somewhere random and walk, so a folder full of past picks doesn't
    # make a list source give up on its first collision.
    start = random.randrange(len(entries))
    for step in range(len(entries)):
        entry = entries[(start + step) % len(entries)]
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
        ident = ident or time.strftime("%H%M%S")
        # The prefix has to be eight digits or stamp() cannot read it back,
        # and APIs hand out dates in every punctuation they can think of.
        day = re.sub(r"\D", "", fill(spec.get("date"), entry))
        if len(day) != _YYYYMMDD_LEN:
            day = time.strftime("%Y%m%d")
        suffix = Path(urllib.parse.urlparse(src).path).suffix or ".jpg"
        out = DIR / f"{day}-{name}-{ident}{suffix}"
        if out.exists() or not download(src, out):
            continue

        # A photograph too small to cover the screen is worse than none: fall
        # through to the next source rather than stretch it.
        size = measure(out)
        if floor and (size is None or size[0] < floor):
            out.unlink(missing_ok=True)
            continue

        remember(out.name, title, fill(spec.get("credit"), entry),
                 fill(spec.get("link"), entry))
        return out
    return None


def probe_source(_name: str, spec: dict) -> tuple[bool, str]:  # noqa: PLR0911 — one return per failure
    """Ask a source what it has today, without downloading it.

    Answers (worked, one line you can read). A source can fail in a dozen
    quiet ways -- an expired key, a moved JSON path, a day with a video
    instead of a photograph -- and all of them look identical from outside:
    the wallpaper just doesn't change. This makes them say so.
    """
    if not isinstance(spec, dict) or not spec.get("image"):
        return False, "no image template"
    document = {}
    url = fill(spec.get("url"), {})
    if url:
        try:
            document = json.loads(fetch_url(url, timeout=20,
                                            headers=spec.get("headers")))
        except (urllib.error.URLError, OSError, TimeoutError) as problem:
            return False, str(getattr(problem, "reason", problem))[:70]
        except (json.JSONDecodeError, ValueError):
            return False, "the reply is not JSON"

    entries = [document]
    if spec.get("list"):
        found = dig(document, spec["list"])
        if not isinstance(found, list) or not found:
            return False, f"nothing to pick from at {spec['list']}"
        entries = found

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
