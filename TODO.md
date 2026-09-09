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

Outside this repo, done 2026-09-09:

- [x] GitHub repo renamed to `jaehho/wallhelper`; remote repointed, pushed.
      The old URL redirects, so a stale checkout's `source=` still resolves.
- [x] `wallhelper-git` pushed to the AUR as a new pkgbase, after a clean
      `makepkg -f` — 41 tests in `check()`, `/usr/bin/wallhelper` and
      `dev.jaeho.Wallhelper.desktop` in the tarball, no trace of the old name.
- [x] dotfiles: units renamed to `wallhelper-fetch.*`, `97-apps.txt`,
      `sync.sh`, `status.sh`, `hypr-settings-menu`, and the hyprland window
      rule (it matched on class `dev\.jaeho\.Paperboy`, which would have
      silently stopped floating the window). Left uncommitted — that repo had
      unrelated work in the tree.
- [x] `~/.config/waypaper/config.ini` `post_command`, which is not stowed:
      waypaper rewrites the file on exit, so it is edited in place or not at
      all.

Still open:

- [ ] Run `/tmp/wallhelper-swap.sh` — installs `wallhelper-git`, moves the
      three state dirs, removes `paperboy-git`, relinks the stowed units and
      `enable --now`s the timer, then `paru --gendb`. Needs sudo, so it is a
      script rather than something run for you. Until it runs, the stowed unit
      symlinks under `~/.config/systemd/user` dangle: their targets were
      renamed out from under them.
- [ ] File the deletion request for `paperboy-git`. The AUR's SSH interface has
      no command for it (`adopt`, `disown`, `flag`, `vote`, `set-keywords`, and
      nothing else) — it is the web form at
      `aur.archlinux.org/pkgbase/paperboy-git/request/`, so it wants a login.
- [ ] Reply to m040601 on the `paperboy-git` page saying where it went.

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
