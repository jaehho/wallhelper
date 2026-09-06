"""So `python -m paperboy` works from a source tree, before it is installed."""

import sys

from .cli import main

sys.exit(main())
