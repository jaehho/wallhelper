"""The window.

A wall label over a full-bleed photograph: the picture fills the frame, the
caption plate sits over the bottom of it, and the strip of everything you kept
runs along the foot. Words rather than icons, one accent colour, and the
desktop's own palette so it belongs to this machine rather than to GNOME.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .cli import cmd_delete, cmd_fetch, cmd_keep
from .config import BLURBS, apply_key, config, needs_setup, save_config
from .desktop import push_wallpaper
from .library import (
    canonical,
    collection,
    credits,
    current_image,
    images,
    label,
    measure,
    set_wallpaper,
)
from .paths import CONFIG, GUIDE_SEEN, KEPT, PALETTE, THUMBS
from .sources import host, probe_source


def palette() -> dict[str, str]:
    """The desktop's Solarized-OKLCH palette, so this window sits at the same
    hue as waybar and swaync instead of inventing its own."""
    out = {
        "crust": "#0c1315", "base": "#141c1e", "text": "#cfdadc",
        "overlay0": "#565f62", "overlay2": "#848e91", "blue": "#3f7dae",
        "maroon": "#aa5d64",
    }
    try:
        for line in PALETTE.read_text().splitlines():
            key, sep, value = line.partition("=")
            key = key.strip()
            if sep and key and not key.startswith("#"):
                out[key] = "#" + value.strip()
    except OSError:
        pass
    return out


def cmd_gui(args) -> int:
    """The GUI lives inside this function so `import gi` -- which pulls in GTK,
    libadwaita and a display connection -- never happens on the fetch/set/like
    paths that run from a timer and a keybind.

    It calls the commands directly rather than shelling out to itself, so
    there is one implementation of every behaviour and the CLI and the
    window cannot drift apart.

    The window has no header bar. There is exactly one piece of content
    here and it is a photograph; framing it in application chrome is the
    thing a picture frame exists not to do. So the photo bleeds to all four
    edges, cropped the same way hyprpaper will crop it -- what you see is the
    wallpaper, not a preview of it -- and the rest is a caption plate over the
    bottom. The cost is that close and drag have to be handled by hand, below.
    """
    import math
    import threading

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, GdkPixbuf, GLib, Gtk, Pango

    C = palette()
    THUMB_W, THUMB_H = 112, 63       # 16:9, filmstrip height

    # Two faces doing two jobs. The title is set like a caption on a print;
    # everything below it is tracked mono, because every one of those strings
    # is transcribed data -- a date out of a filename, a token out of a
    # tab-separated ledger. It reads like an archive card because it is one.
    DISPLAY = '"Adwaita Sans", sans-serif'
    DATA = '"JetBrainsMono NF", "JetBrainsMono Nerd Font", monospace'

    CSS = f"""
    window.paperboy {{ background: {C['crust']}; }}

    /* Scrim: transparent over the top of the photograph, opaque under the
       plate. Ends just short of solid so the image still shows through. */
    .plate {{
        background: linear-gradient(to top,
            alpha({C['crust']}, 0.97) 0%,
            alpha({C['crust']}, 0.94) 62%,
            alpha({C['crust']}, 0.72) 84%,
            alpha({C['crust']}, 0.00) 100%);
        padding: 72px 32px 26px 32px;
    }}

    .plate-title {{
        font-family: {DISPLAY};
        font-size: 31px; font-weight: 300; letter-spacing: -0.7px;
        color: {C['text']};
    }}
    .plate-place, .plate-row, .plate-action, .plate-empty {{
        font-family: {DATA};
        font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
    }}
    /* Three steps of emphasis, so the plate still has a hierarchy on a photo
       that came with no title and the accession line is all there is. */
    .plate-place {{ color: mix({C['overlay2']}, {C['text']}, 0.35); }}
    .plate-row   {{ color: {C['overlay2']}; }}
    .plate-empty {{ color: {C['overlay0']}; letter-spacing: 1.2px; }}

    /* Text controls, not icons: the plate is typographic throughout, and a
       word answers 'what does this do' where a glyph asks it. */
    .plate-action {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 3px 0; min-height: 0; min-width: 0;
        color: {C['overlay2']};
    }}
    .plate-action:hover {{ color: {C['text']}; }}
    .plate-action.danger:hover {{
        color: mix({C['maroon']}, {C['text']}, 0.45);
    }}
    .plate-action.on    {{ color: mix({C['blue']}, {C['text']}, 0.55); }}
    .plate-action:disabled {{ color: {C['overlay0']}; }}

    .plate-link {{ color: {C['overlay2']}; }}
    .plate-link:hover {{ color: {C['text']}; text-decoration: underline; }}

    .hairline {{ background: alpha({C['text']}, 0.10); min-height: 1px; }}

    /* Opacity says 'kept'. The accent rule says 'on screen now'. Two
       channels, two meanings, no badges. */
    .thumb-button {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 0; min-height: 0; min-width: 0;
        border-bottom: 2px solid transparent;
        opacity: 0.5; transition: opacity 140ms ease;
    }}
    .thumb-button.kept    {{ opacity: 1; }}
    .thumb-button:hover   {{ opacity: 1; }}
    .thumb-button.current {{ opacity: 1; border-bottom-color: {C['blue']}; }}
    .thumb {{
        border-radius: 2px;
        box-shadow: inset 0 0 0 1px alpha({C['text']}, 0.14);
    }}

    .close-btn {{
        background: alpha({C['crust']}, 0.55); color: {C['text']};
        border: none; box-shadow: none;
    }}
    .close-btn:hover {{ background: alpha({C['crust']}, 0.85); }}

    .hero {{ opacity: 0; transition: opacity 520ms ease-out; }}
    .hero.shown {{ opacity: 1; }}

    /* Settings and the shortcut list speak the plate's language: tracked mono
       labels, hairlines, words rather than switches. A stock GNOME
       preferences page in here would read as a different application. */
    .panel {{
        background: {C['crust']};
        border-left: 1px solid alpha({C['text']}, 0.10);
        box-shadow: -18px 0 44px alpha(black, 0.5);
        padding: 22px 26px 26px 26px;
    }}
    .panel-title, .section, .field-label, .chip {{
        font-family: {DATA};
        font-weight: 600; letter-spacing: 1.4px;
    }}
    .panel-title {{ font-size: 11px; color: {C['text']}; }}
    .section     {{ font-size: 10px;
                    color: mix({C['overlay2']}, {C['text']}, 0.35); }}
    .field-label {{ font-size: 9px;  color: {C['overlay0']}; }}
    .footnote    {{ font-family: {DISPLAY}; font-size: 11px;
                    color: {C['overlay0']}; }}

    .chip {{
        background: alpha({C['text']}, 0.07); background-image: none;
        border: none; box-shadow: none; border-radius: 2px;
        padding: 5px 9px; min-height: 0; min-width: 0;
        font-size: 10px; color: {C['overlay2']};
    }}
    .chip:hover {{ background: alpha({C['text']}, 0.14); color: {C['text']}; }}
    .chip.on {{
        background: alpha({C['blue']}, 0.32);
        color: mix({C['blue']}, {C['text']}, 0.7);
    }}

    .field, .field text {{
        background: none; background-image: none; box-shadow: none;
        color: {C['text']}; caret-color: {C['blue']};
    }}
    .field {{
        border: none; border-bottom: 1px solid alpha({C['text']}, 0.18);
        border-radius: 0; padding: 3px 0; min-height: 0;
        font-family: {DATA}; font-size: 11px; letter-spacing: 0.5px;
    }}
    .field:focus-within {{ border-bottom-color: {C['blue']}; }}

    /* The corner sits on bare photograph. A short scrim, the mirror of the
       plate's, keeps it legible over a bright sky. */
    .top-scrim {{
        background: linear-gradient(to bottom,
            alpha({C['crust']}, 0.70) 0%,
            alpha({C['crust']}, 0.34) 46%,
            alpha({C['crust']}, 0.00) 100%);
        padding: 13px 14px 52px 14px;
    }}

    /* Unlike the plate, the corner can end up over white cloud, where the
       plate's mid-grey disappears. Full-strength text plus a shadow, so it
       reads on any photograph. */
    .corner-action {{
        color: {C['text']};
        text-shadow: 0 1px 4px alpha(black, 0.75);
    }}
    .corner-action:hover {{ color: white; }}

    .backdrop {{ background: alpha({C['crust']}, 0.62); }}
    .shortcuts {{
        background: {C['crust']};
        border: 1px solid alpha({C['text']}, 0.16);
        box-shadow: 0 16px 52px alpha(black, 0.55);
        border-radius: 3px; padding: 26px 32px;
    }}
    .key {{
        font-family: {DATA}; font-size: 11px; font-weight: 600;
        letter-spacing: 1px;
        color: mix({C['blue']}, {C['text']}, 0.55);
    }}
    .key-alt {{ color: {C['overlay0']}; }}

    .guide {{
        background: {C['crust']};
        border: 1px solid alpha({C['text']}, 0.16);
        border-radius: 3px;
        box-shadow: 0 16px 52px alpha(black, 0.55);
        padding: 40px 46px 32px 46px;
    }}
    .guide-thesis {{
        font-family: {DISPLAY}; font-size: 33px; font-weight: 300;
        letter-spacing: -0.8px; color: {C['text']};
    }}
    .guide-sub, .guide-body {{
        font-family: {DISPLAY}; font-size: 13px; color: {C['overlay2']};
    }}
    .guide-when {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 1.5px;
        color: mix({C['blue']}, {C['text']}, 0.55);
    }}
    .guide-foot {{
        font-family: {DISPLAY}; font-size: 12px; color: {C['overlay0']};
    }}
    .key-action {{ font-family: {DISPLAY}; font-size: 13px;
                   color: {C['text']}; }}

    /* A whole row is the target -- a source is a name you turn on, not a
       property with a switch beside it. */
    .source-row {{
        background: none; background-image: none;
        border: none; box-shadow: none; border-radius: 2px;
        padding: 10px 9px; min-height: 0;
    }}
    .source-row:hover {{ background: alpha({C['text']}, 0.06); }}
    /* Hangs off the row it belongs to, sharing its left edge with the
       numbers, so it reads as that source still talking. */
    .key-card {{
        border-left: 1px solid alpha({C['blue']}, 0.45);
        padding: 4px 0 4px 16px;
    }}

    .source-row:focus {{
        outline: none;
        background: alpha({C['text']}, 0.06);
        box-shadow: inset 2px 0 0 0 {C['blue']};
    }}

    .status {{ font-family: {DISPLAY}; font-size: 11px; }}
    .status-ok  {{ color: {C['overlay0']}; }}
    .status-bad {{ color: mix({C['maroon']}, {C['text']}, 0.4); }}

    .key-name {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 0.8px; color: mix({C['overlay2']}, {C['text']}, 0.3);
    }}
    """

    def tracked(text: str) -> str:
        return text.upper()

    def thumbnail(path: Path):
        """Exactly THUMB_W x THUMB_H, centre-cropped, cached on disk.

        Decoding one costs ~200ms because the JPEG is decoded in full before
        being scaled; reading the cached PNG costs ~2ms. With twenty photos
        that is the difference between the strip appearing and the strip
        arriving. Keyed by name and invalidated by mtime.

        Not scale-to-fit. GdkPixbuf's aspect-preserving scale returns whatever
        shape the source is, and a Gtk.Picture takes its *natural* size from
        the pixbuf it holds -- a size request is only a floor. The strip
        scrolls horizontally, so there is always room for natural size, and a
        portrait photo came out a narrow sliver next to an oversized wide one.
        Cropping makes the row uniform by construction instead of asking the
        layout nicely.

        Decoded at 1x on purpose: the pixbuf's dimensions become the widget's
        natural size in logical units, so a 2x buffer would produce 2x-wide
        thumbnails rather than sharper ones.
        """
        cached = THUMBS / f"{path.name}.png"
        try:
            if cached.stat().st_mtime >= path.stat().st_mtime:
                return GdkPixbuf.Pixbuf.new_from_file(str(cached))
        except (OSError, GLib.Error):
            pass

        try:
            _fmt, src_w, src_h = GdkPixbuf.Pixbuf.get_file_info(str(path))
            if not src_w or not src_h:
                return None
            scale = max(THUMB_W / src_w, THUMB_H / src_h)
            buf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(path),
                max(THUMB_W, math.ceil(src_w * scale)),
                max(THUMB_H, math.ceil(src_h * scale)),
                True,
            )
            buf = buf.new_subpixbuf(
                (buf.get_width() - THUMB_W) // 2,
                (buf.get_height() - THUMB_H) // 2,
                THUMB_W, THUMB_H,
            )
        except (GLib.Error, TypeError, ValueError):
            return None

        try:
            THUMBS.mkdir(parents=True, exist_ok=True)
            tmp = cached.with_name(f".{path.name}.new")
            buf.savev(str(tmp), "png", [], [])
            tmp.replace(cached)
        except (OSError, GLib.Error):
            pass                     # a cold cache is slow, not broken
        return buf

    def dimensions(path: Path) -> str:
        size = measure(path)
        if size is None:
            try:
                _fmt, width, height = GdkPixbuf.Pixbuf.get_file_info(str(path))
                size = (width, height) if width and height else None
            except (GLib.Error, TypeError, ValueError):
                size = None
        return f"{size[0]} \u00d7 {size[1]}" if size else ""

    # A day's cycle, which is what there is to explain. Not a feature tour:
    # the only genuinely surprising behaviour is that not keeping a photograph
    # deletes it, so that is the middle beat and everything else is context.
    GUIDE = (
        ("EACH MORNING",
         "A new photograph arrives and becomes your wallpaper. "
         "Press N if you want a different one today."),
        ("WHEN YOU LIKE ONE",
         "Press K to keep it. Anything you don't keep is deleted when the "
         "next photograph arrives \u2014 there is no countdown and nothing "
         "to tidy up later. Once a photo is kept, the same key is how you "
         "delete it."),
        ("OVER TIME",
         "The strip along the bottom is what you kept. Bright means kept, "
         "and the blue rule marks the one on screen. Walk it with H and L."),
    )

    SHORTCUTS = (
        ("H   L", "\u2190  \u2192", "Move through the strip"),
        ("K", "", "Keep this photo \u00b7 delete it once kept"),
        ("N", "", "Fetch a different photo"),
        ("O", "", "Open the source page"),
        (",", "", "Settings"),
        ("?", "", "This list"),
        ("G", "", "Show the welcome guide"),
        ("Esc", "", "Close"),
    )

    class Window(Adw.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app, title="Paperboy")
            self.set_default_size(1120, 760)
            self.add_css_class("paperboy")
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
            css.load_from_data(CSS.encode())
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
            overlay.add_overlay(self.build_settings())
            overlay.add_overlay(self.build_shortcuts())
            overlay.add_overlay(self.build_guide())

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

        # --- settings ----------------------------------------------------

        def build_settings(self):
            """Sources, switched on and off by clicking their name.

            This panel has been a JSON editor and it has been a wall of
            fields, and both were the same mistake in opposite directions:
            they put the file\u2019s vocabulary in the window. The file is
            better at being a file. What the window is better at is the one
            question you actually open it to answer \u2014 which sources am I
            using, and are they working.
            """
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
            shut.connect("clicked", lambda _b: self.close_overlays())
            head.append(shut)
            column.append(head)

            self.section(column, "SOURCES")
            self.source_list = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0, margin_top=4)
            column.append(self.source_list)

            note = Gtk.Label(
                label="Numbered in the order they are tried. The first one "
                      "with a photograph for today wins, so the rest are a "
                      "fallback \u2014 click a name to switch it on or off.",
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

            path = Gtk.Label(
                label=str(CONFIG).replace(str(Path.home()), "~"),
                xalign=0, wrap=True, wrap_mode=Pango.WrapMode.CHAR,
                selectable=True)
            path.add_css_class("footnote")
            column.append(path)

            self.fill_sources()

            scroller = Gtk.ScrolledWindow(
                hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                child=column,
            )
            panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            panel.add_css_class("panel")
            panel.set_size_request(430, -1)
            panel.append(scroller)

            self.settings_panel = Gtk.Revealer(
                transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
                transition_duration=240, halign=Gtk.Align.END,
                valign=Gtk.Align.FILL, reveal_child=False, child=panel,
                can_target=False,
            )
            return self.settings_panel

        def fill_sources(self):
            """One row per source: the ones in use first, in the order they
            are tried, then the ones you could switch on."""
            while (child := self.source_list.get_first_child()):
                self.source_list.remove(child)

            cfg = config()
            on = [name for name in (cfg.get("sources") or [])
                  if isinstance(cfg.get(name), dict)]
            rest = [name for name, spec in cfg.items()
                    if name not in on and isinstance(spec, dict)
                    and spec.get("image")]
            self.source_notes = {}
            self.source_rows = {}
            self.first_row = None

            for name in on + rest:
                spec = cfg[name]
                row = Gtk.Button()
                row.add_css_class("source-row")
                row.set_cursor(self.pointer)
                row.set_tooltip_text(
                    f"Stop using {name}" if name in on else f"Use {name}")
                row.connect("clicked", self.on_toggle_source, name)
                if name not in on:
                    row.set_opacity(0.5)

                line = Gtk.Box(spacing=13)
                mark = Gtk.Label(
                    label=str(on.index(name) + 1) if name in on
                    else "\u00b7", valign=Gtk.Align.START)
                mark.add_css_class("chip")
                if name in on:
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
                self.source_list.append(row)
                self.source_rows[name] = row
                self.first_row = self.first_row or row

                token = needs_setup(spec)
                if token and (spec.get("key") or {}).get("into"):
                    self.source_list.append(self.key_card(name, spec, token))

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
                             Gtk.UriLauncher(uri=uri).launch(self, None,
                                                             None, None))
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
            on = [key for key in (cfg.get("sources") or [])
                  if isinstance(key, str)]
            if name not in on:
                # Pasting a key is the same sentence as "use this one".
                on.append(name)
                cfg["sources"] = on
            try:
                save_config(cfg)
            except OSError as problem:
                self.set_status(f"Not saved: {problem.strerror}", bad=True)
                return
            self.fill_sources()
            self.set_focus(self.source_rows.get(name) or self.first_row)
            self.set_status(f"{name} has its key and is switched on. "
                            f"Press CHECK to see what it has today.")

        def on_toggle_source(self, _button, name):
            cfg = config()
            on = [key for key in (cfg.get("sources") or [])
                  if isinstance(key, str)]
            if name in on:
                on.remove(name)
            else:
                on.append(name)
            cfg["sources"] = on
            try:
                save_config(cfg)
            except OSError as problem:
                self.set_status(f"Not saved: {problem.strerror}", bad=True)
                return
            self.fill_sources()
            # The row you just pressed no longer exists -- without this,
            # focus falls back to the top of the list every time.
            self.set_focus(self.source_rows.get(name) or self.first_row)
            if not on:
                self.set_status("No source is switched on. Tomorrow\u2019s "
                                "fetch will have nowhere to look.", bad=True)
            elif name in on and needs_setup(cfg.get(name) or {}):
                self.set_status(f"{name} needs a key before it can work; "
                                f"there is a box for it below the row.",
                                bad=True)
            elif name in on:
                self.set_status(f"Using {name}. Press CHECK to see what it "
                                f"has today.")
            else:
                self.set_status(f"No longer using {name}.")

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

        # --- shortcuts ----------------------------------------------------

        def build_shortcuts(self):
            grid = Gtk.Grid(row_spacing=13, column_spacing=30,
                            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            grid.add_css_class("shortcuts")
            for line, (keys, alt, action) in enumerate(SHORTCUTS):
                key = Gtk.Label(label=keys, xalign=1)
                key.add_css_class("key")
                grid.attach(key, 0, line, 1, 1)
                other = Gtk.Label(label=alt, xalign=1)
                other.add_css_class("key")
                other.add_css_class("key-alt")
                grid.attach(other, 1, line, 1, 1)
                what = Gtk.Label(label=action, xalign=0)
                what.add_css_class("key-action")
                grid.attach(what, 2, line, 1, 1)

            backdrop = Gtk.Box(hexpand=True, vexpand=True)
            backdrop.add_css_class("backdrop")
            backdrop.append(grid)
            grid.set_hexpand(True)
            grid.set_vexpand(True)
            dismiss = Gtk.GestureClick()
            dismiss.connect("pressed", lambda *_a: self.close_overlays())
            backdrop.add_controller(dismiss)

            # can_target=False is the whole ballgame. This revealer fills
            # the overlay so its backdrop can dim everything, and a Gtk.Overlay
            # child keeps its allocation whether or not the revealer is showing
            # its child -- so while hidden it still sat on top of the window
            # swallowing every click. Keys were unaffected, which is why this
            # looked like a settings bug rather than a dead window.
            self.shortcuts_panel = Gtk.Revealer(
                transition_type=Gtk.RevealerTransitionType.CROSSFADE,
                transition_duration=160, hexpand=True, vexpand=True,
                halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
                reveal_child=False, child=backdrop, can_target=False,
            )
            return self.shortcuts_panel

        def show_panel(self, panel, shown):
            panel.set_reveal_child(shown)
            panel.set_can_target(shown)

        def build_guide(self):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0,
                           halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            card.add_css_class("guide")
            card.set_size_request(620, -1)

            thesis = Gtk.Label(label="One photograph a day.", xalign=0)
            thesis.add_css_class("guide-thesis")
            card.append(thesis)

            sub = Gtk.Label(
                label="Bing, Wikipedia and NASA each publish one. "
                      "You get today's, every morning.",
                xalign=0, wrap=True, margin_top=10, max_width_chars=52,
            )
            sub.add_css_class("guide-sub")
            card.append(sub)

            rule = Gtk.Box(margin_top=26, margin_bottom=4)
            rule.add_css_class("hairline")
            card.append(rule)

            for when, what in GUIDE:
                row = Gtk.Box(spacing=26, margin_top=22)
                moment = Gtk.Label(label=when, xalign=0,
                                   valign=Gtk.Align.START, wrap=True)
                moment.add_css_class("guide-when")
                moment.set_size_request(150, -1)
                row.append(moment)
                body = Gtk.Label(label=what, xalign=0, wrap=True, hexpand=True,
                                 max_width_chars=48)
                body.add_css_class("guide-body")
                row.append(body)
                card.append(row)

            foot = Gtk.Box(spacing=12, margin_top=32)
            hint = Gtk.Label(
                label="SETTINGS is where you switch sources on and off. "
                      "? lists every shortcut.",
                xalign=0, wrap=True, hexpand=True, valign=Gtk.Align.CENTER,
                max_width_chars=46,
            )
            hint.add_css_class("guide-foot")
            foot.append(hint)
            start = Gtk.Button(label="START", valign=Gtk.Align.CENTER,
                               tooltip_text="Close the guide  (Esc)")
            start.add_css_class("plate-action")
            start.set_cursor(self.pointer)
            start.connect("clicked", lambda _b: self.close_overlays())
            foot.append(start)
            card.append(foot)

            backdrop = Gtk.Box(hexpand=True, vexpand=True)
            backdrop.add_css_class("backdrop")
            backdrop.append(card)
            dismiss = Gtk.GestureClick()
            dismiss.connect("pressed", lambda *_a: self.close_overlays())
            backdrop.add_controller(dismiss)

            self.guide_panel = Gtk.Revealer(
                transition_type=Gtk.RevealerTransitionType.CROSSFADE,
                transition_duration=200, hexpand=True, vexpand=True,
                halign=Gtk.Align.FILL, valign=Gtk.Align.FILL,
                reveal_child=False, child=backdrop, can_target=False,
            )
            return self.guide_panel

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
            self.set_focus(self.first_row if shown and self.first_row
                           else self.hero)

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

        def on_key(self, _controller, keyval, _code, _state):
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

    class App(Adw.Application):
        def __init__(self):
            super().__init__(application_id="dev.jaeho.Paperboy")

        def do_activate(self):
            (self.props.active_window or Window(self)).present()

    return App().run(None)
