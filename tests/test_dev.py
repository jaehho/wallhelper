"""scripts/dev leans on wallhelper in two ways no other test sees.

Its seed imports names from the library, and its hyprctl stub answers
only the one call the window makes for its monitors. Neither breaks
loudly: a rename leaves the dev window an empty strip, and a call the
stub does not know leaves it pushing no wallpaper, so hyprctl.log never
shows the push. Both read scripts/dev as text and run nothing of it.
"""

import importlib
import re
import unittest
from pathlib import Path
from unittest import mock

from tests import guard
from wallhelper import desktop

DEV = Path(__file__).resolve().parent.parent / "scripts/dev"
# `if [ "\$*" = "<ask>" ]; then echo '<answer>'` in the stub's heredoc.
STUB_ANSWER = re.compile(
    r'if \[ "\\\$\*" = "(?P<ask>[^"]+)" \]; then\n'
    r"\s*echo '(?P<answer>[^']+)'")


def setUpModule():
    guard()


class Seed(unittest.TestCase):
    def test_every_name_it_imports_from_wallhelper_exists(self):
        imports = re.findall(r"^from (wallhelper[.\w]*) import (.+)$",
                             DEV.read_text(), re.MULTILINE)
        self.assertTrue(imports, "scripts/dev imports nothing from "
                        "wallhelper; is the seed still there?")
        for module, names in imports:
            for name in (each.strip() for each in names.split(",")):
                with self.subTest(module=module, name=name):
                    self.assertTrue(
                        hasattr(importlib.import_module(module), name))


class HyprctlStub(unittest.TestCase):
    def setUp(self):
        stub = STUB_ANSWER.search(DEV.read_text())
        self.assertIsNotNone(stub, "no hyprctl answer in scripts/dev")
        self.calls = []

        def hyprctl(*args):
            # The stub compares "$*", the arguments joined by spaces.
            asked = " ".join(args)
            self.calls.append(asked)
            return stub["answer"] + "\n" if asked == stub["ask"] else ""

        for name, value in [("hyprctl", hyprctl),
                            ("_MONITORS", [(0.0, [])])]:
            patch = mock.patch.object(desktop, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_wallpaper_push_names_its_monitor(self):
        desktop.push_wallpaper(Path("/scratch/photos/a.jpg"))
        self.assertIn("hyprpaper wallpaper DEV-1,/scratch/photos/a.jpg",
                      self.calls)

    def test_its_monitor_is_the_focused_one(self):
        self.assertEqual(desktop.focused_monitor(), "DEV-1")
