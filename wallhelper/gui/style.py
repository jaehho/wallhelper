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

GRID_W, GRID_H = 220, 124        # 16:9, the strip's tiles (and the cache's)
TILE_GAP = 12                    # between two tiles
STRIP_PAD = 18                   # the strip's ends, before the first tile
STRIP_W, STRIP_H = 1600, 226     # until hyprland.lua docks it full width
LONG_TOAST_SECONDS = 7           # a toast with something to read in it

# The desktop's Everforest Dark Medium, as waybar and swaync paint it. The
# accent (the rule under the tile on the wall) is Everforest's green, and
# grey1 is the faint voice. Used as-is when waybar's
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
    """A mat under the photographs: solid, so the caption reads over any
    wallpaper, and quiet, so the wallpaper above it is what you look at."""
    return f"""
    window.wallhelper {{ background: {colors['bg_dim']}; }}

    /* The caption: a wall label over the strip. */
    .plate {{ padding: 14px 24px 0 24px; }}
    .plate-title {{
        font-family: {DISPLAY};
        font-size: 21px; font-weight: 300; letter-spacing: -0.3px;
        color: {colors['fg']};
    }}
    .plate-place, .plate-row, .plate-action {{
        font-family: {DATA};
        font-size: 10px; font-weight: 600; letter-spacing: 1.5px;
    }}
    /* Three steps of emphasis, so the caption still has a hierarchy for a
       photograph that came with no title. */
    .plate-place {{ color: mix({colors['grey2']}, {colors['fg']}, 0.35); }}
    .plate-row   {{ color: {colors['grey2']}; }}

    /* Words, not icons: a word answers 'what does this do' where a glyph
       asks it. */
    .plate-action {{
        background: none; background-image: none; border: none;
        box-shadow: none; padding: 3px 0; min-height: 0; min-width: 0;
        color: {colors['grey2']};
    }}
    .plate-action:hover {{ color: {colors['fg']}; }}
    .plate-action.danger:hover {{
        color: mix({colors['red']}, {colors['fg']}, 0.45);
    }}
    .plate-action:disabled {{ color: {colors['grey1']}; }}
    .plate-link:hover {{ text-decoration: underline; }}

    /* The strip. The green rule says 'on the wall now', and the wall
       follows the selection, so it sits under the selected tile. */
    .strip-scroll, listview.strip {{ background: none; }}
    listview.strip {{ padding: 12px {STRIP_PAD}px 16px {STRIP_PAD}px; }}
    listview.strip > row {{
        background: none; padding: 0 0 5px 0; margin: 0 {TILE_GAP // 2}px;
        border-radius: 0; outline-color: transparent;
        border-bottom: 2px solid transparent;
        opacity: 0.62; transition: opacity 140ms ease;
    }}
    listview.strip > row:hover {{ opacity: 0.9; }}
    listview.strip > row:selected {{
        background: none; opacity: 1;
        border-bottom-color: {colors['green']};
    }}
    .thumb {{
        border-radius: 2px;
        box-shadow: inset 0 0 0 1px alpha({colors['fg']}, 0.14);
    }}
    .tile.said {{
        background: alpha({colors['fg']}, 0.05); border-radius: 2px;
        box-shadow: inset 0 0 0 1px alpha({colors['fg']}, 0.14);
    }}
    .tile-mark {{
        font-family: {DATA}; font-size: 9px; font-weight: 600;
        letter-spacing: 1.2px; color: {colors['fg']};
        background: alpha({colors['bg_dim']}, 0.82);
        padding: 1px 5px; margin: 0 0 6px 6px; border-radius: 2px;
    }}
    .tile-note {{
        font-family: {DATA}; font-size: 10px; font-weight: 600;
        letter-spacing: 1.2px;
        color: mix({colors['grey2']}, {colors['fg']}, 0.3);
    }}

    /* The key list, a band over the strip. */
    .backdrop {{ background: alpha({colors['bg_dim']}, 0.96); }}
    .key {{
        font-family: {DATA}; font-size: 11px; font-weight: 600;
        letter-spacing: 1px;
        color: mix({colors['green']}, {colors['fg']}, 0.55);
    }}
    .key-alt {{ color: {colors['grey1']}; }}
    .key-action {{ font-family: {DISPLAY}; font-size: 13px;
                   color: {colors['fg']}; }}
"""
