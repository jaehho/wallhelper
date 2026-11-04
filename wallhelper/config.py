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
# `autofetch` -- there is no code to change.
#
# `autofetch` is what the morning timer pulls: bing, and nothing else is
# shipped.
DEFAULTS = {
    "autofetch": ["bing"],
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
    """Reading order, not alphabetical order: the name list first, then
    each source's own settings in the order they are used, then the rest of
    the shipped ones, then anything you added yourself."""
    out = {}
    if "autofetch" in cfg:
        out["autofetch"] = cfg["autofetch"]
    for name in list(cfg.get("autofetch") or []) + list(DEFAULTS):
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
    """Old `sources` meant "enabled for fetch". Morning is bing-only now,
    and wallhaven is gone; a stock wallhaven body goes with it."""
    if "sources" not in stored:
        return stored
    if stored.get("wallhaven") == _OLD_WALLHAVEN:
        stored.pop("wallhaven", None)
    old = [name for name in (stored.pop("sources") or [])
           if isinstance(name, str)]
    body = stored.get("bing")
    if "bing" in old or (isinstance(body, dict) and body.get("image")):
        stored["autofetch"] = ["bing"]
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


def _named(cfg: dict, key: str) -> list[str]:
    return [name for name in (cfg.get(key) or [])
            if isinstance(cfg.get(name), dict) and cfg[name].get("image")]


def autofetch_sources() -> list[str]:
    """The morning list: names that actually describe a source."""
    return _named(config(), "autofetch")

