# wallhelper

One new photograph a day, and the ones you kept.

Every morning it fetches a photograph — Bing's picture of the day, a Wallhaven
top wallpaper, NASA's APOD, whatever you switch on — sets it as the wallpaper,
and remembers who took it. Photographs you don't keep are deleted when the next
one arrives. There is no countdown and nothing to tidy up later.

Built for Hyprland and hyprpaper. The window is GTK4 and libadwaita.

## Install

```sh
paru -S wallhelper-git
```

Or from a checkout: `make install`. See `packaging/` for the recipe and the
AUR workflow.

## Use

```
wallhelper fetch [--next]    pull the day's photo (what the systemd timer runs)
wallhelper set <image>       make an image the wallpaper
wallhelper keep [--undo]     keep what's on screen
wallhelper delete            remove what's on screen for good
wallhelper info              what's on screen and where it came from
wallhelper gui               the same thing with pictures
```

In the window: `H`/`L` walk the strip, `K` keeps the photograph (and deletes it
once kept), `N` fetches a different one, `O` opens the source page, `,` opens
settings, `?` lists every shortcut, `G` shows the guide.

## Sources

A source is data, not code:

```json
"peapix": {
  "url":    "https://peapix.com/bing/feed?country=jp",
  "list":   ".",
  "image":  "{fullUrl}",
  "title":  "{title}",
  "credit": "{copyright}",
  "link":   "{pageUrl}"
}
```

Fetch one JSON document, optionally pick a random entry from an array inside
it, fill the templates from that entry. `{a.path}` reads a value out of the
reply, `{date:%Y%m%d}` comes from the clock, `"."` as a list means the reply is
itself an array, and a string with no braces is used as-is.

| field | |
|---|---|
| `url` | the JSON to fetch |
| `list` | path to an array; one entry is picked at random |
| `image` | the photograph's URL — the only required field |
| `title` | shown large on the label |
| `credit` | photographer; `place (© name)` splits across both label lines |
| `link` | what the source button opens |
| `id` | used in the filename; `\|name\|stem` trims a path or an extension |
| `date` | the photograph's own date, if it has one |
| `require` | `{"media_type": "image"}` skips entries that don't match |
| `replace` | `["pattern", "with"]` — a regex over the image URL |
| `headers` | extra request headers |
| `min_width` | skip anything narrower than this |
| `key` | `{"get": url, "note": text, "into": placeholder}` — see below |

Shipped: `bing`, `wallhaven`, `apod`, `wikipedia`, `unsplash`. Switch them on in
the settings panel, which also has a **CHECK** button that asks every source
what it has today without downloading it — the fastest way to find out whether
a source you wrote works.

A source needing an API key declares where to get one, and the panel then offers
the signup link and a box to paste into; the key goes wherever the placeholder
appears, whether that is a query argument or a header.

Your changes live in `~/.config/wallhelper/config.json`, and only your changes —
the shipped sources stay shipped, so they keep improving.

## How it fits together

- `.current` in the collection is a symlink, and hyprpaper.conf points at it, so
  the wallpaper survives a reboot. Talking to hyprpaper alone does not.
- `kept/` holds hardlinks, not copies. Keeping a photograph costs no disk and is
  the only thing that saves it from the next sweep.
- `.credits` is tab-separated filename/title/byline/url. A dotfile, so an image
  browser pointed at the folder skips it.

## Develop

```sh
make test     # python -m unittest discover -s tests -t .
make lint     # ruff
make run      # the window, straight from the source tree
make install  # build and install the Arch package
```

`PRODUCT.md` is what this is and what it must never become; `DESIGN_LOG.md` is what
was done and why, and GitHub issues hold what is open. The tests delete files, so run them through `make test` — anything
else and a guard stops them before they touch a real collection.

Modules: `paths` (every path, importing nothing), `config` (the shipped sources
and your deltas), `net`, `desktop` (notifications, hyprctl, hyprpaper),
`library` (the collection on disk), `sources` (the template engine), `cli`, and
`gui/` (`style`, `thumbs`, `sheets`, `settings`, `window`, `app`). Importing
`wallhelper.gui` is what pulls in GTK, which is why the CLI does it inside the
`gui` subcommand and nowhere else.
