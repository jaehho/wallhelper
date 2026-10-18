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
from typing import BinaryIO, NamedTuple

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


def in_collection(path: Path, folder: Path = DIR) -> bool:
    """Whether the file sits directly in the collection folder.

    Symlinks are followed first, because that is where a delete would
    land: a link in the folder to a file elsewhere is not in it."""
    return path.resolve().parent == folder.resolve()


# JPEG markers: SOF0-SOF15 carry the frame size; DHT/JPG/DAC sit among them.
_JPEG_MARKER_PREFIX = 0xFF
_JPEG_MARKER_LEN = 2
_JPEG_SOF_LO = 0xC0
_JPEG_SOF_HI = 0xCF
_JPEG_SOF_SKIP = (0xC4, 0xC8, 0xCC)
_YYYYMMDD_LEN = 8
_WEBP_HEAD_LEN = 12            # "RIFF", a size, "WEBP"
_ORIG_PATH = "trash::orig-path="
_GIO_TIMEOUT_S = 15
# What gui.thumbs writes: '<photo>-<w>x<h>.png'.
_CACHE_NAME = re.compile(r"(?P<photo>.+)-\d+x\d+\.png")


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
            return measure_stream(handle)
    except OSError:
        return None


def measure_stream(handle: BinaryIO) -> tuple[int, int] | None:
    """measure() for anything seekable, such as the first bytes of a file
    that is still a URL. None when they do not reach the size."""
    try:
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


def is_image(path: Path) -> bool:
    """Whether the file is a photograph, by its name and its first bytes.

    measure() answers for PNG and JPEG. WebP and BMP, which the sources can
    also hand us, are told apart by their signatures; a file called .jpg
    that holds text is neither.
    """
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return False
    if measure(path) is not None:
        return True
    try:
        with path.open("rb") as handle:
            head = handle.read(_WEBP_HEAD_LEN)
    except OSError:
        return False
    return head[:2] == b"BM" or (head[:4] == b"RIFF"
                                 and head[8:12] == b"WEBP")


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


# --- deleting -------------------------------------------------------------


TRASHED = "trashed"
UNLINKED = "unlinked"


class Trashed(NamedTuple):
    """One thing in the desktop wastebasket."""

    uri: str          # what gio addresses it by
    was: Path         # where it sat before
    when: str         # deletion date; ISO, so text order is time order


class Deleted(NamedTuple):
    """What delete_photo did."""

    path: Path
    title: str        # the caption's title, else the file's stem
    how: str          # TRASHED, or UNLINKED when the wastebasket refused


def _gio(*args: str) -> subprocess.CompletedProcess[str]:
    """Run gio. OSError when it cannot be run or does not answer in time;
    a non-zero exit is for the caller to read."""
    try:
        return subprocess.run(["gio", *args], capture_output=True,
                              text=True, errors="replace",
                              timeout=_GIO_TIMEOUT_S, check=False)
    except subprocess.SubprocessError as err:
        raise OSError(str(err)) from err


def trash(path: Path) -> str:
    """Send to the desktop wastebasket, not unlink. Says which happened.

    A person deleting a photograph can change their mind, so the
    wastebasket comes first. When it won't take the file (no gio, or a
    mount it can't trash from) the ask is still honoured and the answer is
    UNLINKED, so nobody tells the user about a Trash that doesn't hold it.

    Only the collection's own photographs: `delete` acts on whatever is on
    screen, and that can be a file wallhelper never owned. ValueError for
    anything else; OSError if the file is still there.
    """
    if not in_collection(path):
        msg = f"{path} is outside the collection ({DIR}), so not deleting it"
        raise ValueError(msg)
    try:
        done = _gio("trash", str(path))
    except OSError:
        pass
    else:
        if done.returncode == 0:
            return TRASHED
    path.unlink()                  # no gio, no trash -- still honour the ask
    return UNLINKED


def parse_trash(listing: str) -> list[Trashed]:
    """The wastebasket's entries out of `gio list -u -a
    trash::orig-path,trash::deletion-date trash:///`, one per line:

        trash:///a%20b.jpg  2  (regular)  trash::orig-path=/x/a b.jpg
        trash::deletion-date=2026-10-18T01:19:06

    A line that does not say where its entry came from is skipped.
    """
    out = []
    for line in listing.splitlines():
        uri, _, rest = line.partition("\t")
        attrs = rest.rpartition("\t")[2]
        orig, _, when = attrs.partition(" trash::deletion-date=")
        if uri and orig.startswith(_ORIG_PATH):
            out.append(Trashed(uri, Path(orig.removeprefix(_ORIG_PATH)), when))
    return out


def in_trash() -> list[Trashed]:
    """What the wastebasket holds. OSError when gio cannot say.

    That is not an empty Trash, and whoever would act on "nothing there"
    must not take it for one."""
    done = _gio("list", "-u", "-a", "trash::orig-path,trash::deletion-date",
                "trash:///")
    if done.returncode != 0:
        msg = done.stderr.strip() or "gio could not list the Trash"
        raise OSError(msg)
    return parse_trash(done.stdout)


def restore(path: Path) -> None:
    """Put a photograph back where it was, out of the Trash. OSError when
    the Trash does not have it or gio will not give it up.

    If it was trashed more than once, the latest comes back. Its ledger
    line and thumbnails never left (see prune), so it returns captioned."""
    here = [entry for entry in in_trash() if _same_place(entry.was, path)]
    if not here:
        msg = f"{path.name} is not in the Trash"
        raise FileNotFoundError(msg)
    latest = sorted(here, key=lambda entry: entry.when)[-1]
    done = _gio("trash", "--restore", latest.uri)
    if done.returncode != 0:
        msg = done.stderr.strip() or f"gio could not restore {path.name}"
        raise OSError(msg)
    # gvfs's view of the Trash goes stale for a restored name: trash the
    # photograph again and `gio list` never shows it, nor will --restore
    # find it, until something lists the Trash once more. Measured with a
    # private gvfsd-trash: five restore/trash cycles list correctly with
    # this line, and the second cycle fails without it.
    with contextlib.suppress(OSError):
        in_trash()


def cache_owner(cached: str) -> str | None:
    """The photograph a cached thumbnail was cut from, from its filename
    ('<photo>-<w>x<h>.png', see gui.thumbs). None for the cache entries
    that belong to no photograph: Elsewhere's remote-*, temp files."""
    match = _CACHE_NAME.fullmatch(cached)
    if match is None or cached.startswith("."):
        return None
    photo = match["photo"]
    return photo if Path(photo).suffix.lower() in IMAGE_SUFFIXES else None


def _same_place(one: Path, other: Path) -> bool:
    """Same name in the same folder, folders taken with symlinks followed
    (the file itself may be gone)."""
    return (one.name == other.name
            and one.parent.resolve() == other.parent.resolve())


def names_in_trash(entries: list[Trashed], folder: Path = DIR) -> set[str]:
    """Filenames of the entries that were trashed out of `folder`."""
    where = folder.resolve()
    return {entry.was.name for entry in entries
            if entry.was.parent.resolve() == where}


def _is_gone(name: str, present: set[str], trashed: set[str]) -> bool:
    return name not in present and name not in trashed


def _prune_ledger(present: set[str], trashed: set[str]) -> None:
    try:
        lines = CREDITS.read_text().splitlines()
        kept = [line for line in lines
                if not _is_gone(line.split("\t")[0], present, trashed)]
        if len(kept) == len(lines):
            return
        tmp = CREDITS.with_name(CREDITS.name + ".new")
        tmp.write_text("".join(line + "\n" for line in kept))
        tmp.replace(CREDITS)
    except OSError:
        pass


def _prune_thumbnails(present: set[str], trashed: set[str]) -> None:
    try:
        cached = list(THUMBS.iterdir())
    except OSError:
        return
    for path in cached:
        owner = cache_owner(path.name)
        if owner and _is_gone(owner, present, trashed):
            with contextlib.suppress(OSError):
                path.unlink()


def prune() -> None:
    """Drop the ledger line and cached thumbnails of every photograph that
    is gone from the collection and from the wastebasket, so neither
    outgrows the collection it describes.

    A photograph in the Trash keeps both: one restored from there has its
    title and byline back, and its tile does not wait on a decode. Files
    removed outside wallhelper are caught here too. It runs when the
    window opens, not after a delete: right after one, gvfs's list of the
    Trash can still be missing the photograph just trashed.

    Nothing is dropped when it cannot be sure. Losing a caption is not
    undoable, and keeping a stale line is free: so not when the Trash
    cannot be read, and not when the folder looks empty, which is also how
    an unmounted drive looks. The folder is read before the Trash, so a
    photograph deleted in between still counts as present rather than as
    missing from both lists.
    """
    try:
        present = {entry.name for entry in DIR.iterdir()}
        trashed = names_in_trash(in_trash())
    except OSError:
        return
    if not present:
        return
    _prune_ledger(present, trashed)
    _prune_thumbnails(present, trashed)


def delete_photo(path: Path) -> Deleted:
    """Take one photograph out of the collection and put its neighbour on
    the wall. ValueError and OSError as for trash().

    The neighbour is the next one along the grid, so deleting a run walks
    along it rather than throwing you back to the start every time.
    """
    title = label(path)["title"] or path.stem
    everything = collection()
    index = next((i for i, other in enumerate(everything)
                  if other.name == path.name), 0)
    following = [other for other in everything if other.name != path.name]

    how = trash(path)
    if following:
        # The photograph is gone either way; a neighbour that vanished too
        # leaves the wall as it was rather than undoing the answer.
        with contextlib.suppress(OSError):
            set_wallpaper(following[min(index, len(following) - 1)])
    return Deleted(path, title, how)
