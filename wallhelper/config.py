"""The shipped sources, and your changes to them.

Settings live here rather than in a dotfile because the window can change them,
and a stowed dotfile is a symlink into a git repo: writing to it from a GUI
would mean the app editing the repo behind your back. Defaults are code, your
deltas are JSON, and a missing or corrupt file just means defaults.
"""

from __future__ import annotations

import contextlib
import json

from .paths import CONFIG

# Settings the window can change, which is why they are not in this file. A
# stowed dotfile is a symlink into the git repo; writing to it from a GUI would
# mean the app editing the repo behind your back. Defaults live here, the
# deltas live in CONFIG, and a missing or corrupt CONFIG just means defaults.
#
# Nothing below is a fixed vocabulary. Sources take their parameters straight
# from here -- a url is a url, and config() keeps any key you add that isn't
# listed. Every source is data. The engine fetches `url`, optionally picks
# entries out of the array at `list`, then fills these templates from each:
# {some.json.path} anywhere in a string, plus {date:%Y%m%d} from the clock.
# Adding a source means adding one of these objects and naming it in
# `autofetch` or `gallery` -- there is no code to change.
#
# `autofetch` is what the morning timer pulls (bing). `gallery` is what the
# window offers when you want a different wallpaper by hand.
DEFAULTS = {
    "autofetch": ["bing"],
    "gallery": ["apod", "wikipedia", "unsplash"],
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
    "apod": {
        # api.nasa.gov/planetary/apod lost its image fields in the 2026-09
        # WordPress move; this route is the replacement and needs no key.
        "url": "https://science.nasa.gov/wp-json/wp/v2/apod-basic?per_page=8",
        "list": ".",
        "image": "{hdurl}",
        "title": "{title}",
        "credit": "{credit|text}",
        "link": "{permalink}",
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
               "?orientation=landscape&count=12"
               "&client_id=PASTE_YOUR_ACCESS_KEY",
        "list": ".",
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
# just the sentence the shipped ones deserve.
BLURBS = {
    "bing": "One curated photograph a day, titled and located.",
    "apod": "NASA's astronomy picture of the day.",
    "wikipedia": "Wikipedia's picture of the day, fully credited.",
    "unsplash": "Needs a free access key pasted into its url first.",
}


# What wallhaven looked like when it shipped, so migrate() can tell a
# stock body from one you rewrote before dropping the source entirely.
_OLD_WALLHAVEN = {
    "url": "https://wallhaven.cc/api/v1/search"
           "?categories=100&purity=100&atleast=2560x1440"
           "&sorting=toplist&topRange=1M",
    "list": "data",
    "image": "{path}",
    "id": "{id}",
    "credit": "wallhaven.cc",
    "link": "https://wallhaven.cc/w/{id}",
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
    """Reading order, not alphabetical order: the two name lists first, then
    each source's own settings in the order they are used, then the rest of
    the shipped ones, then anything you added yourself."""
    out = {}
    for key in ("autofetch", "gallery"):
        if key in cfg:
            out[key] = cfg[key]
    for name in list(cfg.get("autofetch") or []) \
            + list(cfg.get("gallery") or []) + list(DEFAULTS):
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


def _rewrite_lists(stored: dict) -> dict:
    """Old `sources` meant "enabled for fetch". Morning is bing-only now;
    the rest of what you had on becomes the elsewhere gallery."""
    if "sources" not in stored:
        return stored
    if stored.get("wallhaven") == _OLD_WALLHAVEN:
        stored.pop("wallhaven", None)
    old = [name for name in (stored.pop("sources") or [])
           if isinstance(name, str) and name != "wallhaven"]
    body = {key: value for key, value in stored.items()
            if isinstance(value, dict) and value.get("image")}
    auto = [name for name in old if name == "bing"] or (
        ["bing"] if body.get("bing") else [])
    gallery: list[str] = []
    for name in list(DEFAULTS.get("gallery") or []) + old:
        if name in auto or name in gallery or name == "wallhaven":
            continue
        if body.get(name) or (name in DEFAULTS and name != "bing"):
            gallery.append(name)
    if auto:
        stored["autofetch"] = auto
    if gallery:
        stored["gallery"] = gallery
    return stored


def migrate() -> None:
    """One-shot repairs for configs written by an older wallhelper."""
    try:
        stored = json.loads(CONFIG.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return
    if not isinstance(stored, dict):
        return
    rewritten = _rewrite_lists(json.loads(json.dumps(stored)))
    if rewritten != stored:
        with contextlib.suppress(OSError):
            CONFIG.write_text(json.dumps(rewritten))
        stored = rewritten
    if trim(stored) != stored:
        with contextlib.suppress(OSError):
            save_config(config())


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


def _named(cfg: dict, key: str) -> list[str]:
    return [name for name in (cfg.get(key) or [])
            if isinstance(cfg.get(name), dict) and cfg[name].get("image")]


def autofetch_sources() -> list[str]:
    """The morning list: names that actually describe a source."""
    return _named(config(), "autofetch")


def gallery_sources() -> list[str]:
    """The elsewhere list: names that actually describe a source."""
    return _named(config(), "gallery")
