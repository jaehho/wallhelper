# wallhelper devlog

What was done and why, and the choices that are deliberate. Open work lives in GitHub issues.

## Rename: paperboy → wallhelper (2026-09-09)

- Renamed `paperboy` -> `wallhelper` 2026-09-09. The AUR's `paperboy` (and
      `paperboy-bin`) have been 2mol/pboy since 2019; `paperboy-git` read as
      the VCS build of it, and the recipe's `provides`/`conflicts=('paperboy')`
      actively claimed to satisfy it. Both lines are gone with the name.
      Everything in-repo is renamed: package dir, entry point, app-id
      `dev.jaeho.Wallhelper`, `WALLHELPER_DIR`/`WALLHELPER_CONFIG`, the XDG
      dirs. `~/Pictures/wallpapers` is unchanged — `DIR` was never name-derived,
      so the collection survived untouched.

Outside this repo, done 2026-09-09:

- GitHub repo renamed to `jaehho/wallhelper`; remote repointed, pushed.
      The old URL redirects, so a stale checkout's `source=` still resolves.
- `wallhelper-git` pushed to the AUR as a new pkgbase, after a clean
      `makepkg -f` — 41 tests in `check()`, `/usr/bin/wallhelper` and
      `dev.jaeho.Wallhelper.desktop` in the tarball, no trace of the old name.
- dotfiles: units renamed to `wallhelper-fetch.*`, `97-apps.txt`,
      `sync.sh`, `status.sh`, `hypr-settings-menu`, and the hyprland window
      rule (it matched on class `dev\.jaeho\.Paperboy`, which would have
      silently stopped floating the window). Left uncommitted — that repo had
      unrelated work in the tree.
- `~/.config/waypaper/config.ini` `post_command`, which is not stowed:
      waypaper rewrites the file on exit, so it is edited in place or not at
      all.

The swap script ran afterwards: `wallhelper-git` installed, the timer active, `paperboy-git` gone from the AUR.

## Watch for

- The units have been renamed by hand twice now (`wallpaper-fetch` ->
  `paperboy-fetch`, and `-> wallhelper-fetch` still pending), never by
  `make sync`. `systemctl --user enable` alone leaves a timer *enabled but
  dead* until the next login; it wants `enable --now`, or `start` after the
  fact. `make status` does check `is-active`, so it would have caught this —
  nobody ran it. Third time: `disable --now` the old pair first.
- `make status` now also reports whether the installed `wallhelper-git` matches
  this repo's HEAD. It reports; it does not rebuild.

## Known and deliberate

- `like` stays as a hidden alias for `keep`. Costs one line, saves muscle
  memory.
- No logging beyond stderr and the journal. reel writes rotating JSONL because
  a GUI misbehaving mid-session needs a trace; a once-a-day timer already has
  one, in `journalctl --user -u wallhelper-fetch`.
- The config file only ever stores your deltas. A full copy would pin every
  shipped source at whatever it looked like the day you first touched a switch,
  which is exactly the bug that shipped two wrong source links.

## Extraction from dotfiles

- **Extraction.** 2,400-line single file in dotfiles → this package. Core split
  into `paths` / `config` / `net` / `desktop` / `library` / `sources` / `cli`,
  the window into `gui/{style,thumbs,sheets,settings,window,app}`. 41 tests,
  ruff clean, PKGBUILD builds and runs the suite in `check()`.
- **Sources became data.** Five Python fetchers → five JSON objects and one
  template engine. Adding a source is a config edit; `CHECK` in the panel asks
  every source what it has today without downloading it.
- **Keys.** A source declares where to get one; the panel offers the link and a
  box, and puts the key wherever the placeholder appeared.
- **One action.** KEEP and DELETE were never both meaningful for the same
  photograph. See PRODUCT.md principle 2.
- **`liked/` → `kept/`**, migrated in code on first run.
- **Tests refuse to run against a real collection** after they ate part of one.
