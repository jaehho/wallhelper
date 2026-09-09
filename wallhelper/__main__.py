"""So `python -m wallhelper` works from a source tree, before installing."""

import sys

from .cli import main

sys.exit(main())
