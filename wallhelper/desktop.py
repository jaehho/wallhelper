"""Talking to the desktop: notifications, Hyprland, hyprpaper.

Everything here shells out, so everything here is a process spawn, which is why
the monitor list is cached and why the wallpaper push is something the window
does off the main thread.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

# --- plumbing -------------------------------------------------------------


def notify(summary: str, body: str = "", urgent: bool = False) -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "Wallpaper",
             "-u", "critical" if urgent else "low", summary, body],
            check=False, capture_output=True,
        )
    except OSError:
        pass


def hyprctl(*args: str) -> str:
    try:
        out = subprocess.run(
            ["hyprctl", *args], capture_output=True, text=True, timeout=10,
            check=False,
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


_MONITORS: tuple[float, list[str]] = (0.0, [])


def monitors() -> list[str]:
    """Cached briefly. Every hyprctl call is a process spawn, and setting a
    wallpaper asks for this list each time -- which made holding an arrow key
    down spawn a process per frame. Short enough that a hotplug still lands."""
    global _MONITORS
    when, names = _MONITORS
    if names and time.monotonic() - when < 5:
        return names
    try:
        names = [m["name"]
                 for m in json.loads(hyprctl("monitors", "-j") or "[]")]
    except (json.JSONDecodeError, KeyError, TypeError):
        names = []
    _MONITORS = (time.monotonic(), names)
    return names


def focused_monitor() -> str | None:
    try:
        for m in json.loads(hyprctl("monitors", "-j") or "[]"):
            if m.get("focused"):
                return m["name"]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def active() -> dict[str, str]:
    """monitor -> displayed image path, from hyprpaper."""
    out = {}
    for line in hyprctl("hyprpaper", "listactive").splitlines():
        name, sep, path = line.partition(":")
        if sep and path.strip():
            out[name.strip()] = path.strip()
    return out


def push_wallpaper(image: Path) -> None:
    """hyprpaper decodes the photograph before it answers, so this blocks for
    the best part of a tenth of a second. The window runs it off the main
    loop; the CLI just waits."""
    for name in monitors():
        hyprctl("hyprpaper", "wallpaper", f"{name},{image}")
