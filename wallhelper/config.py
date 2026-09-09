"""The shipped sources, and your changes to them.

Settings live here rather than in a dotfile because the window can change them,
and a stowed dotfile is a symlink into a git repo: writing to it from a GUI
would mean the app editing the repo behind your back. Defaults are code, your
deltas are JSON, and a missing or corrupt file just means defaults.
"""

from __future__ import annotations

import json

from .paths import CONFIG, KEPT, LEGACY_KEPT

# Settings the window can change, which is why they are not in this file. A
# stowed dotfile is a symlink into the git repo; writing to it from a GUI would
# mean the app editing the repo behind your back. Defaults live here, the
# deltas live in CONFIG, and a missing or corrupt CONFIG just means defaults.
#
# Nothing below is a fixed vocabulary. Both sources take their parameters
# straight from here -- wallhaven's is the raw query string, so every
# parameter its API accepts works whether or not this file mentions it -- and
# config() keeps any key you add that isn't listed.
# Every source is data. The engine below fetches `url`, optionally picks an
# entry out of the array at `list`, then fills these templates from it:
# {some.json.path} anywhere in a string, plus {date:%Y%m%d} from the clock.
# Adding a source means adding one of these objects and putting its name in
# `sources` -- there is no code to change.
DEFAULTS = {
    "sources": ["bing", "wallhaven"],
    "bing": {
        "url": "https://www.bing.com/HPImageArchive.aspx"
               "?format=js&idx=0&n=1&mkt=en-US",
        "list": "images",
        "image": "https://www.bing.com{urlbase}_UHD.jpg",
        "title": "{title}",
        "credit": "{copyright}",
        # Bing's own caption links here: a search for the subject, per photo.
        # The front page is not a link to today's picture, it is a link to
        # tomorrow's.
        "link": "{copyrightlink}",
        "date": "{startdate}",
    },
    "wallhaven": {
        "url": "https://wallhaven.cc/api/v1/search"
               "?categories=100&purity=100&atleast=2560x1440"
               "&sorting=toplist&topRange=1M",
        "list": "data",
        "image": "{path}",
        "id": "{id}",
        "credit": "wallhaven.cc",
        "link": "https://wallhaven.cc/w/{id}",
    },
    "apod": {
        "url": "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY",
        "image": "{hdurl}",
        "title": "{title}",
        "credit": "{copyright}",
        # astropix.html is whatever is newest; apYYMMDD.html is this one.
        "link": "https://apod.nasa.gov/apod/ap{date:%y%m%d}.html",
        "require": {"media_type": "image"},
        "date": "{date}",
        "min_width": 1920,
    },
    "wikipedia": {
        "url": "https://en.wikipedia.org/api/rest_v1/feed/featured"
               "/{date:%Y/%m/%d}",
        "image": "{image.thumbnail.source}",
        "replace": ["/[0-9]+px-", "/3840px-"],
        "id": "{image.title|name|stem}",
        "credit": "{image.description.text} (\u00a9 {image.artist.text})",
        "link": "{image.file_page}",
    },
    "unsplash": {
        "url": "https://api.unsplash.com/photos/random"
               "?orientation=landscape&client_id=PASTE_YOUR_ACCESS_KEY",
        "image": "{urls.full}",
        "id": "{id}",
        "title": "{alt_description}",
        "credit": "{user.name}",
        "link": "{links.html}",
        # A source that needs a key says where to get one and what the
        # placeholder is called; the window then offers the link and a box to
        # paste into, and puts the key everywhere the placeholder appears.
        "key": {
            "get": "https://unsplash.com/oauth/applications/new",
            "note": "Register an application \u2014 free, instant, no review "
                    "\u2014 then copy its Access Key.",
            "into": "PASTE_YOUR_ACCESS_KEY",
        },
    },
}


# One line each, shown beside the switch in the window. A source you add
# yourself falls back to its host name, so this is not a registry -- it is
# just the sentence the shipped five deserve.
BLURBS = {
    "bing": "One curated photograph a day, titled and located.",
    "wallhaven": "Community wallpapers. Its url is a raw query you can tune.",
    "apod": "NASA's astronomy picture of the day.",
    "wikipedia": "Wikipedia's picture of the day, fully credited.",
    "unsplash": "Needs a free access key pasted into its url first.",
}


def config() -> dict:
    """DEFAULTS with the stored deltas merged over them, one level deep."""
    out = json.loads(json.dumps(DEFAULTS))
    try:
        stored = json.loads(CONFIG.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return out
    if not isinstance(stored, dict):
        return out
    for key, value in stored.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            # Unlisted keys are kept, not dropped. It is your file.
            out[key] = value
    return out


def ordered(cfg: dict) -> dict:
    """Reading order, not alphabetical order: the list of sources first, then
    each one's own settings in the order they are tried, then the sources you
    could turn on, then anything you added yourself."""
    out = {}
    if "sources" in cfg:
        out["sources"] = cfg["sources"]
    for name in list(cfg.get("sources") or []) + list(DEFAULTS):
        if isinstance(name, str) and name in cfg and name not in out:
            out[name] = cfg[name]
    for key, value in cfg.items():
        out.setdefault(key, value)
    return out


def trim(cfg: dict) -> dict:
    """Keep the difference, not the document.

    Writing the whole merged config back pins every shipped source at whatever
    it looked like the first time you touched a switch -- an old url, a link
    that no longer points at the photograph -- and no later version of this
    tool could correct it, because your file would always win. Only what you
    actually changed belongs in your file.
    """
    out = {}
    for key, value in cfg.items():
        base = DEFAULTS.get(key)
        if base == value:
            continue
        if isinstance(value, dict) and isinstance(base, dict):
            delta = {inner: item for inner, item in value.items()
                     if base.get(inner) != item}
            if delta:
                out[key] = delta
        else:
            out[key] = value
    return out


def save_config(cfg: dict) -> None:
    """Via a tempfile: a half-written config reads as no config at all, and
    the next fetch would silently run on defaults."""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_name(CONFIG.name + ".new")
    tmp.write_text(json.dumps(ordered(trim(cfg)), indent=2) + "\n")
    tmp.replace(CONFIG)


def migrate() -> None:
    """liked/ was the old name for kept/, and an older config held a full copy
    of every shipped source rather than your changes to them."""
    if LEGACY_KEPT.is_dir() and not KEPT.exists():
        try:
            LEGACY_KEPT.rename(KEPT)
        except OSError:
            pass
    try:
        stored = json.loads(CONFIG.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return
    if isinstance(stored, dict) and trim(stored) != stored:
        try:
            save_config(config())
        except OSError:
            pass


def needs_setup(spec: dict) -> str:
    """The placeholder still sitting in the spec, or "".

    A source waiting on a key is indistinguishable from a broken one until you
    read its url, so both the window and the toggle check this rather than
    letting it fail silently at 6am tomorrow.
    """
    if not isinstance(spec, dict):
        return ""
    token = (spec.get("key") or {}).get("into") or "PASTE_YOUR_"
    body = json.dumps({key: value for key, value in spec.items()
                       if key != "key"})
    return token if token in body else ""


def apply_key(spec: dict, token: str, value: str) -> dict:
    """The key goes wherever the placeholder went. Which parameter carries it
    is the source's business -- a query argument for one API, a header for the
    next -- so this replaces the token and asks no further questions."""
    def walk(node):
        if isinstance(node, str):
            return node.replace(token, value)
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, dict):
            return {key: walk(item) for key, item in node.items()}
        return node

    # Everywhere except the block that named the placeholder. Rewriting that
    # too renames the token to the key itself, and needs_setup then finds the
    # key in the url and reports the source as still unconfigured forever.
    setup = spec.get("key")
    out = walk({key: item for key, item in spec.items() if key != "key"})
    if setup is not None:
        out["key"] = setup
    return out


def enabled() -> list[str]:
    """The names in config["sources"] that actually describe a source."""
    cfg = config()
    return [name for name in (cfg.get("sources") or [])
            if isinstance(cfg.get(name), dict) and cfg[name].get("image")]
