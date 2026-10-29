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

Or from a checkout, which is how it runs on the author's machine and what
contributors use:

```sh
make install
```

That puts a `wallhelper` launcher and a desktop entry under `~/.local`: no
sudo, nothing in `/usr`, no package. The launcher runs the checkout on the
system Python, so `git pull` is the update. On the author's machine the
fetch timer (in the dotfiles repo) calls this launcher.

The window needs `python-gobject`, `gtk4` and `libadwaita` from the
distribution; the other commands need only Python 3.11. `make uninstall`
removes the launcher and the entry and leaves the photos, config and state
alone.

See `packaging/` for the recipe and the AUR workflow.

## Use

```
wallhelper fetch [--wait]   pull the day's photo (what the systemd timer runs)
wallhelper set <image>      make a photo in the collection the wallpaper
wallhelper delete           send what's on screen to the Trash
wallhelper info             what's on screen and where it came from
wallhelper gui              the same thing with pictures
```

In the window: click a tile to set it as wallpaper, `D` deletes (UNDO on the message, or `U`, brings it back out of the Trash for a few seconds), `E` expands Elsewhere, `O` opens the source page, `F` fetches now, `,` opens settings, `?` lists every shortcut, `G` shows the guide. `Ctrl+W` or `Ctrl+Q` closes the window and `Ctrl+?` lists the shortcuts, from the settings fields too; the letters are keys on their own, so `Ctrl+D` deletes nothing.

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
| `min_aspect` | skip anything below this width ÷ height; `1.3` drops squares and portraits |
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
Unsplash takes `count=12` so Elsewhere has a grid; it needs a free access key,
and the settings panel has a box for it. Switch sources on in the settings
panel, which also has a **CHECK** button that asks every source what it has
today without downloading it, and an **EDIT** button that opens `config.json`
in your text editor. Under MORNING it says when the morning fetch last ran and
what it came to (`Last fetch 2026·10·18: bing`, or `failed: bing —
Unauthorized`), so a source that broke while nobody was looking says so the
next time you open it. `F` in the window runs the same fetch and toasts the
same answer.

A source needing an API key declares where to get one, and the panel then offers
the signup link and a box to paste into; the key goes wherever the placeholder
appears, whether that is a query argument or a header.

Elsewhere asks every `gallery` source at once and paints each as it answers,
waiting no more than eight seconds on any. A source that is down, slow, or
still holding its key placeholder gets a muted line under the row in place of
silence (`UNSPLASH — needs a key`, `APOD — timed out`, `DENIED —
Unauthorized`), and a placeholder is never sent to the API.

A tile the collection already holds says SAVED, and choosing it sets that
photograph instead of fetching it again.

Your changes live in `~/.config/wallhelper/config.json`, and only your changes —
the shipped sources stay shipped, so they keep improving.

## How it fits together

- The collection is one folder. `.current` in it is a symlink, and
  hyprpaper.conf points at that, so the wallpaper survives a reboot. Talking
  to hyprpaper alone does not.
- `.credits` is tab-separated filename/title/byline/url. A dotfile, so an image
  browser pointed at the folder skips it.
- `~/.local/state/wallhelper/last-fetch.json` is what the last morning fetch
  came to: when, which source, and its reason if it failed. The settings panel
  reads it. It is rewritten each run and is not a log; the journal is the log.
  A second run the same day asks nobody when that note says today's photograph
  is still in the collection, and a photograph the source serves a second time
  (Bing before it rolls over) counts as fetched.
- Everything fetched is kept. Deleting is the only removal, and it goes through
  the desktop wastebasket. A deleted photograph keeps its `.credits` line and
  thumbnails while the Trash holds it, so restoring it brings its caption
  back; both are pruned, when the window opens, once it is in neither place.
  If the Trash refuses the file, `delete` says it was deleted for good.

## Develop

```sh
make test     # python -m unittest discover -s tests -t .
make lint     # ruff
make run      # the window, straight from the source tree
make install  # the launcher and desktop entry in ~/.local, no sudo
```

`PRODUCT.md` is what this is and what it must never become. GitHub issues hold
what is open, plus what was done and why (label `decision`) and known traps
(label `gotcha`). The tests delete files, so run them through `make test` — anything
else and a guard stops them before they touch a real collection.

Modules: `paths` (every path, importing nothing), `config` (the shipped sources
and your deltas), `net`, `desktop` (notifications, hyprctl, hyprpaper),
`library` (the collection on disk), `sources` (the template engine),
`morning` (the daily fetch and the note it leaves), `cli`, and
`gui/` (`style`, `thumbs`, `grid`, `elsewhere`, `plate`, `sheets`, `settings`,
`window`, `app`). Importing `wallhelper.gui` is what pulls in GTK, which is why
the CLI does it inside the `gui` subcommand and nowhere else.
