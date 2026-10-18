"""The window shell: the collection grid, the elsewhere row, and the plate.

There is no full-bleed hero here any more -- the wallpaper is already on
the desktop, and this window opens on what you have saved. Issue #1's
split landed as these modules rather than as an extraction of the old
plate and strip.
"""

from __future__ import annotations

import argparse
import threading

import gi

from ..cli import cmd_fetch
from ..desktop import push_wallpaper
from ..library import (
    TRASHED,
    current_image,
    delete_photo,
    prune,
    restore,
    set_wallpaper,
)
from ..paths import GUIDE_SEEN
from .elsewhere import ElsewhereBar
from .grid import CollectionGrid
from .plate import Plate
from .settings import SettingsPanel
from .sheets import guide_sheet, shortcuts_sheet
from .style import palette, stylesheet
from .thumbs import dimensions

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

UNDO_SECONDS = 7


class Window(Adw.ApplicationWindow):
    def __init__(self, app):  # noqa: PLR0915 — GTK widget tree, one constructor
        super().__init__(application=app, title="Wallhelper")
        self.set_default_size(1120, 760)
        self.add_css_class("wallhelper")
        self.current = None
        self.push_lock = threading.Lock()
        self.wanted = None
        self.url = ""
        self.undoable = None         # (toast, Deleted) while UNDO is on offer
        self.held = set()            # keycodes pressed and not yet released

        css = Gtk.CssProvider()
        css.load_from_data(stylesheet(palette()).encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.pointer = Gdk.Cursor.new_from_name("pointer", None)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toasts.set_child(outer)

        top = Gtk.Box(halign=Gtk.Align.FILL, valign=Gtk.Align.START)
        top.add_css_class("top-scrim")
        corner = Gtk.Box(spacing=18, halign=Gtk.Align.END, hexpand=True)
        top.append(corner)
        for text, tip, handler in (
            ("SETTINGS", "Sources and housekeeping  (,)",
             self.open_settings),
            ("?", "Keyboard shortcuts  (?)", self.open_shortcuts),
        ):
            button = Gtk.Button(label=text, tooltip_text=tip,
                                valign=Gtk.Align.CENTER)
            button.add_css_class("plate-action")
            button.add_css_class("corner-action")
            button.set_cursor(self.pointer)
            button.connect("clicked", handler)
            corner.append(button)

        close = Gtk.Button(
            icon_name="window-close-symbolic", tooltip_text="Close  (Esc)",
        )
        close.add_css_class("circular")
        close.add_css_class("close-btn")
        close.connect("clicked", lambda _b: self.close())
        corner.append(close)
        outer.append(top)

        self.elsewhere = ElsewhereBar(self.pointer, self.on_adopt, self.toast)
        outer.append(self.elsewhere)

        self.grid = CollectionGrid(self.pointer, self.on_pick)
        outer.append(self.grid)

        self.plate = Plate(self.pointer, self.on_delete, self.on_source)
        outer.append(self.plate)

        overlay = Gtk.Overlay()
        # Sheets stack over everything; the window's own chrome is below.
        self.toasts.set_child(overlay)
        overlay.set_child(outer)

        self.settings_panel = SettingsPanel(self.pointer, self.close_overlays)
        self.shortcuts_panel = shortcuts_sheet(self.close_overlays)
        self.guide_panel = guide_sheet(self.pointer, self.close_overlays)
        for panel in (self.settings_panel, self.shortcuts_panel,
                      self.guide_panel):
            overlay.add_overlay(panel)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        keys.connect("key-released", self.on_key_released)
        self.add_controller(keys)
        # A release that lands elsewhere (focus moved) would leave its key
        # looking held.
        self.connect("notify::is-active", lambda *_a: self.held.clear())

        self.refresh()
        self.elsewhere.reload()
        # Off the main thread: it asks gio what the Trash holds.
        threading.Thread(target=prune, daemon=True).start()
        if not GUIDE_SEEN.exists():
            GLib.timeout_add(620, self.open_guide)

    def show_panel(self, panel, shown):
        panel.set_reveal_child(shown)
        panel.set_can_target(shown)

    def open_guide(self, _button=None):
        self.show_panel(self.settings_panel, False)
        self.show_panel(self.shortcuts_panel, False)
        self.show_panel(self.guide_panel, True)
        try:
            GUIDE_SEEN.parent.mkdir(parents=True, exist_ok=True)
            GUIDE_SEEN.touch()
        except OSError:
            pass                 # shows again next time, which is fine
        return False

    def open_settings(self, _button=None):
        self.show_panel(self.guide_panel, False)
        self.show_panel(self.shortcuts_panel, False)
        self.show_panel(self.settings_panel, True)
        # Not a source row: Enter or Space straight after `,` would switch
        # that source off.
        self.set_focus(self.settings_panel.shut)
        return False

    def open_shortcuts(self, _button=None):
        self.show_panel(self.settings_panel, False)
        self.show_panel(self.guide_panel, False)
        self.show_panel(self.shortcuts_panel, True)
        return False

    def close_overlays(self):
        self.show_panel(self.guide_panel, False)
        self.show_panel(self.settings_panel, False)
        self.show_panel(self.shortcuts_panel, False)
        return False

    def toast(self, text, timeout=2, priority=Adw.ToastPriority.NORMAL):
        self.toasts.add_toast(
            Adw.Toast(title=text, timeout=timeout, priority=priority))

    def offer_undo(self, gone):
        """The delete toast, with UNDO for as long as it is up. U does the
        same, so nothing here needs the pointer."""
        self.withdraw_undo()
        toast = Adw.Toast(
            title=f"{gone.title} — moved to Trash", timeout=UNDO_SECONDS,
            button_label="UNDO", priority=Adw.ToastPriority.HIGH,
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

    def refresh(self, current=None):
        self.current = current or current_image()
        size = dimensions(self.current) if self.current else ""
        self.plate.refresh(self.current, size)
        self.url = self.plate.url
        self.grid.refresh(self.current)

    def push(self, image):
        """Serialised, latest-wins. Holding an arrow down otherwise queues
        a 70ms hyprpaper round trip per frame."""
        self.wanted = image

        def work():
            with self.push_lock:
                target = self.wanted
                if target is not None:
                    push_wallpaper(target)

        threading.Thread(target=work, daemon=True).start()

    def on_pick(self, _btn, path):
        try:
            set_wallpaper(path, push=False)
        except OSError:
            self.toast("That file is gone")
            self.refresh()
            return
        self.push(path)
        self.refresh(path)

    def on_adopt(self, path, _cand):
        try:
            set_wallpaper(path, push=False)
        except OSError:
            self.toast("Saved, but the wallpaper did not take")
            self.refresh()
            return
        self.push(path)
        self.refresh(path)
        self.toast("Saved and set")
        self.elsewhere.reload()

    def on_source(self, _btn):
        if self.url:
            Gtk.UriLauncher(uri=self.url).launch(self, None, None, None)

    def on_delete(self, _button=None):
        if self.current is None:
            return
        # The photograph the plate is showing, not whatever hyprpaper
        # reports: a pick is pushed on a thread, so the two can disagree.
        try:
            gone = delete_photo(self.current)
        except ValueError:
            self.toast("That one is not in the collection")
        except OSError:
            self.toast("Couldn't delete that one")
        else:
            if gone.how == TRASHED:
                self.offer_undo(gone)
            else:
                self.toast(f"{gone.title} — deleted for good, "
                           "the Trash refused it", timeout=UNDO_SECONDS,
                           priority=Adw.ToastPriority.HIGH)
        self.refresh()

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
                       "the Trash", timeout=UNDO_SECONDS)
            return
        self.on_pick(None, gone.path)
        self.toast(f"{gone.title} — restored")

    def on_fetch(self, _button=None):
        def work():
            rc = cmd_fetch(argparse.Namespace(wait=False))
            GLib.idle_add(done, rc)

        def done(rc):
            if rc != 0:
                self.toast("Couldn't reach the morning source")
            self.refresh()

        threading.Thread(target=work, daemon=True).start()

    def on_key_released(self, _controller, _keyval, code, _state):
        self.held.discard(code)

    def on_key(self, _controller, keyval, code, _state):
        # GTK4 sends an auto-repeat as more presses with no release between
        # them, and says nothing else to tell it from a fresh one.
        repeat = code in self.held
        self.held.add(code)

        # BUBBLE phase, so a focused entry has already had its go at the
        # key -- but settings has text fields, and a stray 'd' there must
        # type a d, not delete a photo.
        typing = isinstance(self.get_focus(), (Gtk.Entry, Gtk.Text))

        if keyval == Gdk.KEY_Escape:
            if (self.settings_panel.get_reveal_child()
                    or self.shortcuts_panel.get_reveal_child()
                    or self.guide_panel.get_reveal_child()):
                self.close_overlays()
            else:
                self.close()
            return True

        if (self.shortcuts_panel.get_reveal_child()
                or self.guide_panel.get_reveal_child()):
            self.close_overlays()      # any key dismisses either sheet
            return True

        if self.settings_panel.get_reveal_child():
            # A source row is a button, so D or F would act on the window
            # behind the panel. Settings answers Esc, and the keys of the
            # widget that has focus, and nothing else.
            return False

        if typing:
            return False

        actions = {
            Gdk.KEY_question: self.open_shortcuts,
            Gdk.KEY_g: self.open_guide, Gdk.KEY_G: self.open_guide,
            Gdk.KEY_comma: self.open_settings,
            Gdk.KEY_d: self.on_delete, Gdk.KEY_D: self.on_delete,
            Gdk.KEY_u: self.on_undo, Gdk.KEY_U: self.on_undo,
            Gdk.KEY_e: self.elsewhere.toggle, Gdk.KEY_E: self.elsewhere.toggle,
            Gdk.KEY_o: self.on_source, Gdk.KEY_O: self.on_source,
            Gdk.KEY_f: self.on_fetch, Gdk.KEY_F: self.on_fetch,
        }
        if keyval in actions:
            # Held down, D would thin the collection one photograph per
            # repeat, each deleted as the neighbour of the last.
            if not (repeat and keyval in (Gdk.KEY_d, Gdk.KEY_D)):
                actions[keyval](None)
            return True
        return False
