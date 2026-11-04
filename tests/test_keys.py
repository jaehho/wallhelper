"""Every key the strip answers, and the ones it no longer does.

No display is opened: on_key only reads whether the key list is up, so a
stand-in for the window will do. Its handlers are autospecced from the
real class, so a key mapped to a handler that cannot take the call fails
here, not on someone's keyboard weeks later.
"""

import unittest
from unittest import mock

from tests import guard
from wallhelper.gui import app, window

from gi.repository import Gdk  # isort: skip -- after gui pins the version

CTRL = Gdk.ModifierType.CONTROL_MASK
ALT = Gdk.ModifierType.ALT_MASK
SHIFT = Gdk.ModifierType.SHIFT_MASK
CAPS = Gdk.ModifierType.LOCK_MASK


def setUpModule():
    guard()


HANDLERS = ("on_delete", "on_source", "on_undo", "on_done", "open_keys",
            "close_keys", "step_back", "step_on")


def stand_in(keys_open=False):
    win = mock.Mock()
    # Mock takes any call, which is how E raised on every press unseen.
    spec = mock.create_autospec(window.Window, instance=True)
    for name in HANDLERS:
        setattr(win, name, getattr(spec, name))
    win.key_actions = lambda: window.Window.key_actions(win)
    win.keys_panel.get_reveal_child.return_value = keys_open
    win.held = set()
    return win


def press(win, keyval, code=0, state=0):
    return window.Window.on_key(win, None, keyval, code, state)


def release(win, keyval, code=0):
    window.Window.on_key_released(win, None, keyval, code, 0)


def called(win):
    return [name for name in HANDLERS if getattr(win, name).called]


class EveryKey(unittest.TestCase):
    """Each key reaches its handler once, called the way on_key calls it."""

    def test_each_key_runs_its_handler(self):
        for key, handler in (
            (Gdk.KEY_question, "open_keys"),
            (Gdk.KEY_d, "on_delete"), (Gdk.KEY_D, "on_delete"),
            (Gdk.KEY_Delete, "on_delete"), (Gdk.KEY_BackSpace, "on_delete"),
            (Gdk.KEY_u, "on_undo"), (Gdk.KEY_U, "on_undo"),
            (Gdk.KEY_o, "on_source"), (Gdk.KEY_O, "on_source"),
            (Gdk.KEY_h, "step_back"), (Gdk.KEY_Left, "step_back"),
            (Gdk.KEY_l, "step_on"), (Gdk.KEY_Right, "step_on"),
            (Gdk.KEY_Return, "on_done"), (Gdk.KEY_KP_Enter, "on_done"),
            (Gdk.KEY_Escape, "on_done"),
        ):
            with self.subTest(key=Gdk.keyval_name(key)):
                win = stand_in()
                self.assertTrue(press(win, key))
                self.assertEqual(called(win), [handler])

    def test_the_keys_of_the_old_window_are_free(self):
        # E was Elsewhere (#23); F, G and , were the fetch, the guide and
        # settings (#24).
        for key in (Gdk.KEY_e, Gdk.KEY_f, Gdk.KEY_g, Gdk.KEY_comma):
            with self.subTest(key=Gdk.keyval_name(key)):
                win = stand_in()
                self.assertFalse(press(win, key))
                self.assertEqual(called(win), [])


class KeyList(unittest.TestCase):
    """With the key list up, any key puts it away and does nothing else."""

    def test_any_key_closes_it_alone(self):
        for key, state in ((Gdk.KEY_d, 0), (Gdk.KEY_Escape, 0),
                           (Gdk.KEY_l, 0), (Gdk.KEY_z, CTRL)):
            with self.subTest(key=Gdk.keyval_name(key)):
                win = stand_in(keys_open=True)
                self.assertTrue(press(win, key, state=state))
                self.assertEqual(called(win), ["close_keys"])


class KeyRepeat(unittest.TestCase):
    """Holding D must delete one photograph, not walk the collection."""

    D = 40                       # a keycode; any would do

    def test_a_held_d_deletes_once(self):
        win = stand_in()
        for _ in range(5):
            self.assertTrue(press(win, Gdk.KEY_d, self.D))
        win.on_delete.assert_called_once()

    def test_a_held_backspace_deletes_once(self):
        win = stand_in()
        for _ in range(5):
            press(win, Gdk.KEY_BackSpace, 22)
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
        press(win, Gdk.KEY_l, 46)
        press(win, Gdk.KEY_d, self.D)
        win.on_delete.assert_called_once()

    def test_moving_still_repeats(self):
        # Holding l walks the strip, as holding an arrow does.
        win = stand_in()
        press(win, Gdk.KEY_l, 46)
        press(win, Gdk.KEY_l, 46)
        self.assertEqual(win.step_on.call_count, 2)


class Chords(unittest.TestCase):
    """Ctrl+D is not D: a letter held with Ctrl or Alt does nothing here.

    The chords the window does answer are application accelerators, which
    GTK runs before this handler, and Ctrl+Z; a Ctrl+letter that gets
    this far otherwise is one the window has no use for.
    """

    LETTERS = (Gdk.KEY_d, Gdk.KEY_u, Gdk.KEY_o, Gdk.KEY_h, Gdk.KEY_l,
               Gdk.KEY_question)

    def test_a_letter_with_ctrl_or_alt_does_nothing(self):
        for held in (CTRL, ALT, CTRL | SHIFT):
            for key in self.LETTERS:
                with self.subTest(key=Gdk.keyval_name(key), held=held):
                    win = stand_in()
                    self.assertFalse(press(win, key, state=held))
                    self.assertEqual(called(win), [])

    def test_shift_and_caps_lock_leave_a_letter_a_letter(self):
        # ? is Shift+/, and Caps Lock turns d into D.
        for key, held, handler in (
            (Gdk.KEY_D, SHIFT, "on_delete"),
            (Gdk.KEY_D, CAPS, "on_delete"),
            (Gdk.KEY_question, SHIFT, "open_keys"),
        ):
            with self.subTest(key=Gdk.keyval_name(key), held=held):
                win = stand_in()
                self.assertTrue(press(win, key, state=held))
                getattr(win, handler).assert_called_once()


class AppChords(unittest.TestCase):
    """Ctrl+W, Ctrl+Q and Ctrl+? are bound on the application, which GTK
    runs before the focused widget sees the key."""

    def test_each_chord_is_bound(self):
        wallhelper = app.App()
        for action, accel in (("window.close", "<Control>w"),
                              ("app.quit", "<Control>q"),
                              ("win.shortcuts", "<Control>question")):
            with self.subTest(action=action):
                self.assertEqual(
                    wallhelper.get_accels_for_action(action), [accel])

    def test_ctrl_q_quits(self):
        wallhelper = app.App()
        with mock.patch.object(app.App, "quit") as leave:
            wallhelper.lookup_action("quit").activate(None)
        leave.assert_called_once_with()


class CtrlZ(unittest.TestCase):
    """Ctrl+Z undoes a delete, as U does."""

    def test_ctrl_z_undoes(self):
        for key, held in ((Gdk.KEY_z, CTRL), (Gdk.KEY_Z, CTRL | CAPS)):
            with self.subTest(key=Gdk.keyval_name(key), held=held):
                win = stand_in()
                self.assertTrue(press(win, key, state=held))
                win.on_undo.assert_called_once_with(None)

    def test_other_chords_on_z_do_nothing(self):
        for key, held in ((Gdk.KEY_Z, CTRL | SHIFT), (Gdk.KEY_z, ALT),
                          (Gdk.KEY_z, CTRL | ALT), (Gdk.KEY_z, 0)):
            with self.subTest(key=Gdk.keyval_name(key), held=held):
                win = stand_in()
                self.assertFalse(press(win, key, state=held))
                win.on_undo.assert_not_called()
