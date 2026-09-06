"""Point paperboy at a scratch collection before anything imports it.

paths.py reads the environment at import time, on purpose: one process, one
collection. That makes this the only place the redirection can happen, so it
has to happen before the first `import paperboy.*` anywhere in the suite.
"""

import os
import tempfile

_ROOT = tempfile.mkdtemp(prefix="paperboy-test-")
os.environ["PAPERBOY_DIR"] = os.path.join(_ROOT, "photos")
os.environ["PAPERBOY_CONFIG"] = os.path.join(_ROOT, "config.json")
os.environ["XDG_CACHE_HOME"] = os.path.join(_ROOT, "cache")
os.environ["XDG_STATE_HOME"] = os.path.join(_ROOT, "state")
