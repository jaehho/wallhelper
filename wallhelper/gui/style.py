"""Palette, faces, and the stylesheet built from them.

The window borrows the desktop's own colours rather than shipping its own, so
it belongs to this machine. Two faces do two jobs: the title is set like a
caption on a print, and everything below it is tracked mono, because every one
of those strings is transcribed data -- a date out of a filename, a token out
of a tab-separated ledger. It reads like an archive card because it is one.
"""

from __future__ import annotations

from ..paths import PALETTE

DISPLAY = '"Adwaita Sans", sans-serif'
DATA = '"JetBrainsMono NF", "JetBrainsMono Nerd Font", monospace'

THUMB_W, THUMB_H = 112, 63       # 16:9, elsewhere row
GRID_W, GRID_H = 220, 124        # 16:9, collection tiles
LONG_TOAST_SECONDS = 7           # a toast with something to read in it


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


def tracked(text: str) -> str:
    return text.upper()


def stylesheet(colors: dict[str, str]) -> str:
    """Settings and the shortcut list speak the plate's language: tracked
    mono labels, hairlines, words rather than switches. A stock GNOME
    preferences page in here would read as a different application."""
    return f"""
    window.wallhelper {{ background: {colors['crust']}; }}

    /* Scrim: transparent over the top of the photograph, opaque under the
       plate. Ends just short of solid so the image still shows through. */
    .plate {{
        background: linear-gradient(to top,
            alpha({colors['crust']}, 0.97) 0%,
            alpha({colors['crust']}, 0.94) 62%,
            alpha({colors['crust']}, 0.72) 84%,
            alpha({colors['crust']}, 0.00) 100%);
        padding: 72px 32px 26px 32px;
    }}

    .plate-title {{
        font-family: {DISPLAY};
        font-size: 31px; font-weight: 300; letter-spacing: -0.7px;
        color: {colors['text']};
    }}
    .plate-place, .plate-row, .plate-action, .plate-empty {{
        font-family: {DATA};
        font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
    }}
    /* Three steps of emphasis, so the plate still has a hierarchy on a photo
       that came with no title and the accession line is all there is. */
    .plate-place {{ color: mix({colors['overlay2']}, {colors['text']}, 0.35); }}
    .plate-row   {{ color: {colors['overlay2']}; }}
    .plate-empty {{ color: {colors['overlay0']}; letter-spacing: 1.2px; }}

    /* Text controls, not icons: the plate is typographic throughout, and a
       word answers 'what does this do' where a glyph asks it. */
    .plate-action {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 3px 0; min-height: 0; min-width: 0;
        color: {colors['overlay2']};
    }}
    .plate-action:hover {{ color: {colors['text']}; }}
    .plate-action.danger:hover {{
        color: mix({colors['maroon']}, {colors['text']}, 0.45);
    }}
    .plate-action.on    {{ color: mix({colors['blue']}, {colors['text']}, 0.55); }}
    .plate-action:disabled {{ color: {colors['overlay0']}; }}

    .plate-link {{ color: {colors['overlay2']}; }}
    .plate-link:hover {{ color: {colors['text']}; text-decoration: underline; }}

    .hairline {{ background: alpha({colors['text']}, 0.10); min-height: 1px; }}

    /* The accent rule says 'on screen now'. One channel, one meaning. */
    .thumb-button, .grid-tile {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 0; min-height: 0; min-width: 0;
        border-bottom: 2px solid transparent;
        opacity: 0.72; transition: opacity 140ms ease;
    }}
    .thumb-button:hover, .grid-tile:hover {{ opacity: 1; }}
    .thumb-button.current, .grid-tile.current {{
        opacity: 1; border-bottom-color: {colors['blue']};
    }}
    .thumb {{
        border-radius: 2px;
        box-shadow: inset 0 0 0 1px alpha({colors['text']}, 0.14);
    }}

    .elsewhere-row {{
        padding: 10px 18px 6px 18px;
    }}
    .elsewhere-label {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 1.5px; color: {colors['overlay2']};
    }}

    /* A source with nothing to show, and why: quieter than the label it
       sits under, and not coloured like an alarm. */
    .elsewhere-note {{
        font-family: {DATA}; font-size: 10px; font-weight: 400;
        letter-spacing: 1.2px; color: {colors['overlay2']};
    }}

    .close-btn {{
        background: alpha({colors['crust']}, 0.55); color: {colors['text']};
        border: none; box-shadow: none;
    }}
    .close-btn:hover {{ background: alpha({colors['crust']}, 0.85); }}

    .hero {{ opacity: 0; transition: opacity 520ms ease-out; }}
    .hero.shown {{ opacity: 1; }}

    /* Settings and the shortcut list speak the plate's language: tracked mono
       labels, hairlines, words rather than switches. A stock GNOME
       preferences page in here would read as a different application. */
    .panel {{
        background: {colors['crust']};
        border-left: 1px solid alpha({colors['text']}, 0.10);
        box-shadow: -18px 0 44px alpha(black, 0.5);
        padding: 22px 26px 26px 26px;
    }}
    .panel-title, .section, .field-label, .chip {{
        font-family: {DATA};
        font-weight: 600; letter-spacing: 1.4px;
    }}
    .panel-title {{ font-size: 11px; color: {colors['text']}; }}
    .section     {{ font-size: 10px;
                    color: mix({colors['overlay2']}, {colors['text']}, 0.35); }}
    .field-label {{ font-size: 9px;  color: {colors['overlay0']}; }}
    .footnote    {{ font-family: {DISPLAY}; font-size: 11px;
                    color: {colors['overlay0']}; }}

    .chip {{
        background: alpha({colors['text']}, 0.07); background-image: none;
        border: none; box-shadow: none; border-radius: 2px;
        padding: 5px 9px; min-height: 0; min-width: 0;
        font-size: 10px; color: {colors['overlay2']};
    }}
    .chip:hover {{ background: alpha({colors['text']}, 0.14); color: {colors['text']}; }}
    .chip.on {{
        background: alpha({colors['blue']}, 0.32);
        color: mix({colors['blue']}, {colors['text']}, 0.7);
    }}

    .field, .field text {{
        background: none; background-image: none; box-shadow: none;
        color: {colors['text']}; caret-color: {colors['blue']};
    }}
    .field {{
        border: none; border-bottom: 1px solid alpha({colors['text']}, 0.18);
        border-radius: 0; padding: 3px 0; min-height: 0;
        font-family: {DATA}; font-size: 11px; letter-spacing: 0.5px;
    }}
    .field:focus-within {{ border-bottom-color: {colors['blue']}; }}

    /* The corner sits on bare photograph. A short scrim, the mirror of the
       plate's, keeps it legible over a bright sky. */
    .top-scrim {{
        background: linear-gradient(to bottom,
            alpha({colors['crust']}, 0.70) 0%,
            alpha({colors['crust']}, 0.34) 46%,
            alpha({colors['crust']}, 0.00) 100%);
        padding: 13px 14px 52px 14px;
    }}

    /* Unlike the plate, the corner can end up over white cloud, where the
       plate's mid-grey disappears. Full-strength text plus a shadow, so it
       reads on any photograph. */
    .corner-action {{
        color: {colors['text']};
        text-shadow: 0 1px 4px alpha(black, 0.75);
    }}
    .corner-action:hover {{ color: white; }}

    .backdrop {{ background: alpha({colors['crust']}, 0.62); }}
    .shortcuts {{
        background: {colors['crust']};
        border: 1px solid alpha({colors['text']}, 0.16);
        box-shadow: 0 16px 52px alpha(black, 0.55);
        border-radius: 3px; padding: 26px 32px;
    }}
    .key {{
        font-family: {DATA}; font-size: 11px; font-weight: 600;
        letter-spacing: 1px;
        color: mix({colors['blue']}, {colors['text']}, 0.55);
    }}
    .key-alt {{ color: {colors['overlay0']}; }}

    .guide {{
        background: {colors['crust']};
        border: 1px solid alpha({colors['text']}, 0.16);
        border-radius: 3px;
        box-shadow: 0 16px 52px alpha(black, 0.55);
        padding: 40px 46px 32px 46px;
    }}
    .guide-thesis {{
        font-family: {DISPLAY}; font-size: 33px; font-weight: 300;
        letter-spacing: -0.8px; color: {colors['text']};
    }}
    .guide-sub, .guide-body {{
        font-family: {DISPLAY}; font-size: 13px; color: {colors['overlay2']};
    }}
    .guide-when {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 1.5px;
        color: mix({colors['blue']}, {colors['text']}, 0.55);
    }}
    .guide-foot {{
        font-family: {DISPLAY}; font-size: 12px; color: {colors['overlay0']};
    }}
    .key-action {{ font-family: {DISPLAY}; font-size: 13px;
                   color: {colors['text']}; }}

    /* A whole row is the target -- a source is a name you turn on, not a
       property with a switch beside it. */
    .source-row {{
        background: none; background-image: none;
        border: none; box-shadow: none; border-radius: 2px;
        padding: 10px 9px; min-height: 0;
    }}
    .source-row:hover {{ background: alpha({colors['text']}, 0.06); }}
    /* Hangs off the row it belongs to, sharing its left edge with the
       numbers, so it reads as that source still talking. */
    .key-card {{
        border-left: 1px solid alpha({colors['blue']}, 0.45);
        padding: 4px 0 4px 16px;
    }}

    .source-row:focus {{
        outline: none;
        background: alpha({colors['text']}, 0.06);
        box-shadow: inset 2px 0 0 0 {colors['blue']};
    }}

    .status {{ font-family: {DISPLAY}; font-size: 11px; }}
    .status-ok  {{ color: {colors['overlay0']}; }}
    .status-bad {{ color: mix({colors['maroon']}, {colors['text']}, 0.4); }}

    .key-name {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 0.8px; color: mix({colors['overlay2']}, {colors['text']}, 0.3);
    }}
"""
