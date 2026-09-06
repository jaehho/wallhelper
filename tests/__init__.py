"""Point paperboy at a scratch collection before anything imports it.

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

_ROOT = tempfile.mkdtemp(prefix="paperboy-test-")
os.environ["PAPERBOY_DIR"] = os.path.join(_ROOT, "photos")
os.environ["PAPERBOY_CONFIG"] = os.path.join(_ROOT, "config.json")
os.environ["XDG_CACHE_HOME"] = os.path.join(_ROOT, "cache")
os.environ["XDG_STATE_HOME"] = os.path.join(_ROOT, "state")


def guard():
    """Refuse to run against anything but the scratch collection."""
    from paperboy.paths import DIR
    if "paperboy-test-" not in str(DIR):
        raise RuntimeError(
            f"the tests are pointed at {DIR}, which is a real collection. "
            f"Run them with `make test`.")
