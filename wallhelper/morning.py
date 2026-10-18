"""The morning fetch: what the timer runs and what F in the window runs.

It walks the morning sources until one gives a photograph, and says what
came of it in an Outcome. The command prints that and the window toasts
it. Either way it is also written to LAST_FETCH, because the run is
usually unattended and the next look at the panel is where a broken
source is supposed to say so.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import NamedTuple

from .config import autofetch_sources, config
from .library import set_wallpaper
from .paths import DIR, LAST_FETCH
from .sources import fetch_source

SAVED = "saved"      # a new photograph, now the wallpaper
HELD = "held"        # the source's photograph is one the collection has
TODAY = "today"      # today's is already here, so nobody was asked
FAILED = "failed"    # no source gave a photograph
UNSET = "unset"      # no morning source is switched on
KINDS = (SAVED, HELD, TODAY, FAILED, UNSET)


class Outcome(NamedTuple):
    """What a morning fetch came to."""

    kind: str
    source: str          # whose photograph; after a failure, who was asked
    message: str         # one line, naming the source where there is one
    photo: Path | None = None
    when: str = ""       # local time it ran, once recorded

    @property
    def ok(self) -> bool:
        return self.kind not in (FAILED, UNSET)


def record(run: Outcome) -> Outcome:
    """Leave the run where the panel will find it, and hand it back.

    Via a tempfile, like the config: a half-written note reads as no
    note. A state directory that cannot be written to is not a reason for
    a fetch to fail.
    """
    run = run._replace(when=time.strftime("%Y-%m-%dT%H:%M:%S"))
    note = {"when": run.when, "kind": run.kind, "source": run.source,
            "message": run.message,
            "photo": run.photo.name if run.photo else ""}
    try:
        LAST_FETCH.parent.mkdir(parents=True, exist_ok=True)
        tmp = LAST_FETCH.with_name(LAST_FETCH.name + ".new")
        tmp.write_text(json.dumps(note, indent=2) + "\n")
        tmp.replace(LAST_FETCH)
    except OSError:
        pass
    return run


def last_run() -> Outcome | None:
    """The run record() left, or None when there is none to believe."""
    try:
        note = json.loads(LAST_FETCH.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(note, dict):
        return None
    fields = [note.get(key) for key in
              ("kind", "source", "message", "photo", "when")]
    if not all(isinstance(item, str) for item in fields):
        return None
    kind, source, message, photo, when = fields
    if kind not in KINDS or not when:
        return None
    return Outcome(kind, source, message, DIR / photo if photo else None,
                   when)


def headline(run: Outcome) -> str:
    """The run in a line for the panel."""
    day = run.when[:10].replace("-", "·")
    if not run.ok:
        return f"Last fetch {day} failed: {run.message}"
    if run.kind == SAVED:
        return f"Last fetch {day}: {run.source}"
    return f"Last fetch {day}: {run.source}, nothing new"


def todays(usable: list[str]) -> Outcome | None:
    """The photograph the last run kept, when it is today's and still here.

    This is what stops a second run the same day from asking again, and it
    is keyed on the run, not on what the folder happens to hold: an
    Elsewhere pick dated today is not the morning's photograph. A photo
    named for an earlier day (Bing has not rolled over yet) is not today's
    either, and is left to the source to say it already has.
    """
    last = last_run()
    if (last is None or not last.ok or last.source not in usable
            or last.photo is None or not last.photo.is_file()
            or not last.photo.name.startswith(time.strftime("%Y%m%d-"))):
        return None
    return Outcome(TODAY, last.source, "already have today's photo",
                   last.photo)


def fetch_morning() -> Outcome:
    """One photograph a day from the morning sources: ask each in turn
    until one has a photograph, and set it as the wallpaper."""
    DIR.mkdir(parents=True, exist_ok=True)

    usable = autofetch_sources()
    if not usable:
        return record(Outcome(UNSET, "", "no morning source is switched on"))

    # Without this, a second run finds Bing already has today's and asks
    # again for nothing. The source would say so, too: that is HELD.
    if (kept := todays(usable)) is not None:
        return kept

    why: dict[str, str] = {}
    for name in usable:
        got = fetch_source(name, config()[name])
        if got.path is None:
            why[name] = got.why
        elif got.new:
            set_wallpaper(got.path)
            return record(Outcome(SAVED, name, f"{name} -> {got.path.name}",
                                  got.path))
        else:
            return record(Outcome(
                HELD, name, f"{name} \u2014 already have this photograph",
                got.path))

    return record(Outcome(FAILED, ", ".join(usable), "; ".join(
        f"{name} \u2014 {reason}" for name, reason in why.items())))
