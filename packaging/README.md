# Packaging

AUR package `wallhelper-git` — builds from `main` and installs `/usr/bin/wallhelper`
plus a `.desktop` launcher entry.

Files:

- `PKGBUILD` — the AUR recipe (VCS `-git` package, no release tags needed).
- `.SRCINFO` — generated metadata the AUR requires (`makepkg --printsrcinfo`).
- `dev.jaeho.Wallhelper.desktop` — launcher entry.

## Test the build locally (no AUR, no GitHub)

```fish
cd /tmp; rm -rf wallhelper-pkgtest; mkdir wallhelper-pkgtest; cd wallhelper-pkgtest
cp ~/projects/wallhelper/packaging/PKGBUILD .
# temporarily build from the local repo instead of GitHub:
sed -i 's#git+https://github.com/jaehho/wallhelper.git#git+file:///home/jaeho/projects/wallhelper#' PKGBUILD
makepkg -f            # build; the package lands in this directory
```

`makepkg` runs the test suite in `check()`, so a broken build fails here rather
than on the next daily fetch.

## Publish to the AUR (first time)

1. Push the source to GitHub so the `source=` URL resolves.
2. Regenerate metadata: `makepkg --printsrcinfo > .SRCINFO`.
3. Clone the (empty) AUR repo and push:

   ```fish
   git clone ssh://aur@aur.archlinux.org/wallhelper-git.git aur-wallhelper
   cp PKGBUILD .SRCINFO aur-wallhelper/     # the .desktop ships in the source
   cd aur-wallhelper; git branch -m master  # the AUR rejects a push to main
   git add -A
   git commit -m "Initial import: wallhelper-git"
   git push
   ```

## Update

`-git` packages track `main` automatically, so there is no version to
bump. Only re-touch the AUR when the recipe itself changes (deps,
install layout), and regenerate `.SRCINFO` when you do.

The author's machine does not install this package. `make install` at
the top of the repo runs the checkout (see the README), so `git pull`
is its update.
