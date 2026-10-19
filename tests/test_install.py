"""`make install` runs this checkout from a prefix; `make uninstall` takes
back what it put there and nothing else.

Both run into a scratch prefix and data directory with HOME pointed at
scratch as well, so a write that strays lands where the assertions look
for it. Nothing here touches ~/.local, and nothing launches the window.
"""

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import guard

CHECKOUT = Path(__file__).resolve().parent.parent
ENTRY = "dev.jaeho.Wallhelper.desktop"
PYTHON = Path("/usr/bin/python")
# What `make install` writes, relative to the scratch directory.
INSTALLED = {"prefix/bin/wallhelper", f"share/applications/{ENTRY}"}
# update-desktop-database keeps this beside every entry, not just ours.
SHARED = "share/applications/mimeinfo.cache"


def setUpModule():
    guard()


@unittest.skipUnless(shutil.which("make"), "make is not installed")
class Install(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="wallhelper-install-")
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        home = self.scratch / "home"
        home.mkdir()
        self.launcher = self.scratch / "prefix/bin/wallhelper"
        self.entry = self.scratch / "share/applications" / ENTRY
        # Leave out make's own flags (this runs under `make test`) and
        # anything that would point the launcher at a tree: it must find
        # the checkout from what install baked in.
        env = {
            k: v for k, v in os.environ.items()
            if not k.startswith(("MAKE", "MFLAGS", "PYTHONPATH",
                                 "WALLHELPER_"))
        }
        env.update(
            HOME=str(home),
            PREFIX=str(self.scratch / "prefix"),
            DATADIR=str(self.scratch / "share"),
            XDG_DATA_HOME=str(self.scratch / "share"),
            XDG_STATE_HOME=str(home / ".local/state"),
            XDG_CONFIG_HOME=str(home / ".config"),
            XDG_CACHE_HOME=str(home / ".cache"),
            WALLHELPER_DIR=str(home / "Pictures/wallpapers"),
            WALLHELPER_CONFIG=str(home / ".config/wallhelper/config.json"),
        )
        self.env = env

    def make(self, *args):
        done = subprocess.run(
            ["make", "-C", str(CHECKOUT), *args],
            env=self.env, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done

    def launch(self, *args, cwd=None, **env):
        """Run the installed launcher, by default from a directory that
        is not the checkout, so a hit on the tree cannot come from the
        cwd."""
        return subprocess.run(
            [str(self.launcher), *args], cwd=cwd or self.scratch,
            env={**self.env, **env}, capture_output=True, text=True,
            check=False)

    def files(self):
        """Every file under scratch: {path: (mode, content)}.

        Whatever has strayed outside the prefix and the data directory,
        into HOME say, shows up here. The shared cache is left out: the
        desktop database tool owns it, and it outlives any one entry.
        """
        found = {}
        for path in self.scratch.rglob("*"):
            rel = path.relative_to(self.scratch).as_posix()
            if rel == SHARED or (path.is_dir() and not path.is_symlink()):
                continue
            content = path.readlink() if path.is_symlink() else \
                path.read_bytes()
            found[rel] = (path.lstat().st_mode, content)
        return found

    def test_install_writes_a_launcher_and_an_entry_and_no_more(self):
        self.make("install")
        self.assertEqual(set(self.files()), INSTALLED)
        self.assertTrue(self.launcher.is_file())
        self.assertTrue(os.access(self.launcher, os.X_OK))

    def test_install_never_asks_for_privilege_a_service_or_a_package(self):
        out = self.make("-n", "install", "uninstall").stdout
        for word in ("sudo", "systemctl", "pacman", "paru", "makepkg"):
            with self.subTest(word):
                self.assertIsNone(re.search(rf"\b{word}\b", out))

    def test_a_second_install_changes_nothing(self):
        self.make("install")
        first = self.files()
        self.make("install")
        self.assertEqual(self.files(), first)

    def test_the_template_keeps_its_sentinel(self):
        template = CHECKOUT / "scripts/wallhelper-live"
        before = template.read_bytes()
        self.make("install")
        self.assertEqual(template.read_bytes(), before)
        self.assertIn(b'\nDEFAULT_ROOT="@ROOT@"\n', before)
        installed = self.launcher.read_text()
        self.assertIn(f'\nDEFAULT_ROOT="{CHECKOUT}"\n', installed)
        self.assertNotIn('\nDEFAULT_ROOT="@ROOT@"\n', installed)

    def test_install_replaces_a_symlink_and_spares_what_it_pointed_at(self):
        # Writing through a link would empty its target, and the
        # target of a link left by hand could be the template itself.
        stash = self.scratch / "stash"
        stash.mkdir()
        for dest in (self.launcher, self.entry):
            dest.parent.mkdir(parents=True, exist_ok=True)
            target = stash / dest.name
            target.write_text("keep")
            dest.symlink_to(target)
        self.make("install")
        self.assertEqual({p.read_text() for p in stash.iterdir()}, {"keep"})
        for dest in (self.launcher, self.entry):
            with self.subTest(dest.name):
                self.assertFalse(dest.is_symlink())
        self.assertEqual(
            {x for x in self.files() if not x.startswith("stash/")},
            INSTALLED)
        self.assertTrue(os.access(self.launcher, os.X_OK))

    def test_a_failed_install_leaves_the_installed_launcher_alone(self):
        self.make("install")
        # A checkout whose launcher template cannot be read: sed fails.
        broken = self.scratch / "broken"
        (broken / "scripts/wallhelper-live").mkdir(parents=True)
        shutil.copy(CHECKOUT / "Makefile", broken)
        shutil.copytree(CHECKOUT / "packaging", broken / "packaging")
        before = self.files()
        done = subprocess.run(
            ["make", "-C", str(broken), "install"], env=self.env,
            capture_output=True, text=True, check=False)
        self.assertNotEqual(done.returncode, 0)
        # The same launcher, and no half-written file beside it.
        self.assertEqual(self.files(), before)
        self.assertTrue(os.access(self.launcher, os.X_OK))

    def test_the_entry_launches_by_the_absolute_launcher_path(self):
        self.make("install")
        lines = self.entry.read_text().splitlines()
        (exec_line,) = (x for x in lines if x.startswith("Exec="))
        self.assertEqual(shlex.split(exec_line.removeprefix("Exec=")),
                         [str(self.launcher), "gui"])
        self.assertTrue(self.launcher.is_file())
        # Exec= is the one line that differs from the packaged entry.
        packaged = (CHECKOUT / "packaging" / ENTRY).read_text().splitlines()
        self.assertEqual([x for x in lines if not x.startswith("Exec=")],
                         [x for x in packaged if not x.startswith("Exec=")])

    @unittest.skipUnless(PYTHON.exists(), f"{PYTHON} is not installed")
    def test_the_launcher_runs_the_checkout_it_was_installed_from(self):
        self.make("install")
        done = self.launch("--help")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("usage: wallhelper", done.stdout)

    @unittest.skipUnless(PYTHON.exists(), f"{PYTHON} is not installed")
    def test_a_wallhelper_package_in_the_cwd_does_not_shadow_the_tree(self):
        # Another clone or a worktree: run from inside it, the launcher
        # still runs the checkout it was installed from.
        other = self.scratch / "other"
        (other / "wallhelper").mkdir(parents=True)
        (other / "wallhelper/__init__.py").write_text("")
        (other / "wallhelper/__main__.py").write_text(
            "print('OTHER TREE RAN')\n")
        self.make("install")
        done = self.launch("--help", cwd=other)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("OTHER TREE RAN", done.stdout)
        self.assertIn("usage: wallhelper", done.stdout)

    @unittest.skipUnless(PYTHON.exists(), f"{PYTHON} is not installed")
    def test_wallhelper_src_picks_another_tree_and_passes_arguments(self):
        tree = self.scratch / "tree"
        (tree / "wallhelper").mkdir(parents=True)
        (tree / "wallhelper/__init__.py").write_text("")
        (tree / "wallhelper/__main__.py").write_text(
            "import sys\nprint(__file__)\nprint(*sys.argv[1:])\n")
        self.make("install")
        done = self.launch("fetch", "--wait", WALLHELPER_SRC=str(tree))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            done.stdout.splitlines(),
            [str(tree / "wallhelper/__main__.py"), "fetch --wait"])

    def test_a_missing_checkout_is_named_and_fails(self):
        self.make("install")
        nowhere = self.scratch / "nowhere"
        done = self.launch("--help", WALLHELPER_SRC=str(nowhere))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(str(nowhere), done.stderr)
        self.assertIn("WALLHELPER_SRC", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_uninstall_removes_what_install_made_and_nothing_else(self):
        # A collection, its config and state, and neighbours of the two
        # installed files: none of it is install's to touch.
        for rel in ("home/Pictures/wallpapers/20260905-bing-in.png",
                    "home/Pictures/wallpapers/.credits",
                    "home/.config/wallhelper/config.json",
                    "home/.local/state/wallhelper/last-fetch.json",
                    "home/.cache/wallhelper/thumbs/x.png",
                    "prefix/bin/other-tool",
                    "share/applications/other.desktop"):
            path = self.scratch / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rel)
        before = self.files()
        self.make("install")
        self.assertEqual(set(self.files()) - set(before), INSTALLED)
        self.make("uninstall")
        self.assertEqual(self.files(), before)
        # Nothing left to remove is not an error.
        self.make("uninstall")
        self.assertEqual(self.files(), before)
