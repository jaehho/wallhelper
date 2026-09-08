# TODO

## Now

- [x] `github.com/jaehho/paperboy` — public, pushed.
- [x] `paperboy-git` on the AUR. `packages/arch/97-apps.txt` lists it, so
      `make sync` installs it on a fresh machine and `paru -Syu` (Devel is on)
      rebuilds it whenever this repo moves. Nothing else to do to stay current.
- [ ] Run `/tmp/install-paperboy.sh` once, to replace the locally-built package
      with the AUR one. Until then paru has no devel record for it and upgrades
      will skip it; `make status` says `stale` while that is true.
- [ ] Retire the ancestors once this has run for a few days: archive
      `github.com/jaehho/hypr-tools` and `hypr-wallpaper`, orphan the
      `hypr-wallpaper-git` AUR package. Not authorised yet.

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

- The units were switched from `wallpaper-fetch` to `paperboy-fetch` by hand,
  not by `make sync`. `systemctl --user enable` alone leaves a timer *enabled
  but dead* until the next login; it wants `enable --now`, or `start` after
  the fact. `make status` does check `is-active`, so it would have caught this
  — nobody ran it.
- `make status` now also reports whether the installed `paperboy-git` matches
  this repo's HEAD. It reports; it does not rebuild.

## Known and deliberate

- `like` stays as a hidden alias for `keep`. Costs one line, saves muscle
  memory.
- No logging beyond stderr and the journal. reel writes rotating JSONL because
  a GUI misbehaving mid-session needs a trace; a once-a-day timer already has
  one, in `journalctl --user -u paperboy-fetch`.
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
