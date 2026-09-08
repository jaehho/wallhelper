# Packaging

AUR package `paperboy-git` — builds from `main` and installs `/usr/bin/paperboy`
plus a `.desktop` launcher entry.

Files:

- `PKGBUILD` — the AUR recipe (VCS `-git` package, no release tags needed).
- `.SRCINFO` — generated metadata the AUR requires (`makepkg --printsrcinfo`).
- `dev.jaeho.Paperboy.desktop` — launcher entry.

## Test the build locally (no AUR, no GitHub)

```fish
cd /tmp; rm -rf paperboy-pkgtest; mkdir paperboy-pkgtest; cd paperboy-pkgtest
cp ~/projects/paperboy/packaging/PKGBUILD .
# temporarily build from the local repo instead of GitHub:
sed -i 's#git+https://github.com/jaehho/paperboy.git#git+file:///home/jaeho/projects/paperboy#' PKGBUILD
makepkg -f            # build; add -si to also install
```

`makepkg` runs the test suite in `check()`, so a broken build fails here rather
than on the next daily fetch.

## Publish to the AUR (first time)

1. Push the source to GitHub so the `source=` URL resolves.
2. Regenerate metadata: `makepkg --printsrcinfo > .SRCINFO`.
3. Clone the (empty) AUR repo and push:

   ```fish
   git clone ssh://aur@aur.archlinux.org/paperboy-git.git aur-paperboy
   cp PKGBUILD .SRCINFO aur-paperboy/     # the .desktop ships in the source
   cd aur-paperboy; git branch -m master  # the AUR rejects a push to main
   git add -A
   git commit -m "Initial import: paperboy-git"
   git push
   ```

## Update

`-git` packages track `main` automatically, and `/etc/paru.conf` here has
`Devel` on, so `paru -Syu` — which `make sync` runs — rebuilds whenever this
repo gets new commits. Only re-touch the AUR when the recipe itself changes
(deps, install layout), and regenerate `.SRCINFO` when you do.

`make status` in dotfiles reports whether the installed package matches this
repo's HEAD.
