"""The settings panel: which sources am I using, and are they working."""

from __future__ import annotations

import threading
from pathlib import Path

import gi

from ..config import (
    BLURBS,
    apply_key,
    config,
    ensure_config,
    needs_setup,
    save_config,
    settings_lists,
    toggle_source,
)
from ..paths import CONFIG
from ..sources import host, probe_source

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk, Pango  # noqa: E402


class SettingsPanel(Gtk.Revealer):
    """Sources, switched on and off by clicking their name.

    This panel has been a JSON editor and it has been a wall of fields, and
    both were the same mistake in opposite directions: they put the file's
    vocabulary in the window. The file is better at being a file. What the
    window is better at is the one question you actually open it to answer --
    which sources am I using, and are they working.
    """

    def __init__(self, pointer, on_close):
        super().__init__(
            transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
            transition_duration=240, halign=Gtk.Align.END,
            valign=Gtk.Align.FILL, reveal_child=False, can_target=False,
        )
        self.pointer = pointer
        self.on_close = on_close
        self.build()

    def build(self):
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        head = Gtk.Box()
        heading = Gtk.Label(label="SETTINGS", xalign=0, hexpand=True,
                            valign=Gtk.Align.CENTER)
        heading.add_css_class("panel-title")
        head.append(heading)
        shut = Gtk.Button(icon_name="window-close-symbolic",
                          tooltip_text="Close settings  (Esc)")
        shut.add_css_class("circular")
        shut.add_css_class("close-btn")
        shut.set_cursor(self.pointer)
        shut.connect("clicked", lambda _b: self.on_close())
        head.append(shut)
        self.shut = shut
        column.append(head)

        self.section(column, "MORNING")
        self.auto_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0, margin_top=4)
        column.append(self.auto_list)

        self.section(column, "ELSEWHERE")
        self.gallery_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0, margin_top=4)
        column.append(self.gallery_list)

        note = Gtk.Label(
            label="Morning is Bing's picture of the day. Elsewhere is for "
                  "when you want a change by hand. Click a name to switch "
                  "it on or off. Moving a source between the two lists is "
                  "a config.json edit \u2014 the file is better at being a file.",
            xalign=0, wrap=True, max_width_chars=44, margin_top=16,
        )
        note.add_css_class("footnote")
        column.append(note)

        check = Gtk.Button(
            label="CHECK", halign=Gtk.Align.START, margin_top=22,
            tooltip_text="Ask every source what it has today, "
                         "without downloading anything",
        )
        check.add_css_class("plate-action")
        check.set_cursor(self.pointer)
        check.connect("clicked", self.on_check)
        column.append(check)

        self.status = Gtk.Label(xalign=0, wrap=True, margin_top=12,
                                max_width_chars=44, visible=False)
        self.status.add_css_class("status")
        self.status.add_css_class("status-ok")
        column.append(self.status)

        rule = Gtk.Box(margin_top=34, margin_bottom=12)
        rule.add_css_class("hairline")
        column.append(rule)

        column.append(self.config_row())

        self.fill_sources()

        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
            child=column,
        )
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("panel")
        panel.set_size_request(430, -1)
        panel.append(scroller)

        self.set_child(panel)

    def config_row(self):
        """Where the file is, and a way to open it."""
        path = Gtk.Label(
            label=str(CONFIG).replace(str(Path.home()), "~"),
            xalign=0, wrap=True, wrap_mode=Pango.WrapMode.CHAR,
            selectable=True, hexpand=True, valign=Gtk.Align.CENTER)
        path.add_css_class("footnote")
        edit = Gtk.Button(
            label="EDIT", valign=Gtk.Align.CENTER,
            tooltip_text="Open config.json in your text editor",
        )
        edit.add_css_class("plate-action")
        edit.set_cursor(self.pointer)
        edit.connect("clicked", self.on_edit)
        row = Gtk.Box(spacing=16)
        row.append(path)
        row.append(edit)
        return row

    def fill_sources(self):
        """MORNING lists the morning sources, on or off; ELSEWHERE the
        gallery and anything else defined that you could switch on."""
        for box in (self.auto_list, self.gallery_list):
            while (child := box.get_first_child()):
                box.remove(child)

        cfg = config()
        morning, elsewhere = settings_lists(cfg)
        self.source_notes = {}
        self.source_rows = {}
        self.first_row = None

        for name in morning:
            self._row(self.auto_list, name, cfg[name],
                      name in (cfg.get("autofetch") or []), "autofetch")
        for name in elsewhere:
            self._row(self.gallery_list, name, cfg[name],
                      name in (cfg.get("gallery") or []), "gallery")

    def _row(self, box, name, spec, on, which):
        row = Gtk.Button()
        row.add_css_class("source-row")
        row.set_cursor(self.pointer)
        row.set_tooltip_text(
            f"Stop using {name}" if on else f"Use {name}")
        row.connect("clicked", self.on_toggle_source, name, which)
        if not on:
            row.set_opacity(0.5)

        line = Gtk.Box(spacing=13)
        mark = Gtk.Label(label="*" if on else "\u00b7",
                         valign=Gtk.Align.START)
        mark.add_css_class("chip")
        if on:
            mark.add_css_class("on")
        mark.set_size_request(15, -1)
        line.append(mark)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                       hexpand=True)
        title = Gtk.Label(label=name, xalign=0)
        title.add_css_class("key-name")
        text.append(title)
        note = Gtk.Label(
            label=BLURBS.get(name) or host(spec.get("url")),
            xalign=0, wrap=True, max_width_chars=40,
        )
        note.add_css_class("footnote")
        text.append(note)
        self.source_notes[name] = note
        line.append(text)

        row.set_child(line)
        box.append(row)
        self.source_rows[name] = row
        self.first_row = self.first_row or row

        token = needs_setup(spec)
        if token and (spec.get("key") or {}).get("into"):
            box.append(self.key_card(name, spec, token))

    def key_card(self, name, spec, token):
        """The gap between "switch this on" and "it works" is a signup
        page, an application form and a string to paste. All three belong
        here, in the row that is asking for them."""
        setup = spec.get("key") or {}
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       margin_start=28, margin_end=9,
                       margin_top=2, margin_bottom=14)
        card.add_css_class("key-card")

        note = Gtk.Label(label=setup.get("note") or f"{name} needs a key.",
                         xalign=0, wrap=True, max_width_chars=38)
        note.add_css_class("footnote")
        card.append(note)

        # In the order you do them: fetch the key, then paste it.
        if setup.get("get"):
            link = Gtk.Button(label="OPEN THE SIGNUP PAGE",
                              halign=Gtk.Align.START,
                              tooltip_text=setup["get"])
            link.add_css_class("plate-action")
            link.set_cursor(self.pointer)
            link.connect("clicked", lambda _b, uri=setup["get"]:
                         Gtk.UriLauncher(uri=uri).launch(
                             self.get_root(), None, None, None))
            card.append(link)

        paste = Gtk.Entry(placeholder_text="Paste the key here",
                          hexpand=True, activates_default=False)
        paste.add_css_class("field")
        paste.connect("activate", self.on_key_entered, name, token)

        row = Gtk.Box(spacing=16, margin_top=2)
        row.append(paste)
        save = Gtk.Button(label="SAVE", valign=Gtk.Align.CENTER,
                          tooltip_text=f"Put this key into {name}")
        save.add_css_class("plate-action")
        save.set_cursor(self.pointer)
        save.connect("clicked",
                     lambda _b: self.on_key_entered(paste, name, token))
        row.append(save)
        card.append(row)
        return card

    def on_key_entered(self, entry, name, token):
        value = entry.get_text().strip()
        if not value:
            self.set_status("Nothing pasted yet.", bad=True)
            return
        cfg = config()
        cfg[name] = apply_key(cfg.get(name) or {}, token, value)
        key = "autofetch" if name in settings_lists(cfg)[0] else "gallery"
        on = [item for item in (cfg.get(key) or [])
              if isinstance(item, str)]
        if name not in on:
            # Pasting a key is the same sentence as "use this one".
            on.append(name)
            cfg[key] = on
        try:
            save_config(cfg)
        except OSError as problem:
            self.set_status(f"Not saved: {problem.strerror}", bad=True)
            return
        self.fill_sources()
        self.get_root().set_focus(
                self.source_rows.get(name) or self.first_row)
        self.set_status(f"{name} has its key and is switched on. "
                        f"Press CHECK to see what it has today.")

    def on_toggle_source(self, _button, name, which):
        cfg = config()
        now_on = toggle_source(cfg, name, which)
        try:
            save_config(cfg)
        except OSError as problem:
            self.set_status(f"Not saved: {problem.strerror}", bad=True)
            return
        self.fill_sources()
        # The row you just pressed no longer exists -- without this,
        # focus falls back to the top of the list every time.
        self.get_root().set_focus(
                self.source_rows.get(name) or self.first_row)
        if not (cfg.get("autofetch") or []):
            self.set_status("No morning source is switched on. "
                            "Tomorrow\u2019s fetch will have nowhere to look.",
                            bad=True)
        elif now_on and needs_setup(cfg.get(name) or {}):
            self.set_status(f"{name} needs a key before it can work; "
                            f"there is a box for it below the row.",
                            bad=True)
        elif now_on:
            self.set_status(f"Using {name}. Press CHECK to see what it "
                            f"has today.")
        else:
            self.set_status(f"No longer using {name}.")

    def on_edit(self, _button=None):
        """The moves between lists are a file edit, so put the file in
        front of you rather than leaving you to find its path. The text
        editor, not the JSON handler: that is usually a browser."""
        try:
            ensure_config()
        except OSError as problem:
            self.set_status(f"Not opened: {problem.strerror}", bad=True)
            return
        editor = Gio.AppInfo.get_default_for_type("text/plain", False)
        try:
            opened = editor is not None and editor.launch(
                [Gio.File.new_for_path(str(CONFIG))],
                self.get_display().get_app_launch_context())
        except GLib.Error:
            opened = False
        if not opened:
            self.set_status("No text editor is set for plain text, so "
                            "open the file yourself.", bad=True)

    def on_check(self, _button=None):
        cfg = config()
        names = list(self.source_notes)
        self.set_status("Asking each source what it has today\u2026")

        def work():
            for name in names:
                ok, text = probe_source(name, cfg.get(name) or {})
                GLib.idle_add(self.show_check, name, ok, text)
            GLib.idle_add(self.set_status, "", False)

        threading.Thread(target=work, daemon=True).start()

    def show_check(self, name, ok, text):
        note = self.source_notes.get(name)
        if note is not None:
            note.set_text(text)      # not selectable: a selectable
            # label inside a button eats the click that toggles the row
            if ok:
                note.remove_css_class("status-bad")
            else:
                note.add_css_class("status-bad")
        return False

    def section(self, box, text):
        widget = Gtk.Label(label=text, xalign=0,
                           margin_top=28, margin_bottom=2)
        widget.add_css_class("section")
        box.append(widget)

    def set_status(self, text, bad=False):
        self.status.set_text(text)
        self.status.set_visible(bool(text))    # no reserved empty band
        self.status.set_selectable(bool(text))
        self.status.remove_css_class("status-ok" if bad else "status-bad")
        self.status.add_css_class("status-bad" if bad else "status-ok")
        return False
