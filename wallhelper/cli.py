"""The commands. One per thing you can ask wallhelper to do."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

from .config import config, enabled, migrate
from .desktop import notify
from .library import (
    collection,
    current_image,
    forget,
    images,
    label,
    set_wallpaper,
    sweep,
    trash,
)
from .paths import DIR, KEPT
from .sources import fetch_source

# --- commands -------------------------------------------------------------


def cmd_fetch(args) -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    KEPT.mkdir(parents=True, exist_ok=True)

    # One photo a day, whichever source it came from. Without this, a
    # second run finds Bing already has today's, falls through to wallhaven
    # -- which almost always succeeds -- and stacks up a second image.
    today = time.strftime("%Y%m%d")
    if not args.next and list(DIR.glob(f"{today}-*")):
        print("wallhelper: already have today's photo"
              " (--next to pull another)")
        return 0

    usable = enabled()
    if not usable:
        notify("Wallhelper", "no usable source is switched on", urgent=True)
        print("wallhelper: no usable source is switched on", file=sys.stderr)
        return 1

    # A user timer cannot reliably order itself after the network is up:
    # network-online.target belongs to the system manager and nothing in the
    # user manager pulls it in. The unit fired at login on 2026-09-03 and
    # -09-04, both sources failed on DNS, and those days simply had no photo.
    # Retrying beats pretending the ordering works. Only the timer waits --
    # the window's NEXT button must stay snappy.
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

    for name in sweep(spare=new):
        print(f"wallhelper: deleted {name} (not kept)")

    set_wallpaper(new)
    return 0


def cmd_set(args) -> int:
    path = Path(args.image).expanduser()
    if not path.is_file():
        print(f"wallhelper: no such image: {args.image}", file=sys.stderr)
        return 1
    set_wallpaper(path)
    return 0


def cmd_keep(args) -> int:
    path = current_image()
    if path is None:
        notify("Nothing to keep", "no active wallpaper")
        print("wallhelper: no active wallpaper", file=sys.stderr)
        return 1

    KEPT.mkdir(parents=True, exist_ok=True)
    target = KEPT / path.name
    info = label(path)
    shown = info["title"] or path.stem
    if info["author"]:
        shown += f" \u2014 {info['author']}"

    if args.undo:
        if target.exists():
            # Un-keeping means "let the next sweep have it", not "delete it
            # now". If the daily copy is already gone this link is the last
            # one, and unlinking would destroy the photo outright.
            if target.stat().st_nlink == 1:
                notify("Can't stop keeping this", "it is the only copy left")
                print("wallhelper: this is the only copy left; "
                      "delete it by hand if you really mean to",
                      file=sys.stderr)
                return 1
            target.unlink()
            notify("No longer kept", shown)
            print(f"No longer kept: {shown}")
        else:
            notify("Not kept", path.name)
            print(f"Not kept: {path.name}")
        return 0

    if target.exists():
        notify("Already kept", shown)
        print(f"Already kept: {shown}")
        return 0

    try:
        os.link(path, target)      # hardlink: free, and survives the prune
    except OSError:
        try:
            shutil.copy2(path, target)   # only if kept/ is on another device
        except OSError:
            notify("Couldn't keep", path.name)
            return 1
    notify("Kept", shown)
    print(f"Kept: {shown}")
    return 0


def cmd_delete(_args) -> int:
    """Remove the photo on screen for good, and move on to the next one."""
    path = current_image()
    if path is None:
        print("wallhelper: no active wallpaper", file=sys.stderr)
        return 1

    info = label(path)
    shown = info["title"] or path.stem

    # Where it sat in the strip, so what replaces it is its neighbour rather
    # than whatever happens to be oldest. Deleting a run of photos should walk
    # along the strip, not throw you back to the start of it every time.
    was = [other.name for other in collection()]
    index = was.index(path.name) if path.name in was else 0
    following = [other for other in collection() if other.name != path.name]

    # kept/ and the folder are two names for one inode; both have to go, and
    # the last one has to go last or the file is unreachable halfway through.
    ok = True
    for victim in ((KEPT / path.name), (DIR / path.name), path):
        if victim.exists() and not trash(victim):
            ok = False
    if not ok:
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
    for key in ("file", "title", "place", "date", "source", "author",
                "url", "kept"):
        print(f"{key + ':':9}{info[key] or 'unknown'}")
    if args.notify:
        body = " \u00b7 ".join(
            part for part in (info["date"], info["source"].upper(),
                              info["author"]) if part
        ) or "no recorded source"
        notify(info["title"] or Path(info["file"]).stem, body)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wallhelper",
        description="One new photograph a day, and the ones you kept.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="pull the day's photo")
    p.add_argument("-n", "--next", action="store_true",
                   help="skip today's and pull a different one")
    p.add_argument("-w", "--wait", action="store_true",
                   help="retry for a few minutes if no source answers")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("set", help="make an image the wallpaper")
    p.add_argument("image")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("keep", aliases=["like"], help="keep what's on screen")
    p.add_argument("-u", "--undo", action="store_true", help="stop keeping it")
    p.set_defaults(func=cmd_keep)

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
    return args.func(args)
