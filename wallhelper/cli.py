"""The commands. One per thing you can ask wallhelper to do."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import autofetch_sources, config, migrate
from .desktop import notify
from .library import (
    collection,
    current_image,
    forget,
    images,
    label,
    migrate_collection,
    set_wallpaper,
    trash,
)
from .paths import DIR
from .sources import fetch_source

# --- commands -------------------------------------------------------------


def cmd_fetch(args) -> int:
    DIR.mkdir(parents=True, exist_ok=True)

    # One photo a day from the morning sources. Without this, a second run
    # finds Bing already has today's and downloads a second copy.
    today = time.strftime("%Y%m%d")
    if list(DIR.glob(f"{today}-*")):
        print("wallhelper: already have today's photo")
        return 0

    usable = autofetch_sources()
    if not usable:
        notify("Wallhelper", "no morning source is switched on", urgent=True)
        print("wallhelper: no morning source is switched on", file=sys.stderr)
        return 1

    # A user timer cannot reliably order itself after the network is up:
    # network-online.target belongs to the system manager and nothing in the
    # user manager pulls it in. The unit fired at login on 2026-09-03 and
    # -09-04, both sources failed on DNS, and those days simply had no photo.
    # Retrying beats pretending the ordering works. Only the timer waits.
    new = None
    for delay in (0, *((30, 60, 120, 240) if args.wait else ())):
        if delay:
            print(f"wallhelper: no source answered; retrying in {delay}s",
                  file=sys.stderr)
            time.sleep(delay)
        for name in usable:
            new = fetch_source(name, config()[name])
            if new:
                print(f"wallhelper: {name} -> {new.name}")
                break
        if new:
            break

    if new is None:
        # Exit non-zero so systemd marks the unit failed and it shows up in
        # `make status`; silence here is how the tool this replaced stayed
        # broken from April to September. A toast on every flaky-wifi failure
        # would train you to ignore it, so only an empty pool escalates.
        if not images(DIR):
            notify("Wallhelper", "every source failed and none are on disk",
                   urgent=True)
            print("wallhelper: every source failed and none are on disk",
                  file=sys.stderr)
            return 1
        print("wallhelper: every source failed; keeping what's on disk",
              file=sys.stderr)
        return 1

    set_wallpaper(new)
    return 0


def cmd_set(args) -> int:
    path = Path(args.image).expanduser()
    if not path.is_file():
        print(f"wallhelper: no such image: {args.image}", file=sys.stderr)
        return 1
    set_wallpaper(path)
    return 0


def cmd_delete(_args) -> int:
    """Remove the photo on screen for good, and move on to its neighbour."""
    path = current_image()
    if path is None:
        print("wallhelper: no active wallpaper", file=sys.stderr)
        return 1

    info = label(path)
    shown = info["title"] or path.stem

    # Where it sat in the collection, so what replaces it is its neighbour
    # rather than whatever happens to be oldest. Deleting a run of photos
    # should walk along the grid, not throw you back to the start every time.
    was = [other.name for other in collection()]
    index = was.index(path.name) if path.name in was else 0
    following = [other for other in collection() if other.name != path.name]

    if not trash(path):
        notify("Couldn't delete", path.name)
        print(f"wallhelper: couldn't delete {path.name}", file=sys.stderr)
        return 1

    forget([path.name])
    if following:
        set_wallpaper(following[min(index, len(following) - 1)])
    notify("Deleted", shown)
    print(f"Deleted: {shown}")
    return 0


def cmd_info(args) -> int:
    info = label(current_image())
    if not info:
        print("wallhelper: no active wallpaper", file=sys.stderr)
        return 1
    for key in ("file", "title", "place", "date", "source", "author", "url"):
        print(f"{key + ':':9}{info[key] or 'unknown'}")
    if args.notify:
        body = " · ".join(
            part for part in (info["date"], info["source"].upper(),
                              info["author"]) if part
        ) or "no recorded source"
        notify(info["title"] or Path(info["file"]).stem, body)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wallhelper",
        description="Bing in the morning, and the ones you saved.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="pull the day's photo")
    p.add_argument("-w", "--wait", action="store_true",
                   help="retry for a few minutes if no source answers")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("set", help="make an image the wallpaper")
    p.add_argument("image")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("delete", help="remove what's on screen for good")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("info", help="what's on screen, and where it came from")
    p.add_argument("-n", "--notify", action="store_true",
                   help="also send a desktop notification")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("gui", help="the same thing with pictures")
    p.set_defaults(func=lambda args: __import__(
        "wallhelper.gui", fromlist=["cmd_gui"]).cmd_gui(args))

    args = parser.parse_args()
    migrate()
    migrate_collection()
    return args.func(args)
