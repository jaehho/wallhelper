"""Point wallhelper at a scratch collection before anything imports it.

paths.py reads the environment once, at import time, on purpose: one process,
one collection. That makes this the only place the redirection can happen, and
it only happens because discovery imports this package before any test module
inside it -- run with `make test`, which passes the top-level directory so that
ordering is guaranteed.

Every test module also calls guard() from setUpModule, because getting this
wrong is not a failing test. The suite deletes files. Pointed at the real
collection it deletes yours.
"""

import os
import tempfile
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="wallhelper-test-"))
os.environ["WALLHELPER_DIR"] = str(_ROOT / "photos")
os.environ["WALLHELPER_CONFIG"] = str(_ROOT / "config.json")
os.environ["XDG_CACHE_HOME"] = str(_ROOT / "cache")
os.environ["XDG_STATE_HOME"] = str(_ROOT / "state")


def guard():
    """Refuse to run against anything but the scratch collection."""
    # late import: paths.py reads the env vars set above
    from wallhelper.paths import DIR  # noqa: PLC0415

    if "wallhelper-test-" not in str(DIR):
        msg = f"the tests are pointed at {DIR}, which is a real collection. Run them with `make test`."
        raise RuntimeError(msg)
