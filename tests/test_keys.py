"""The window's single-letter shortcuts stand down while Settings is up.

A source row in Settings is a button, so a bare D, F, E, O or G reaches the
window's key handler with focus inside the panel. Each of them acts on the
window behind it: D deletes the wallpaper, F starts a fetch. No display is
opened; on_key only reads panel state, so a stand-in for the window will do.
"""

import unittest
from unittest import mock

from tests import guard
from wallhelper.gui import window

from gi.repository import Gdk  # isort: skip -- after gui pins the version


def setUpModule():
    guard()


def stand_in(settings=False, shortcuts=False, guide=False):
    win = mock.Mock()
    win.get_focus.return_value = None
    win.settings_panel.get_reveal_child.return_value = settings
    win.shortcuts_panel.get_reveal_child.return_value = shortcuts
    win.guide_panel.get_reveal_child.return_value = guide
    win.held = set()
    return win


def press(win, keyval, code=0):
    return window.Window.on_key(win, None, keyval, code, 0)


def release(win, keyval, code=0):
    window.Window.on_key_released(win, None, keyval, code, 0)


class SettingsOpen(unittest.TestCase):
    ACTIONS = ("on_delete", "on_fetch", "on_source", "on_undo",
               "open_guide", "open_settings", "open_shortcuts")

    def test_letters_do_nothing_behind_the_panel(self):
        for key in (Gdk.KEY_d, Gdk.KEY_u, Gdk.KEY_f, Gdk.KEY_e, Gdk.KEY_o,
                    Gdk.KEY_g, Gdk.KEY_comma, Gdk.KEY_question):
            with self.subTest(key=Gdk.keyval_name(key)):
                win = stand_in(settings=True)
                self.assertFalse(press(win, key))
                for name in self.ACTIONS:
                    getattr(win, name).assert_not_called()
                win.elsewhere.toggle.assert_not_called()

    def test_escape_still_closes_it(self):
        win = stand_in(settings=True)
        self.assertTrue(press(win, Gdk.KEY_Escape))
        win.close_overlays.assert_called_once_with()

    def test_u_undoes_a_delete(self):
        win = stand_in()
        self.assertTrue(press(win, Gdk.KEY_u))
        win.on_undo.assert_called_once()

    def test_the_same_letters_work_with_no_panel_up(self):
        win = stand_in()
        self.assertTrue(press(win, Gdk.KEY_d))
        win.on_delete.assert_called_once()
        self.assertTrue(press(win, Gdk.KEY_f))
        win.on_fetch.assert_called_once()


class KeyRepeat(unittest.TestCase):
    """Holding D must delete one photograph, not walk the collection."""

    D = 40                       # a keycode; any would do

    def test_a_held_d_deletes_once(self):
        win = stand_in()
        for _ in range(5):
            self.assertTrue(press(win, Gdk.KEY_d, self.D))
        win.on_delete.assert_called_once()

    def test_a_second_press_after_the_release_deletes_again(self):
        win = stand_in()
        press(win, Gdk.KEY_d, self.D)
        release(win, Gdk.KEY_d, self.D)
        press(win, Gdk.KEY_d, self.D)
        self.assertEqual(win.on_delete.call_count, 2)

    def test_the_release_may_come_with_the_other_case(self):
        # Shift let go first: D went down, d comes up. Same keycode.
        win = stand_in()
        press(win, Gdk.KEY_D, self.D)
        release(win, Gdk.KEY_d, self.D)
        press(win, Gdk.KEY_D, self.D)
        self.assertEqual(win.on_delete.call_count, 2)

    def test_another_key_in_between_does_not_reset_it(self):
        win = stand_in()
        press(win, Gdk.KEY_d, self.D)
        press(win, Gdk.KEY_e, 26)
        press(win, Gdk.KEY_d, self.D)
        win.on_delete.assert_called_once()

    def test_other_keys_still_repeat(self):
        win = stand_in()
        press(win, Gdk.KEY_f, 41)
        press(win, Gdk.KEY_f, 41)
        self.assertEqual(win.on_fetch.call_count, 2)
