"""The collection on disk: what is in it, and what each photo is.

The durable pieces are the folder itself and .credits (who took it).
Everything fetched is kept; the only removal is the one you ask for. Nothing
in here knows about a window or a command line.
"""

from __future__ import annotations

import contextlib
import re
import struct
import subprocess
import unicodedata
from pathlib import Path

from .desktop import active, focused_monitor, push_wallpaper
from .paths import CREDITS, CURRENT, DIR, IMAGE_SUFFIXES, THUMBS

# Migration only: kept/ and liked/ were how a photo outlived the daily
# copy. The collection is one folder now.
_KEPT = DIR / "kept"
_LEGACY_KEPT = DIR / "liked"


def slugify(text: str, limit: int = 44) -> str:
    """A filename fragment that survives a foreign title and stays readable."""
    plain = unicodedata.normalize("NFKD", text) \
        .encode("ascii", "ignore").decode()
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
    """Everything on offer, newest name first. One folder, one photo each."""
    return images(DIR)


def trash(path: Path) -> bool:
    """Send to the desktop wastebasket, not unlink.

    A person deleting a photograph can change their mind."""
    try:
        done = subprocess.run(["gio", "trash", str(path)],
                              capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        pass
    else:
        if done.returncode == 0:
            return True
    try:
        path.unlink()              # no gio, no trash -- still honour the ask
    except OSError:
        return False
    return True


# JPEG markers: SOF0-SOF15 carry the frame size; DHT/JPG/DAC sit among them.
_JPEG_MARKER_PREFIX = 0xFF
_JPEG_MARKER_LEN = 2
_JPEG_SOF_LO = 0xC0
_JPEG_SOF_HI = 0xCF
_JPEG_SOF_SKIP = (0xC4, 0xC8, 0xCC)
_YYYYMMDD_LEN = 8


# --- credits --------------------------------------------------------------


def credits() -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    try:
        for line in CREDITS.read_text().splitlines():
            parts = line.split("\t")
            if parts and parts[0]:
                out[parts[0]] = tuple(([*parts, "", "", ""])[1:4])  # type: ignore[assignment]
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


def current_image() -> Path | None:
    """The wallpaper on the focused monitor, else any displayed one, else
    whatever .current points at (hyprpaper may not be running)."""
    shown = active()
    if shown:
        name = focused_monitor()
        path = shown.get(name) if name else None
        path = path or next(iter(shown.values()))
        if path and Path(path).is_file():
            return Path(path)
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
    if parts and len(parts[0]) == _YYYYMMDD_LEN and parts[0].isdigit():
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

    # An id wearing a title's clothes ('wallhaven 7jlq13'). Better to show
    # no title than a fake one -- the accession line already says where this
    # came from, which is all that string ever meant.
    if title.lower().startswith("wallhaven "):
        title = ""

    # Bing glues place and photographer together:
    #   'Beach huts, Southwold, England (© stevendocwra/Getty Images)'
    match = CREDIT_RE.match(credit)
    place, author = (match.group(1), match.group(2)) if match else ("", credit)

    # A photographer credited as the source's own host only repeats the
    # source token.
    if author and source and author.lower().split(".")[0] == source:
        author = ""

    return {
        "file": str(path), "title": title, "place": place, "date": date,
        "source": source, "author": author, "url": url,
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
                if len(marker) < _JPEG_MARKER_LEN or marker[0] != _JPEG_MARKER_PREFIX:
                    return None
                length = struct.unpack(">H", handle.read(2))[0]
                if (_JPEG_SOF_LO <= marker[1] <= _JPEG_SOF_HI
                        and marker[1] not in _JPEG_SOF_SKIP):
                    height, width = struct.unpack(">HH", handle.read(5)[1:5])
                    return int(width), int(height)
                handle.seek(length - 2, 1)
    except (OSError, struct.error, ValueError, IndexError):
        return None


def set_wallpaper(image: Path, push: bool = True) -> None:
    """Repoint .current (durable) and push to every output (immediate).

    hyprpaper 0.8's empty-monitor wildcard -- `wallpaper ",path"` -- is
    accepted over IPC and silently does nothing, so name each output. Resolve
    first: .current must not point at another symlink, or pruning the middle
    link leaves it dangling.
    """
    image = image.resolve(strict=True)
    DIR.mkdir(parents=True, exist_ok=True)

    tmp = CURRENT.with_name(CURRENT.name + ".new")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(image)
    tmp.replace(CURRENT)          # atomic: never a window with no .current

    if push:
        push_wallpaper(image)


# --- migration ------------------------------------------------------------


def migrate_collection() -> list[str]:
    """kept/ and liked/ were how a photo outlived the daily copy. One folder
    now; anything still sitting in those names is merged in as kept."""
    if _LEGACY_KEPT.is_dir() and not _KEPT.exists():
        with contextlib.suppress(OSError):
            _LEGACY_KEPT.rename(_KEPT)
    if not _KEPT.is_dir():
        return []

    DIR.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for path in list(images(_KEPT)):
        dest = DIR / path.name
        if not dest.exists():
            path.rename(dest)
            moved.append(path.name)
        elif dest.stat().st_ino == path.stat().st_ino:
            path.unlink()          # hardlink twin: drop the extra name
        else:
            path.rename(DIR / f"{path.stem}-kept{path.suffix}")
            moved.append(path.name)

    # .current may still name a path under kept/; repoint before that name
    # disappears so a reboot is never without a wallpaper.
    if CURRENT.is_symlink():
        raw = Path(CURRENT.readlink())
        if raw.parent == _KEPT:
            twin = DIR / raw.name
            if twin.is_file():
                tmp = CURRENT.with_name(CURRENT.name + ".new")
                tmp.unlink(missing_ok=True)
                tmp.symlink_to(twin.resolve())
                tmp.replace(CURRENT)

    with contextlib.suppress(OSError):
        _KEPT.rmdir()
    return moved


def forget(names: list[str]) -> None:
    """Drop ledger lines whose file is gone, so .credits doesn't outgrow
    the collection it describes."""
    if not names:
        return
    gone = {name for name in names if not (DIR / name).exists()}
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
