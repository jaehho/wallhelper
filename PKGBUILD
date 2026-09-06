# Maintainer: Jaeho Cho <jaewon0907@gmail.com>

pkgname=paperboy-git
_name=paperboy
pkgver=r1
pkgrel=1
pkgdesc="One new photograph a day, and the ones you kept"
arch=('any')
url="https://github.com/jaehho/paperboy"
license=('MIT')
# python-gobject, gtk4 and libadwaita are only needed by `paperboy gui`; the
# fetch that runs from a systemd timer uses nothing but the standard library.
depends=('python' 'python-gobject' 'gtk4' 'libadwaita')
optdepends=('hyprpaper: setting the wallpaper under Hyprland'
            'libnotify: desktop notifications'
            'xdg-desktop-portal: opening source pages and signup pages')
makedepends=('git' 'python-build' 'python-installer' 'python-setuptools'
             'python-wheel')
provides=("$_name")
conflicts=("$_name")
source=("$_name::git+$url.git")
sha256sums=('SKIP')

pkgver() {
    cd "$srcdir/$_name"
    printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

build() {
    cd "$srcdir/$_name"
    python -m build --wheel --no-isolation
}

check() {
    cd "$srcdir/$_name"
    python -m unittest discover -s tests
}

package() {
    cd "$srcdir/$_name"
    python -m installer --destdir="$pkgdir" dist/*.whl
    install -Dm644 data/dev.jaeho.Paperboy.desktop \
        "$pkgdir/usr/share/applications/dev.jaeho.Paperboy.desktop"
    install -Dm644 README.md "$pkgdir/usr/share/doc/$_name/README.md"
}
