"""The window: a caption over a strip of every photograph saved.

It opens on the bottom edge of an empty workspace (hyprland.lua docks it
there and takes you back when it closes), so the desktop above it shows
the selection: moving it sets the wallpaper, and closing keeps whatever
is on the wall (#24). Nothing here needs a settings panel or a guide:
the morning's fetch says how it went in the strip's first place, and
every action is a key, listed on ? for the day one is forgotten.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import gi

from ..config import autofetch_sources
from ..desktop import push_wallpaper
from ..library import (
    TRASHED,
    collection,
    current_image,
    delete_photo,
    prune,
    restore,
    set_wallpaper,
)
from ..morning import FAILED, SAVED, Outcome, fetch_morning, todays
from ..net import describe
from .plate import Plate
from .sheets import keys_sheet
from .strip import ARRIVING, Item, Strip
from .style import LONG_TOAST_SECONDS, STRIP_H, STRIP_W, palette, stylesheet
from .thumbs import dimensions

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

# Held with any of these, a letter is a chord and not the letter: Ctrl+D
# must not delete a photograph. Shift is not here, because ? is Shift+/.
CHORD_MODIFIERS = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK
                   | Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.HYPER_MASK
                   | Gdk.ModifierType.META_MASK)
DELETE_KEYS = (Gdk.KEY_d, Gdk.KEY_D, Gdk.KEY_Delete, Gdk.KEY_BackSpace)
# A fetch that answers sooner than this (Bing has nothing new yet) never
# shows its place at all: the strip would flicker on every open.
ARRIVING_AFTER_MS = 600


def is_ctrl_z(keyval: int, state: Gdk.ModifierType) -> bool:
    """Ctrl+Z and nothing else held but Caps Lock: Ctrl+Shift+Z is redo
    elsewhere, and this window has nothing to redo."""
    held = state & (CHORD_MODIFIERS | Gdk.ModifierType.SHIFT_MASK)
    return (keyval in (Gdk.KEY_z, Gdk.KEY_Z)
            and held == Gdk.ModifierType.CONTROL_MASK)


def morning_due(usable: list[str], kept: Outcome | None) -> bool:
    """Whether opening the strip should go and get this morning's
    photograph: a morning source is on, and no run kept one today."""
    return bool(usable) and kept is None


def _in_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


class WallPusher:
    """Latest wins, one at a time.

    A push blocks on hyprpaper decoding the photograph, about a tenth of
    a second per output, so holding an arrow must not queue one per tile.
    The first goes at once; whatever is wanted when it lands goes next,
    and everything passed over in between never goes at all.
    """

    def __init__(self, push: Callable[[Path], None], *,
                 start: Callable = _in_thread,
                 finish: Callable = GLib.idle_add):
        self.push_now = push
        self.start = start        # runs the push off the main loop
        self.finish = finish      # brings its end back onto it
        self.wanted: Path | None = None
        self.busy = False

    def push(self, image: Path) -> None:
        self.wanted = image
        if not self.busy:
            self._go(image)

    def _go(self, image: Path) -> None:
        self.busy = True
        self.start(lambda: self._run(image))

    def _run(self, image: Path) -> None:
        try:
            self.push_now(image)
        finally:
            self.finish(self._landed, image)

    def _landed(self, image: Path) -> bool:
        self.busy = False
        if self.wanted is not None and self.wanted != image:
            self._go(self.wanted)
        return False


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Wallhelper")
        self.set_default_size(STRIP_W, STRIP_H)
        self.add_css_class("wallhelper")
        self.before = current_image()    # the wall when the strip opened
        self.current = self.before
        self.wall = WallPusher(push_wallpaper)
        self.undoable = None         # (toast, Deleted) while UNDO is on offer
        self.status: Item | None = None    # the morning's place, if shown
        self.fetching = False
        self.held = set()            # keycodes pressed and not yet released

        css = Gtk.CssProvider()
        css.load_from_data(stylesheet(palette()).encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        pointer = Gdk.Cursor.new_from_name("pointer", None)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        overlay = Gtk.Overlay()
        self.toasts.set_child(overlay)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.set_child(column)

        self.plate = Plate(pointer, self.on_delete, self.on_source,
                           self.on_done)
        column.append(self.plate)
        self.strip = Strip(pointer, self.on_select, self.on_activate)
        column.append(self.strip)

        self.keys_panel = keys_sheet(self.close_keys)
        overlay.add_overlay(self.keys_panel)

        # Ctrl+? is an application accelerator (app.py), and those
        # activate actions.
        shortcuts = Gio.SimpleAction(name="shortcuts")
        shortcuts.connect("activate", lambda *_a: self.open_keys())
        self.add_action(shortcuts)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        keys.connect("key-released", self.on_key_released)
        self.add_controller(keys)
        # A release that lands elsewhere (focus moved) would leave its key
        # looking held.
        self.connect("notify::is-active", lambda *_a: self.held.clear())
        # Focus needs a mapped list; the arrows then work from the start.
        self.connect("map", lambda *_a: self.strip.focus_selected())

        self.refresh()
        # Off the main thread: it asks gio what the Trash holds.
        threading.Thread(target=prune, daemon=True).start()
        self.check_morning()

    # --- what is shown ------------------------------------------------------

    def refresh(self):
        self.strip.show(collection(), select=self.current,
                        status=self.status, before=self.before)
        self.describe(self.strip.selected())

    def describe(self, item: Item | None):
        if item is None:
            self.plate.say("Nothing saved yet", "")
        elif item.status == ARRIVING:
            self.plate.say("Today\u2019s photograph is on its way", "")
        elif item.status:
            self.plate.say("No photograph this morning",
                           f"{item.message} \u00b7 Enter tries again")
        else:
            self.plate.refresh(item.path, dimensions(item.path))

    def toast(self, text, timeout=2, priority=Adw.ToastPriority.NORMAL):
        self.toasts.add_toast(
            Adw.Toast(title=text, timeout=timeout, priority=priority))

    # --- the strip's side ---------------------------------------------------

    def on_select(self, item: Item):
        if item.status:
            self.describe(item)
            return
        if self.put_on_wall(item.path):
            self.describe(item)

    def put_on_wall(self, path: Path) -> bool:
        """The wall follows the selection: .current at once, hyprpaper as
        soon as the last push has landed."""
        try:
            set_wallpaper(path, push=False)
        except OSError:
            self.toast("That file is gone")
            self.refresh()
            return False
        self.current = path
        self.wall.push(path)
        return True

    def on_activate(self, item: Item):
        if item.status == FAILED:
            self.check_morning(again=True)
        elif not item.status:
            self.on_done()

    def on_done(self, _button=None):
        self.close()

    def on_source(self, _button=None):
        if self.plate.url:
            Gtk.UriLauncher(uri=self.plate.url).launch(self, None, None, None)

    def step_back(self, _button=None):
        self.strip.move(-1)

    def step_on(self, _button=None):
        self.strip.move(1)

    # --- deleting -----------------------------------------------------------

    def on_delete(self, _button=None):
        item = self.strip.selected()
        if item is None or item.status:
            return
        place = self.strip.selected_index() - (1 if self.status else 0)
        try:
            gone = delete_photo(item.path)
        except ValueError:
            self.toast("That one is not in the collection")
            return
        except OSError:
            self.toast("Couldn't delete that one")
            return
        if gone.how == TRASHED:
            self.offer_undo(gone)
        else:
            self.toast(f"{gone.title} \u2014 deleted for good, "
                       "the Trash refused it", timeout=LONG_TOAST_SECONDS,
                       priority=Adw.ToastPriority.HIGH)
        # delete_photo put the next one along on the wall: the photograph
        # that has moved into this place.
        left = collection()
        self.current = left[min(place, len(left) - 1)] if left else None
        self.refresh()

    def offer_undo(self, gone):
        """The delete toast, with UNDO for as long as it is up. U and
        Ctrl+Z do the same, so nothing here needs the pointer."""
        self.withdraw_undo()
        toast = Adw.Toast(
            title=f"{gone.title} \u2014 moved to Trash",
            timeout=LONG_TOAST_SECONDS, button_label="UNDO",
            priority=Adw.ToastPriority.HIGH,
        )
        toast.connect("button-clicked", lambda _t: self.on_undo())
        toast.connect("dismissed", lambda _t: self.lapse_undo(toast))
        self.undoable = (toast, gone)
        self.toasts.add_toast(toast)

    def lapse_undo(self, toast):
        if self.undoable is not None and self.undoable[0] is toast:
            self.undoable = None

    def withdraw_undo(self):
        if self.undoable is not None:
            toast, _gone = self.undoable
            self.undoable = None
            toast.dismiss()

    def on_undo(self, _button=None):
        """Bring the last delete back out of the Trash, and back onto the
        wall: it was the wallpaper when it went."""
        if self.undoable is None:
            return
        _toast, gone = self.undoable
        self.withdraw_undo()
        try:
            restore(gone.path)
        except OSError:
            self.toast(f"Couldn't restore {gone.title}; it is still in "
                       "the Trash", timeout=LONG_TOAST_SECONDS)
            return
        if self.put_on_wall(gone.path):
            self.refresh()
            self.toast(f"{gone.title} \u2014 restored")

    # --- the morning's photograph ---------------------------------------------

    def check_morning(self, *, again: bool = False):
        """Go and get this morning's photograph if no run kept one: the
        timer may have slept through it, or failed. Its place in the strip
        says how that goes, and only if it takes long enough to notice."""
        usable = autofetch_sources()
        kept = None if again else todays(usable)
        if self.fetching or not morning_due(usable, kept):
            return
        self.fetching = True
        GLib.timeout_add(0 if again else ARRIVING_AFTER_MS, self._arriving)

        def work():
            try:
                run = fetch_morning()
            except Exception as err:   # a thread that dies says nothing
                run = Outcome(FAILED, "", describe(err))
            GLib.idle_add(self._fetched, run)

        _in_thread(work)

    def _arriving(self):
        if self.fetching:
            self.status = Item(status=ARRIVING)
            self.refresh()
        return False

    def _fetched(self, run: Outcome):
        self.fetching = False
        self.status = (Item(status=FAILED, message=run.message)
                       if run.kind == FAILED else None)
        if run.kind == SAVED and run.photo is not None:
            # fetch_morning has already put it on the wall.
            self.current = run.photo
        self.refresh()
        return False

    # --- keys -----------------------------------------------------------------

    def open_keys(self, _button=None):
        self.keys_panel.set_reveal_child(True)
        self.keys_panel.set_can_target(True)
        return False

    def close_keys(self):
        self.keys_panel.set_reveal_child(False)
        self.keys_panel.set_can_target(False)
        self.strip.focus_selected()
        return False

    def key_actions(self) -> dict[int, Callable]:
        return {
            Gdk.KEY_question: self.open_keys,
            Gdk.KEY_d: self.on_delete, Gdk.KEY_D: self.on_delete,
            Gdk.KEY_Delete: self.on_delete, Gdk.KEY_BackSpace: self.on_delete,
            Gdk.KEY_u: self.on_undo, Gdk.KEY_U: self.on_undo,
            Gdk.KEY_o: self.on_source, Gdk.KEY_O: self.on_source,
            # The list moves itself on the arrows while it has focus;
            # these are for when it does not, and for h and l.
            Gdk.KEY_h: self.step_back, Gdk.KEY_Left: self.step_back,
            Gdk.KEY_l: self.step_on, Gdk.KEY_Right: self.step_on,
            Gdk.KEY_Return: self.on_done, Gdk.KEY_KP_Enter: self.on_done,
        }

    def on_key_released(self, _controller, _keyval, code, _state):
        self.held.discard(code)

    def on_key(self, _controller, keyval, code, state):
        # GTK4 sends an auto-repeat as more presses with no release between
        # them, and says nothing else to tell it from a fresh one.
        repeat = code in self.held
        self.held.add(code)

        if self.keys_panel.get_reveal_child():
            self.close_keys()            # any key puts the list away
            return True
        if keyval == Gdk.KEY_Escape:
            self.on_done()
            return True

        if state & CHORD_MODIFIERS:
            # The other chords the window answers never get here: GTK
            # runs them as application accelerators (app.py) first.
            action = self.on_undo if is_ctrl_z(keyval, state) else None
        else:
            action = self.key_actions().get(keyval)
        if action is None:
            return False
        # Held down, D would thin the collection one photograph per
        # repeat, each deleted as the neighbour of the last.
        if not (repeat and keyval in DELETE_KEYS):
            action(None)
        return True
