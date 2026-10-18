# wallhelper

Bing in the morning, and the ones you saved.

Every morning it fetches Bing's picture of the day, sets it as the wallpaper,
and keeps it. The window is a gallery of that collection. When you want a
change by hand, Elsewhere shows today's pictures from the other sources —
choosing one saves it and makes it the wallpaper. Photographs you delete go to
Trash. There is no countdown and nothing to tidy up later.

Built for Hyprland and hyprpaper. The window is GTK4 and libadwaita.

## Install

```sh
paru -S wallhelper-git
```

Or from a checkout: `make install`. See `packaging/` for the recipe and the
AUR workflow.

## Use

```
wallhelper fetch [--wait]   pull the day's photo (what the systemd timer runs)
wallhelper set <image>      make a photo in the collection the wallpaper
wallhelper delete           send what's on screen to the Trash
wallhelper info             what's on screen and where it came from
wallhelper gui              the same thing with pictures
```

In the window: click a tile to set it as wallpaper, `D` deletes,
`E` expands Elsewhere, `O` opens the source page, `F` fetches now, `,` opens
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

Fetch one JSON document, optionally pick entries from an array inside it, fill
the templates from each. `{a.path}` reads a value out of the reply,
`{date:%Y%m%d}` comes from the clock, `"."` as a list means the reply is itself
an array, and a string with no braces is used as-is.

| field | |
|---|---|
| `url` | the JSON to fetch |
| `list` | path to an array; every entry is a gallery candidate |
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

Filters in a template: `|name` (after the last `/` or `:`), `|stem` (without
the extension), `|text` (strip HTML, for credits that come wrapped in tags).

Two name lists decide what a source is for:

```json
"autofetch": ["bing"],
"gallery":   ["apod", "wikipedia", "unsplash"]
```

`autofetch` is the morning timer. `gallery` is the Elsewhere row. Shipped:
`bing` (morning), `apod`, `wikipedia`, `unsplash`. APOD reads NASA's WordPress
`apod-basic` route (the old `api.nasa.gov/planetary` image fields are gone).
Unsplash takes `count=12` so Elsewhere has a grid; it needs a free access key
pasted into its url. Switch sources on in the settings panel, which also has a
**CHECK** button that asks every source what it has today without downloading
it, and an **EDIT** button that opens `config.json` in your text editor.

A source needing an API key declares where to get one, and the panel then offers
the signup link and a box to paste into; the key goes wherever the placeholder
appears, whether that is a query argument or a header.

Your changes live in `~/.config/wallhelper/config.json`, and only your changes —
the shipped sources stay shipped, so they keep improving.

## How it fits together

- The collection is one folder. `.current` in it is a symlink, and
  hyprpaper.conf points at that, so the wallpaper survives a reboot. Talking
  to hyprpaper alone does not.
- `.credits` is tab-separated filename/title/byline/url. A dotfile, so an image
  browser pointed at the folder skips it.
- Everything fetched is kept. Deleting is the only removal, and it goes through
  the desktop wastebasket. A deleted photograph keeps its `.credits` line and
  thumbnails while the Trash holds it, so restoring it brings its caption
  back; both are pruned once it is in neither place. If the Trash refuses the
  file, `delete` says it was deleted for good.

## Develop

```sh
make test     # python -m unittest discover -s tests -t .
make lint     # ruff
make run      # the window, straight from the source tree
make install  # build and install the Arch package
```

`PRODUCT.md` is what this is and what it must never become. GitHub issues hold
what is open, plus what was done and why (label `decision`) and known traps
(label `gotcha`). The tests delete files, so run them through `make test` — anything
else and a guard stops them before they touch a real collection.

Modules: `paths` (every path, importing nothing), `config` (the shipped sources
and your deltas), `net`, `desktop` (notifications, hyprctl, hyprpaper),
`library` (the collection on disk), `sources` (the template engine), `cli`, and
`gui/` (`style`, `thumbs`, `grid`, `elsewhere`, `plate`, `sheets`, `settings`,
`window`, `app`). Importing `wallhelper.gui` is what pulls in GTK, which is why
the CLI does it inside the `gui` subcommand and nowhere else.
