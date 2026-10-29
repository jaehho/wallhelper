"""Palette, faces, and the stylesheet built from them.

The window borrows the desktop's own colours rather than shipping its own, so
it belongs to this machine. Two faces do two jobs: the title is set like a
caption on a print, and everything below it is tracked mono, because every one
of those strings is transcribed data -- a date out of a filename, a token out
of a tab-separated ledger. It reads like an archive card because it is one.
"""

from __future__ import annotations

from pathlib import Path

DISPLAY = '"Adwaita Sans", sans-serif'
DATA = '"JetBrainsMono NF", "JetBrainsMono Nerd Font", monospace'

THUMB_W, THUMB_H = 112, 63       # 16:9, elsewhere row
GRID_W, GRID_H = 220, 124        # 16:9, collection tiles
LONG_TOAST_SECONDS = 7           # a toast with something to read in it

# The desktop's Everforest Dark Medium, as waybar and swaync paint it. The
# accent (the current tile's rule and the on-chip share) is Everforest's
# green, and grey1 is the faint voice. Used as-is when waybar's
# everforest.css is not readable.
EVERFOREST = {
    "bg_dim": "#232a2e", "bg0": "#2d353b", "fg": "#d3c6aa",
    "grey1": "#859289", "grey2": "#9da9a0", "green": "#a7c080",
    "red": "#e67e80",
}
WAYBAR_COLORS = Path.home() / ".config/waybar/everforest.css"


def palette() -> dict[str, str]:
    """The desktop's Everforest, so this window sits at the same hue as
    waybar and swaync instead of inventing its own.

    Read from waybar's `@define-color` lines when they are there, so a
    desktop-wide retint reaches this window too; EVERFOREST when they
    are not. Only the names the stylesheet uses are taken.
    """
    out = dict(EVERFOREST)
    try:
        text = WAYBAR_COLORS.read_text()
    except OSError:
        return out
    found = {}
    for line in text.splitlines():
        if not line.startswith("@define-color "):
            continue
        name, _, value = line.removeprefix("@define-color ").partition(" ")
        value = value.strip().rstrip(";")
        if value.startswith("#"):
            found[name.strip()] = value
    for name in EVERFOREST:
        if name in found:
            out[name] = found[name]
    return out


def tracked(text: str) -> str:
    return text.upper()


def stylesheet(colors: dict[str, str]) -> str:
    """Settings and the shortcut list speak the plate's language: tracked
    mono labels, hairlines, words rather than switches. A stock GNOME
    preferences page in here would read as a different application."""
    return f"""
    window.wallhelper {{ background: {colors['bg_dim']}; }}

    /* A caption band at the foot of the grid, not a hero scrim: the
       photograph is already on the desktop. A few px of padding, not the
       72px top that used to clear a full-bleed image. */
    .plate {{
        background: alpha({colors['bg_dim']}, 0.92);
        padding: 10px 22px 14px 22px;
    }}

    .plate-title {{
        font-family: {DISPLAY};
        font-size: 31px; font-weight: 300; letter-spacing: -0.7px;
        color: {colors['fg']};
    }}
    .plate-place, .plate-row, .plate-action, .plate-empty {{
        font-family: {DATA};
        font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
    }}
    /* Three steps of emphasis, so the plate still has a hierarchy on a photo
       that came with no title and the accession line is all there is. */
    .plate-place {{ color: mix({colors['grey2']}, {colors['fg']}, 0.35); }}
    .plate-row   {{ color: {colors['grey2']}; }}
    .plate-empty {{ color: {colors['grey1']}; letter-spacing: 1.2px; }}

    /* Text controls, not icons: the plate is typographic throughout, and a
       word answers 'what does this do' where a glyph asks it. */
    .plate-action {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 3px 0; min-height: 0; min-width: 0;
        color: {colors['grey2']};
    }}
    .plate-action:hover {{ color: {colors['fg']}; }}
    .plate-action.danger:hover {{
        color: mix({colors['red']}, {colors['fg']}, 0.45);
    }}
    .plate-action.on    {{ color: mix({colors['green']}, {colors['fg']}, 0.55); }}
    .plate-action:disabled {{ color: {colors['grey1']}; }}

    .plate-link {{ color: {colors['grey2']}; }}
    .plate-link:hover {{ color: {colors['fg']}; text-decoration: underline; }}

    .hairline {{ background: alpha({colors['fg']}, 0.10); min-height: 1px; }}

    /* The accent rule says 'on screen now'. One channel, one meaning. */
    .thumb-button, .grid-tile {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 0; min-height: 0; min-width: 0;
        border-bottom: 2px solid transparent;
        opacity: 0.72; transition: opacity 140ms ease;
    }}
    .thumb-button:hover, .grid-tile:hover {{ opacity: 1; }}
    .thumb-button.current, .grid-tile.current {{
        opacity: 1; border-bottom-color: {colors['green']};
    }}
    .thumb {{
        border-radius: 2px;
        box-shadow: inset 0 0 0 1px alpha({colors['fg']}, 0.14);
    }}

    .elsewhere-row {{
        padding: 10px 18px 6px 18px;
    }}
    .elsewhere-label {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 1.5px; color: {colors['grey2']};
    }}

    /* On a tile already in the collection. A word, not a colour. */
    .thumb-mark {{
        font-family: {DATA}; font-size: 9px; font-weight: 600;
        letter-spacing: 1.2px; color: {colors['fg']};
        background: alpha({colors['bg_dim']}, 0.8);
        padding: 1px 5px; margin: 0 0 4px 4px; border-radius: 2px;
    }}

    /* A source with nothing to show, and why: quieter than the label it
       sits under, and not coloured like an alarm. */
    .elsewhere-note {{
        font-family: {DATA}; font-size: 10px; font-weight: 400;
        letter-spacing: 1.2px; color: {colors['grey2']};
    }}

    .close-btn {{
        background: alpha({colors['bg_dim']}, 0.55); color: {colors['fg']};
        border: none; box-shadow: none;
    }}
    .close-btn:hover {{ background: alpha({colors['bg_dim']}, 0.85); }}

    .hero {{ opacity: 0; transition: opacity 520ms ease-out; }}
    .hero.shown {{ opacity: 1; }}

    /* Settings and the shortcut list speak the plate's language: tracked mono
       labels, hairlines, words rather than switches. A stock GNOME
       preferences page in here would read as a different application. */
    .panel {{
        background: {colors['bg_dim']};
        border-left: 1px solid alpha({colors['fg']}, 0.10);
        box-shadow: -18px 0 44px alpha(black, 0.5);
        padding: 22px 26px 26px 26px;
    }}
    .panel-title, .section, .field-label, .chip {{
        font-family: {DATA};
        font-weight: 600; letter-spacing: 1.4px;
    }}
    .panel-title {{ font-size: 11px; color: {colors['fg']}; }}
    .section     {{ font-size: 10px;
                    color: mix({colors['grey2']}, {colors['fg']}, 0.35); }}
    .field-label {{ font-size: 9px;  color: {colors['grey1']}; }}
    .footnote    {{ font-family: {DISPLAY}; font-size: 11px;
                    color: {colors['grey2']}; }}

    .chip {{
        background: alpha({colors['fg']}, 0.07); background-image: none;
        border: none; box-shadow: none; border-radius: 2px;
        padding: 5px 9px; min-height: 0; min-width: 0;
        font-size: 10px; color: {colors['grey2']};
    }}
    .chip:hover {{ background: alpha({colors['fg']}, 0.14); color: {colors['fg']}; }}
    .chip.on {{
        background: alpha({colors['green']}, 0.32);
        color: mix({colors['green']}, {colors['fg']}, 0.7);
    }}

    .field, .field text {{
        background: none; background-image: none; box-shadow: none;
        color: {colors['fg']}; caret-color: {colors['green']};
    }}
    .field {{
        border: none; border-bottom: 1px solid alpha({colors['fg']}, 0.18);
        border-radius: 0; padding: 3px 0; min-height: 0;
        font-family: {DATA}; font-size: 11px; letter-spacing: 0.5px;
    }}
    .field:focus-within {{ border-bottom-color: {colors['green']}; }}

    /* The corner actions rode a hero scrim that is gone; they now sit on
       the plate's action row and use the plate-action style. */

    .backdrop {{ background: alpha({colors['bg_dim']}, 0.62); }}
    .shortcuts {{
        background: {colors['bg_dim']};
        border: 1px solid alpha({colors['fg']}, 0.16);
        box-shadow: 0 16px 52px alpha(black, 0.55);
        border-radius: 3px; padding: 26px 32px;
    }}
    .key {{
        font-family: {DATA}; font-size: 11px; font-weight: 600;
        letter-spacing: 1px;
        color: mix({colors['green']}, {colors['fg']}, 0.55);
    }}
    .key-alt {{ color: {colors['grey1']}; }}

    .guide {{
        background: {colors['bg_dim']};
        border: 1px solid alpha({colors['fg']}, 0.16);
        border-radius: 3px;
        box-shadow: 0 16px 52px alpha(black, 0.55);
        padding: 40px 46px 32px 46px;
    }}
    .guide-thesis {{
        font-family: {DISPLAY}; font-size: 33px; font-weight: 300;
        letter-spacing: -0.8px; color: {colors['fg']};
    }}
    .guide-sub, .guide-body {{
        font-family: {DISPLAY}; font-size: 13px; color: {colors['grey2']};
    }}
    .guide-when {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 1.5px;
        color: mix({colors['green']}, {colors['fg']}, 0.55);
    }}
    .guide-foot {{
        font-family: {DISPLAY}; font-size: 12px; color: {colors['grey1']};
    }}
    .key-action {{ font-family: {DISPLAY}; font-size: 13px;
                   color: {colors['fg']}; }}

    /* A whole row is the target -- a source is a name you turn on, not a
       property with a switch beside it. */
    .source-row {{
        background: none; background-image: none;
        border: none; box-shadow: none; border-radius: 2px;
        padding: 10px 9px; min-height: 0;
    }}
    .source-row:hover {{ background: alpha({colors['fg']}, 0.06); }}
    /* Hangs off the row it belongs to, sharing its left edge with the
       numbers, so it reads as that source still talking. */
    .key-card {{
        border-left: 1px solid alpha({colors['green']}, 0.45);
        padding: 4px 0 4px 16px;
    }}

    .source-row:focus {{
        outline: none;
        background: alpha({colors['fg']}, 0.06);
        box-shadow: inset 2px 0 0 0 {colors['green']};
    }}

    .status {{ font-family: {DISPLAY}; font-size: 11px; }}
    .status-ok  {{ color: {colors['grey2']}; }}
    .status-bad {{ color: mix({colors['red']}, {colors['fg']}, 0.4); }}

    .key-name {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 0.8px; color: mix({colors['grey2']}, {colors['fg']}, 0.3);
    }}
"""
