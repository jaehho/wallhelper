"""The collection on disk: what is in it, what each photo is, what goes.

The three durable pieces are the folder itself, kept/ (hardlinks, so keeping a
photo costs nothing and survives the sweep) and .credits (who took it). Nothing
in here knows about a window or a command line.
"""

from __future__ import annotations

import re
import struct
import subprocess
import unicodedata
from pathlib import Path

from .desktop import active, focused_monitor, push_wallpaper
from .paths import CREDITS, CURRENT, DIR, IMAGE_SUFFIXES, KEPT, THUMBS


def slugify(text: str, limit: int = 44) -> str:
    """A filename fragment that survives a foreign title and stays readable."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    out = "".join(char if char.isalnum() else "-" for char in plain)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:limit]


# --- sources --------------------------------------------------------------


def images(folder: Path) -> list[Path]:
    try:
        return sorted(
            (p for p in folder.iterdir()
             if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda p: p.name, reverse=True,
        )
    except OSError:
        return []


def collection() -> list[Path]:
    """Everything on offer, newest name first: the photos you kept, plus
    whatever else is in the folder. A photo kept months ago outlives its daily
    copy, so this is a union rather than one directory listing."""
    seen = {path.name: path for path in images(KEPT)}
    seen.update({path.name: path for path in images(DIR)})
    return [seen[name] for name in sorted(seen, reverse=True)]


def trash(path: Path) -> bool:
    """Send to the desktop wastebasket, not unlink.

    A person deleting a photograph can change their mind; the automatic sweep
    below unlinks outright because that is housekeeping nobody chose."""
    try:
        done = subprocess.run(["gio", "trash", str(path)],
                              capture_output=True, timeout=15, check=False)
        if done.returncode == 0:
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        path.unlink()              # no gio, no trash -- still honour the ask
        return True
    except OSError:
        return False


# --- credits --------------------------------------------------------------


def credits() -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    try:
        for line in CREDITS.read_text().splitlines():
            parts = line.split("\t")
            if parts and parts[0]:
                out[parts[0]] = tuple((parts + ["", "", ""])[1:4])  # type: ignore[assignment]
    except OSError:
        pass
    return out


def remember(name: str, title: str, byline: str, url: str) -> None:
    """Idempotent: re-downloading a file must not add a second line for it."""
    if name in credits():
        return
    with CREDITS.open("a") as fh:
        fh.write(f"{name}\t{title}\t{byline}\t{url}\n")


# --- what's on screen -----------------------------------------------------


def canonical(path: Path) -> Path:
    """kept/ holds hardlinks, so a kept photo has two paths to one inode. Always
    prefer the one in the folder proper: displaying the kept/ path means
    `like --undo` would unlink the very file on screen."""
    if path.parent == KEPT and (DIR / path.name).is_file():
        return DIR / path.name
    return path


def current_image() -> Path | None:
    """The wallpaper on the focused monitor, else any displayed one, else
    whatever .current points at (hyprpaper may not be running)."""
    shown = active()
    if shown:
        name = focused_monitor()
        path = shown.get(name) if name else None
        path = path or next(iter(shown.values()))
        if path and Path(path).is_file():
            return canonical(Path(path))
    if CURRENT.is_file():
        return CURRENT.resolve()
    return None


# --- the caption plate ----------------------------------------------------
#
# A wall label, not a form. The photograph's own title first, then where it
# was taken, then an accession line: date, source, photographer. The sources
# don't hand us those fields separately, so this is where they get separated.


CREDIT_RE = re.compile(r"^(.*?)\s*\(\s*©\s*(.+?)\s*\)\s*$")


def stamp(name: str) -> tuple[str, str]:
    """Filename -> ('2026·09·02', 'bing'). Both halves are optional: a photo
    you dropped in by hand has neither, and the plate just omits them.

    The source is read by position rather than matched against a list of known
    names -- sources are config now, so there is no list to match against.
    """
    parts = Path(name).stem.split("-")
    date = ""
    if parts and len(parts[0]) == 8 and parts[0].isdigit():
        first = parts[0]
        date = f"{first[:4]}·{first[4:6]}·{first[6:8]}"
    else:
        return "", ""
    # Old names were YYYYMMDD-HHMMSS-source; new ones are YYYYMMDD-source-id.
    for candidate in parts[1:3]:
        if candidate and not candidate.isdigit():
            return date, candidate.lower()
    return date, ""


def label(path: Path | None) -> dict[str, str]:
    """Split what the sources give us into the fields a label actually has."""
    if path is None:
        return {}
    known = credits()
    title, credit, url = known.get(path.name, ("", "", ""))
    date, source = stamp(path.name)
    kept = (KEPT / path.name).exists()

    # 'wallhaven 7jlq13' is a filename wearing a title's clothes. Better to
    # show no title than a fake one -- the accession line already says where
    # this came from, which is all that string ever meant.
    if title.lower().startswith("wallhaven "):
        title = ""

    # Bing glues place and photographer together:
    #   'Beach huts, Southwold, England (© stevendocwra/Getty Images)'
    match = CREDIT_RE.match(credit)
    place, author = (match.group(1), match.group(2)) if match else ("", credit)

    # A photographer credited as 'wallhaven.cc' only repeats the source token.
    if author and source and author.lower().split(".")[0] == source:
        author = ""

    return {
        "file": str(path), "title": title, "place": place, "date": date,
        "source": source, "author": author, "url": url,
        "kept": "yes" if kept else "no",
        "ours": "yes" if path.name in known else "no",
    }


# --- setting --------------------------------------------------------------


def measure(path: Path) -> tuple[int, int] | None:
    """Width and height straight out of the file header.

    GdkPixbuf.get_file_info sniffs a file by handing it to every loader in
    turn, which measured at 127ms on a 4K JPEG -- longer than decoding the
    photograph. Reading the two headers the sources actually hand us takes
    microseconds. Anything else falls back to the slow path in the window.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
                width, height = struct.unpack(">II", head[16:24])
                return int(width), int(height)
            if head[:2] != b"\xff\xd8":
                return None
            handle.seek(2)
            while True:
                marker = handle.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                length = struct.unpack(">H", handle.read(2))[0]
                # SOF0-SOF15 carry the frame size; DHT/JPG/DAC sit among them.
                if (0xC0 <= marker[1] <= 0xCF
                        and marker[1] not in (0xC4, 0xC8, 0xCC)):
                    height, width = struct.unpack(">HH", handle.read(5)[1:5])
                    return int(width), int(height)
                handle.seek(length - 2, 1)
    except (OSError, struct.error, ValueError, IndexError):
        return None


def set_wallpaper(image: Path, push: bool = True) -> None:
    """Repoint .current (durable) and push to every output (immediate).

    hyprpaper 0.8's empty-monitor wildcard -- `wallpaper ",path"` -- is accepted
    over IPC and silently does nothing, so each output has to be named. Resolve
    first: .current must not point at another symlink, or pruning the middle
    link leaves it dangling.
    """
    image = canonical(image).resolve(strict=True)
    DIR.mkdir(parents=True, exist_ok=True)

    tmp = CURRENT.with_name(CURRENT.name + ".new")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(image)
    tmp.replace(CURRENT)          # atomic: never a window with no .current

    if push:
        push_wallpaper(image)


# --- pruning --------------------------------------------------------------


def sweep(spare: Path | None = None) -> list[str]:
    """A photo you didn't keep goes when the next one arrives. No countdown,
    and no way to switch it off -- keeping something is the only signal,
    so a second one would just be a way to make the first mean nothing.

    Three things are never touched. Files not in .credits, because we didn't
    download them -- an earlier version deleted by age alone and wiped a
    twelve-image hand-built library on its first run, since every file in it
    was older than the cutoff. Photos you kept, which is the whole point.
    And whatever is on screen or under .current, because hyprpaper resolves
    that symlink at startup and a dangling one means no wallpaper at the next
    login.
    """
    known = credits()
    if not known:
        return []

    spared = {Path(path).resolve() for path in active().values()}
    if CURRENT.is_symlink():
        spared.add(CURRENT.resolve())
    if spare is not None:
        spared.add(spare.resolve())

    removed = []
    for path in images(DIR):
        if path.name not in known or path.resolve() in spared:
            continue
        if (KEPT / path.name).exists():
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            pass
    forget(removed)
    return removed


def forget(names: list[str]) -> None:
    """Drop ledger lines whose file is gone from both folders, so .credits
    doesn't outgrow the collection it describes."""
    if not names:
        return
    gone = {name for name in names
            if not (DIR / name).exists() and not (KEPT / name).exists()}
    if not gone:
        return
    for name in gone:
        (THUMBS / f"{name}.png").unlink(missing_ok=True)
    try:
        kept = [line for line in CREDITS.read_text().splitlines()
                if line.split("\t")[0] not in gone]
        tmp = CREDITS.with_name(CREDITS.name + ".new")
        tmp.write_text("".join(line + "\n" for line in kept))
        tmp.replace(CREDITS)
    except OSError:
        pass
