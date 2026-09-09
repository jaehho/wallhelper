# TODO

## Now

- [x] Renamed `paperboy` -> `wallhelper` 2026-09-09. The AUR's `paperboy` (and
      `paperboy-bin`) have been 2mol/pboy since 2019; `paperboy-git` read as
      the VCS build of it, and the recipe's `provides`/`conflicts=('paperboy')`
      actively claimed to satisfy it. Both lines are gone with the name.
      Everything in-repo is renamed: package dir, entry point, app-id
      `dev.jaeho.Wallhelper`, `WALLHELPER_DIR`/`WALLHELPER_CONFIG`, the XDG
      dirs. `~/Pictures/wallpapers` is unchanged — `DIR` was never name-derived,
      so the collection survived untouched.

Outstanding, all outside this repo:

- [ ] Rename the GitHub repo to `jaehho/wallhelper`. GitHub redirects the old
      URL, so the `source=` in a stale checkout keeps resolving; that is a
      grace period, not a reason to skip it.
- [ ] Push `wallhelper-git` to the AUR as a new pkgbase, then file a deletion
      request for `paperboy-git`. Zero votes, so deletion rather than a merge —
      a merge would carry the misleading name into the new package's history.
- [ ] Reply to m040601 on the `paperboy-git` page saying where it went.
- [ ] dotfiles: `packages/arch/97-apps.txt` still lists `paperboy-git`, and the
      units are still `paperboy-fetch.service`/`.timer`. Renaming the units
      wants `disable --now` on the old pair before `enable --now` on the new,
      or the old timer keeps firing a binary that no longer exists.
- [ ] Local state: `/tmp/wallhelper-migrate.sh` moves `~/.config/paperboy`,
      `~/.cache/paperboy` and `~/.local/state/paperboy` to their new homes.
      Run it before the first `wallhelper fetch`, or the settings panel opens
      on defaults and the guide replays.
- [ ] `paru --gendb` after the reinstall, so the devel record points at the new
      pkgbase instead of the deleted one.

## Next — the window

- [ ] `window.py` is 639 lines and still the largest module. The plate and the
      strip are two independent widgets sharing only `self.current`; splitting
      them the way `settings.py` was split would leave a window that mostly
      wires things together.
- [ ] No test touches the window. `style` is covered now that it imports no
      GTK; `thumbs.dimensions` is pure formatting over `library.measure` and
      could be next without needing a display.
- [ ] The plate's action button changes from KEEP to DELETE in place. Trash
      makes that recoverable, but a double-tap still deletes what you just
      kept. Watch whether it ever actually happens before adding anything.

## Sources

- [ ] `fetch_source` has no test — it is the one place where a network reply
      shapes a filename, and every bug in it so far (APOD's dashed date,
      Wikipedia's `File:` prefix, a non-Latin title slugifying to nothing) was
      found by running it against the live API. Recorded JSON fixtures for the
      five shipped sources would catch the next one.
- [ ] `probe_source` and `fetch_source` resolve a source twice, by nearly the
      same steps. One of them should be written in terms of the other.
- [ ] Candidates nobody has asked for yet: NASA Earth Observatory, Met Museum
      Open Access, Flickr Commons. Each is a config object, not code.

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

## Done

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
