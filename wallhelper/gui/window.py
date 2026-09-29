"""The window itself: the photograph, the caption plate, and the strip.

There is exactly one piece of content here and it is a photograph, so framing
it in application chrome is the thing a picture frame exists not to do. The
photo bleeds to all four edges, cropped the same way hyprpaper will crop it --
what you see is the wallpaper, not a preview of it -- and everything else is a
caption plate laid over the bottom. The cost is that close and drag have to be
handled by hand, below.
"""

from __future__ import annotations

import argparse
import shutil
import threading
from pathlib import Path

import gi

from ..cli import cmd_delete, cmd_fetch, cmd_keep
from ..desktop import push_wallpaper
from ..library import (
    canonical,
    collection,
    credits,
    current_image,
    images,
    label,
    set_wallpaper,
)
from ..paths import GUIDE_SEEN, KEPT
from .settings import SettingsPanel
from .sheets import guide_sheet, shortcuts_sheet
from .style import THUMB_H, THUMB_W, palette, stylesheet, tracked
from .thumbs import dimensions, thumbnail

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402


class Window(Adw.ApplicationWindow):
    def __init__(self, app):  # noqa: PLR0915 — GTK widget tree, one constructor
        super().__init__(application=app, title="Wallhelper")
        self.set_default_size(1120, 760)
        self.add_css_class("wallhelper")
        self.current: Path | None = None
        self.files: list[Path] = []
        self.kept = False
        self.slide = None
        self.thumbs: dict[str, object] = {}     # name -> scaled pixbuf
        self.buttons: dict[str, Gtk.Button] = {}
        self.strip_names: list[str] = []
        self.generation = 0
        self.push_lock = threading.Lock()
        self.wanted: Path | None = None

        css = Gtk.CssProvider()
        css.load_from_data(stylesheet(palette()).encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.pointer = Gdk.Cursor.new_from_name("pointer", None)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)
        overlay = Gtk.Overlay()
        self.toasts.set_child(overlay)

        # The photograph is the window. COVER, so the crop matches
        # what hyprpaper does -- this is the wallpaper itself, not a
        # thumbnail of it.
        self.hero = Gtk.Picture(
            content_fit=Gtk.ContentFit.COVER, hexpand=True, vexpand=True,
            can_focus=True,
        )
        self.hero.add_css_class("hero")
        # No header bar means no drag handle; the image has to be one.
        overlay.set_child(Gtk.WindowHandle(child=self.hero))

        # App-level actions live in the corner; the plate below is about
        # the photograph. Words, not icons, like everything else here.
        corner = Gtk.Box(spacing=18, halign=Gtk.Align.END, hexpand=True)
        top = Gtk.Box(halign=Gtk.Align.FILL, valign=Gtk.Align.START)
        top.add_css_class("top-scrim")
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
        overlay.add_overlay(top)

        overlay.add_overlay(self.build_plate())
        self.settings_panel = SettingsPanel(self.pointer,
                                            self.close_overlays)
        self.shortcuts_panel = shortcuts_sheet(self.close_overlays)
        self.guide_panel = guide_sheet(self.pointer, self.close_overlays)
        for panel in (self.settings_panel, self.shortcuts_panel,
                      self.guide_panel):
            overlay.add_overlay(panel)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)

        self.refresh()
        # Park focus on the photograph. Left unset, GTK hands it to the
        # first control it finds -- SETTINGS -- and the first key press
        # then draws a focus ring round it, which reads as a selected
        # button. Tab still reaches everything from here.
        self.set_focus(self.hero)

        # One orchestrated moment: the photo fades up and the label rises
        # from the bottom edge, once, on open.
        settings = Gtk.Settings.get_default()
        if settings and settings.get_property("gtk-enable-animations"):
            GLib.timeout_add(40, self.reveal)
        else:
            self.revealer.set_transition_duration(0)
            self.reveal()

        # First run only, and after the plate has finished rising -- the
        # guide points at parts of a window you should have seen settle.
        if not GUIDE_SEEN.exists():
            GLib.timeout_add(620, self.open_guide)

    def build_plate(self):
        self.revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
            transition_duration=420,
            valign=Gtk.Align.END, reveal_child=False,
        )

        plate = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        plate.add_css_class("plate")
        self.revealer.set_child(plate)

        self.title = Gtk.Label(
            xalign=0, ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True,
        )
        self.title.add_css_class("plate-title")
        plate.append(self.title)

        self.place = Gtk.Label(
            xalign=0, ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True, margin_top=9,
        )
        self.place.add_css_class("plate-place")
        plate.append(self.place)

        # Accession line: what it is on the left, what you can do on the
        # right, one baseline.
        row = Gtk.Box(spacing=0, margin_top=12)
        plate.append(row)

        # Two groups, not one flat row: the metadata takes the width it
        # needs and only the last field ellipsizes, while the actions stay
        # pinned to the right padding whatever the caption is doing.
        facts = Gtk.Box(spacing=0, hexpand=True)
        row.append(facts)

        # Was the fetch date, which is a fact about this folder rather
        # than about the photograph -- and no better one exists, since both
        # sources strip EXIF. Pixel size at least says whether the photo
        # suits the screen it is about to cover.
        self.size = Gtk.Label(xalign=0)
        self.size.add_css_class("plate-row")
        facts.append(self.size)

        self.source = Gtk.Button(
            label="", tooltip_text="Open the source page")
        self.source.add_css_class("plate-action")
        self.source.add_css_class("plate-link")
        self.source.connect("clicked", self.on_source)
        self.source.set_cursor(self.pointer)
        facts.append(self.source)

        self.author = Gtk.Label(
            xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True,
        )
        self.author.add_css_class("plate-row")
        facts.append(self.author)

        # KEEP and DELETE were never both available in any useful sense:
        # a photo you don't keep is deleted tomorrow anyway, and a photo
        # you kept is one you have already said you want. So the plate
        # asks the only open question about the photo in front of you --
        # is it staying? -- and the answer to the last one becomes the
        # next one.
        self.act_btn = Gtk.Button(label="KEEP", margin_start=24)
        self.act_btn.add_css_class("plate-action")
        self.act_btn.connect("clicked", self.on_act)
        self.act_btn.set_cursor(self.pointer)
        row.append(self.act_btn)

        self.next_btn = Gtk.Button(
            label="NEXT", margin_start=26,
            tooltip_text="Fetch a different photo now",
        )
        self.next_btn.add_css_class("plate-action")
        self.next_btn.connect("clicked", self.on_next)
        self.next_btn.set_cursor(self.pointer)
        row.append(self.next_btn)

        rule = Gtk.Box(margin_top=22, margin_bottom=18)
        rule.add_css_class("hairline")
        plate.append(rule)

        # One strip, newest first: everything on disk, with the kept ones
        # bright. A separate 'kept' tab would have hidden the difference
        # behind a click, and split a collection that is really one
        # chronology.
        self.strip = Gtk.Box(spacing=8)
        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.NEVER,
            child=self.strip,
        )
        scroller.set_size_request(-1, THUMB_H + 4)
        self.scroller = scroller
        plate.append(scroller)

        self.empty = Gtk.Label(xalign=0, visible=False)
        self.empty.add_css_class("plate-empty")
        plate.append(self.empty)

        return self.revealer

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
        shown = not self.settings_panel.get_reveal_child()
        self.show_panel(self.settings_panel, shown)
        # Otherwise focus is still out on the photograph and reaching the
        # panel means tabbing through every thumbnail in the strip.
        first = self.settings_panel.first_row
        self.set_focus(first if shown and first else self.hero)

    def open_shortcuts(self, _button=None):
        self.show_panel(self.guide_panel, False)
        self.show_panel(self.settings_panel, False)
        self.show_panel(self.shortcuts_panel, True)

    def close_overlays(self):
        self.show_panel(self.guide_panel, False)
        self.show_panel(self.settings_panel, False)
        self.show_panel(self.shortcuts_panel, False)
        self.set_focus(self.hero)

    def step(self, delta):
        if not self.files:
            return
        names = [f.name for f in self.files]
        here = names.index(self.current.name) if (
            self.current and self.current.name in names) else -delta
        self.on_pick(None, self.files[(here + delta) % len(self.files)])

    def reveal(self):
        self.revealer.set_reveal_child(True)
        self.hero.add_css_class("shown")
        return False

    # --- render -----------------------------------------------------

    def show_hero(self, path: Path):
        """Decode off the main loop.

        set_filename() loaded the full 3840x2160 JPEG synchronously, so
        every arrow press froze the window for the length of a 4K decode.
        Gdk.Texture is also the fastest loader available here -- measured
        at 55ms against 139ms for a full GdkPixbuf and 230ms for a scaled
        one, since asking GdkPixbuf to scale makes it decode in full and
        then resample.
        """
        self.generation += 1
        token = self.generation

        def landed(tok, texture):
            if tok == self.generation:      # a later press already won
                self.hero.set_paintable(texture)
            return False

        def work():
            try:
                texture = Gdk.Texture.new_from_filename(str(path))
            except GLib.Error:
                return
            GLib.idle_add(landed, token, texture)

        threading.Thread(target=work, daemon=True).start()

    def refresh(self, current: Path | None = None):
        # A caller that just set the wallpaper already knows what it is.
        # Asking current_image() would re-derive it from two more hyprctl
        # spawns for an answer we were handed.
        self.current = current or current_image()
        info = label(self.current)

        if self.current and self.current.exists():
            self.show_hero(self.current)
        size = dimensions(self.current) if self.current else ""

        # No title line rather than a placeholder one. Suppressing
        # 'wallhaven 7jlq13' only to print 'Untitled' in its place would
        # trade one non-fact for another; a photograph nobody titled has
        # nothing to say here, and the plate shrinks to suit.
        title = info.get("title", "")
        if not self.current:
            title = "No wallpaper set"
        self.title.set_text(title)
        self.title.set_visible(bool(title))

        # The source token only appears when it can be a link, so the
        # fallback has to test what is on screen rather than what is in the
        # ledger -- otherwise a file with a recognisable name but no credit
        # line counted as identified and showed nothing at all.
        src, url = info.get("source", ""), info.get("url", "")
        named = bool(src and url)

        # Something always has to identify the photo. A file dropped into
        # the folder by hand has none of these, so it falls back to its own
        # name.
        place = info.get("place", "")
        if not (place or title or named):
            place = Path(info["file"]).stem
        self.place.set_text(tracked(place))
        self.place.set_visible(bool(place))
        self.place.set_margin_top(9 if title else 0)

        self.size.set_text(size)
        self.size.set_visible(bool(size))

        self.source.set_label(tracked(src))
        self.source.set_visible(named)
        self.source.set_margin_start(18 if size else 0)
        self.url = url

        author = info.get("author", "")
        self.author.set_text(tracked(f"© {author}") if author else "")
        self.author.set_visible(bool(author))
        self.author.set_margin_start(18 if (size or named) else 0)

        self.kept = info.get("kept") == "yes"

        # Not "is it kept" but "is it leaving on its own". A photo this
        # tool downloaded and you didn't keep goes with the next sweep;
        # anything else -- kept, or dropped into the folder by hand --
        # stays until somebody removes it.
        self.leaving = bool(self.current) and not self.kept \
            and self.current.name in credits()

        self.act_btn.set_label("KEEP" if self.leaving else "DELETE")
        self.act_btn.set_sensitive(self.current is not None)
        self.act_btn.set_tooltip_text(
            "Keep this photo, or it goes when the next one arrives  (K)"
            if self.leaving else "Delete this photo for good  (K)"
        )
        if self.leaving:
            self.act_btn.remove_css_class("danger")
        else:
            self.act_btn.add_css_class("danger")

        self.load_strip()

    def load_strip(self):
        """Rebuild only when the set of files changed.

        Changing wallpaper changes which thumbnail is marked, not which
        thumbnails exist -- but this used to tear down every button and
        re-read every file from disk on each arrow press.
        """
        self.files = collection()
        names = [path.name for path in self.files]

        self.scroller.set_visible(bool(names))
        self.empty.set_visible(not names)
        if not names:
            self.empty.set_text(tracked("Nothing downloaded yet"))

        if names != self.strip_names:
            self.build_strip()
            self.strip_names = names
        self.mark_strip()

    def build_strip(self):
        while (child := self.strip.get_first_child()) is not None:
            self.strip.remove(child)
        self.buttons.clear()

        live = {path.name for path in self.files}
        for stale in [name for name in self.thumbs if name not in live]:
            del self.thumbs[stale]

        meta = credits()
        pending = []
        for path in self.files:
            pic = Gtk.Picture(
                content_fit=Gtk.ContentFit.COVER,
                width_request=THUMB_W, height_request=THUMB_H,
            )
            pic.add_css_class("thumb")
            cached = self.thumbs.get(path.name)
            if cached is not None:
                pic.set_pixbuf(cached)
            else:
                pending.append((path, pic))
            button = Gtk.Button(
                child=pic, hexpand=False, vexpand=False,
                valign=Gtk.Align.START,
            )
            button.add_css_class("thumb-button")
            title = meta.get(path.name, ("", "", ""))[0]
            button.set_tooltip_text(title or path.name)
            button.connect("clicked", self.on_pick, path)
            button.set_cursor(self.pointer)
            self.strip.append(button)
            self.buttons[path.name] = button

        if pending:
            # Only the ones we have never decoded; a folder of 4K JPEGs is
            # otherwise a visible stall before the window paints.
            threading.Thread(
                target=self._decode, args=(pending,), daemon=True
            ).start()

    def mark_strip(self):
        """Opacity says kept, the accent rule says on screen now."""
        kept = {path.name for path in images(KEPT)}
        here = self.current.name if self.current else None
        for name, button in self.buttons.items():
            for style, on in (("kept", name in kept),
                              ("current", name == here)):
                if on:
                    button.add_css_class(style)
                else:
                    button.remove_css_class(style)
        GLib.idle_add(self.scroll_to_current)

    def scroll_to_current(self, tries=6):
        """Walk off the edge of the strip and the strip follows.

        Idle, and willing to wait: right after a rebuild the buttons have
        no allocation yet, so measuring immediately puts the marked
        thumbnail at x=0 and scrolls to the wrong place.
        """
        button = self.buttons.get(self.current.name) if self.current \
            else None
        adjust = self.scroller.get_hadjustment()
        page = adjust.get_page_size()
        if button is None or not page:
            if tries and button is not None:
                GLib.idle_add(self.scroll_to_current, tries - 1)
            return False

        found, bounds = button.compute_bounds(self.strip)
        if not found:
            return False
        edge = 26                      # a hint of the next one along
        left = bounds.get_x() - edge
        right = bounds.get_x() + bounds.get_width() + edge
        value = adjust.get_value()
        if left < value:
            target = max(adjust.get_lower(), left)
        elif right > value + page:
            target = min(adjust.get_upper() - page, right - page)
        else:
            return False
        self.glide(adjust, target)
        return False

    def glide(self, adjust, target):
        """Jumping the strip loses the thread of where the marked
        thumbnail went; 260ms of travel keeps it."""
        if self.slide is not None:
            self.slide.pause()
        self.slide = Adw.TimedAnimation(
            widget=self.scroller, value_from=adjust.get_value(),
            value_to=target, duration=260,
            easing=Adw.Easing.EASE_OUT_CUBIC,
            target=Adw.PropertyAnimationTarget.new(adjust, "value"),
        )
        self.slide.play()

    def _decode(self, items):
        for path, pic in items:
            buf = thumbnail(path)
            if buf is not None:
                self.thumbs[path.name] = buf
                GLib.idle_add(pic.set_pixbuf, buf)

    # --- actions ----------------------------------------------------

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=2))

    def on_key(self, _controller, keyval, _code, _state):  # noqa: PLR0911 — early returns for each failure mode
        # BUBBLE phase, so a focused entry has already had its go at the
        # key -- but settings has text fields, and a stray 'n' there must
        # type an n, not fetch a new photo. Belt and braces.
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

        if typing:
            return False

        actions = {
            Gdk.KEY_question: self.open_shortcuts,
            Gdk.KEY_g: self.open_guide, Gdk.KEY_G: self.open_guide,
            Gdk.KEY_comma: self.open_settings,
            Gdk.KEY_k: self.on_act, Gdk.KEY_K: self.on_act,
            Gdk.KEY_n: self.on_next, Gdk.KEY_N: self.on_next,
            Gdk.KEY_o: self.on_source, Gdk.KEY_O: self.on_source,
        }
        if keyval in actions:
            actions[keyval](None)
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_h, Gdk.KEY_H):
            self.step(-1)
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_l, Gdk.KEY_L):
            self.step(1)
            return True
        return False

    def on_source(self, _btn):
        if self.url:
            Gtk.UriLauncher(uri=self.url).launch(self, None, None, None)

    def on_act(self, _btn=None):
        if self.current is None:
            return
        if self.leaving:
            cmd_keep(argparse.Namespace(undo=False))
            self.refresh()
            self.toast("Kept \u2014 the same button deletes it now")
        else:
            self.on_delete()

    def on_delete(self, _button=None):
        if self.current is None:
            return
        name = label(self.current).get("title") or self.current.stem
        failed = cmd_delete(argparse.Namespace()) != 0
        self.refresh()
        if failed:
            self.toast("Couldn't delete that one")
        elif shutil.which("gio"):
            self.toast(f"{name} \u2014 moved to Trash")
        else:
            self.toast(f"Deleted {name}")

    def push(self, image: Path):
        """Serialised, latest-wins. Holding an arrow down otherwise queues
        a 70ms hyprpaper round trip per frame; each worker takes whatever
        is current when its turn comes, so a burst collapses."""
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
        self.refresh(canonical(path))

    def on_next(self, _btn):
        self.next_btn.set_sensitive(False)
        self.next_btn.set_label("FETCHING")

        def work():
            rc = cmd_fetch(argparse.Namespace(next=True, wait=False))
            GLib.idle_add(done, rc)

        def done(rc):
            self.next_btn.set_label("NEXT")
            self.next_btn.set_sensitive(True)
            if rc != 0:
                self.toast("Couldn't reach Bing or wallhaven")
            self.refresh()

        threading.Thread(target=work, daemon=True).start()
