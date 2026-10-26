"""Every path wallhelper touches, and nothing else.

Imported by everything, importing nothing, so the rest of the package can be
read in any order. The environment overrides exist so a test run -- or a second
collection -- never touches the real one.
"""

from __future__ import annotations

import os
from pathlib import Path

DIR = Path(os.environ.get("WALLHELPER_DIR",
                          Path.home() / "Pictures/wallpapers"))
KEPT = DIR / "kept"
LEGACY_KEPT = DIR / "liked"
CREDITS = DIR / ".credits"
CURRENT = DIR / ".current"
CONFIG = Path(os.environ.get(
    "WALLHELPER_CONFIG", Path.home() / ".config/wallhelper/config.json"))
THUMBS = Path(os.environ.get("XDG_CACHE_HOME",
                             Path.home() / ".cache")) / "wallhelper/thumbs"

# Not in CONFIG: that file is edited by hand in the settings panel, and a
# housekeeping flag sitting among the real settings is noise in a file whose
# whole point is that you read it.
STATE = Path(os.environ.get("XDG_STATE_HOME",
                            Path.home() / ".local/state")) / "wallhelper"
GUIDE_SEEN = STATE / "guide-seen"
# What the last morning fetch came to: one small file, rewritten each run.
LAST_FETCH = STATE / "last-fetch.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
