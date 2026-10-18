"""The commands. One per thing you can ask wallhelper to do."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import migrate
from .desktop import notify
from .library import (
    TRASHED,
    current_image,
    delete_photo,
    images,
    in_collection,
    is_image,
    label,
    migrate_collection,
    set_wallpaper,
)
from .morning import FAILED, UNSET, fetch_morning
from .paths import DIR

# --- commands -------------------------------------------------------------


def cmd_fetch(args) -> int:
    run = fetch_morning()

    # A user timer cannot reliably order itself after the network is up:
    # network-online.target belongs to the system manager and nothing in the
    # user manager pulls it in. The unit fired at login on 2026-09-03 and
    # -09-04, both sources failed on DNS, and those days simply had no photo.
    # Retrying beats pretending the ordering works. Only the timer waits.
    for delay in (30, 60, 120, 240) if args.wait else ():
        if run.kind != FAILED:
            break
        print(f"wallhelper: no source answered; retrying in {delay}s",
              file=sys.stderr)
        time.sleep(delay)
        run = fetch_morning()

    if run.ok:
        print(f"wallhelper: {run.message}")
        return 0

    # Exit non-zero so systemd marks the unit failed and it shows up in
    # `make status`; silence here is how the tool this replaced stayed
    # broken from April to September. A toast on every flaky-wifi failure
    # would train you to ignore it, so only an empty pool escalates, and a
    # morning with no source to ask.
    print(f"wallhelper: {run.message}", file=sys.stderr)
    if run.kind == UNSET:
        notify("Wallhelper", run.message, urgent=True)
    elif not images(DIR):
        notify("Wallhelper", f"{run.message} \u2014 and none are on disk",
               urgent=True)
    return 1


def cmd_set(args) -> int:
    path = Path(args.image).expanduser()
    if not path.is_file():
        print(f"wallhelper: no such image: {args.image}", file=sys.stderr)
        return 1
    # .current is what hyprpaper reads at boot, and `delete` acts on
    # whatever it ends up pointing at: both want a photograph in the
    # collection, not a text file or a copy in ~/Downloads.
    if not is_image(path):
        print(f"wallhelper: not an image: {args.image}", file=sys.stderr)
        return 1
    if not in_collection(path):
        print(f"wallhelper: {args.image} is outside the collection "
              f"({DIR}); copy it in first", file=sys.stderr)
        return 1
    set_wallpaper(path)
    return 0


def cmd_delete(_args) -> int:
    """Send the photo on screen to the Trash, and move on to its neighbour."""
    path = current_image()
    if path is None:
        print("wallhelper: no active wallpaper", file=sys.stderr)
        return 1

    try:
        gone = delete_photo(path)
    except ValueError as err:
        notify("Not deleted", str(err))
        print(f"wallhelper: {err}", file=sys.stderr)
        return 1
    except OSError:
        notify("Couldn't delete", path.name)
        print(f"wallhelper: couldn't delete {path.name}", file=sys.stderr)
        return 1

    if gone.how == TRASHED:
        notify("Moved to Trash", gone.title)
        print(f"Moved to Trash: {gone.title}")
    else:
        # The Trash would not take it, so there is nothing to restore from.
        notify("Deleted for good", f"{gone.title} \u2014 the Trash refused it")
        print(f"Deleted for good, the Trash refused it: {gone.title}")
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

    p = sub.add_parser("set", help="make a photo in the collection the "
                                   "wallpaper")
    p.add_argument("image")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("delete", help="send what's on screen to the Trash")
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
