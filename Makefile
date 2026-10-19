# wallhelper - one new photograph a day, and the ones you kept.

.PHONY: help test lint run install uninstall package srcinfo clean

PREFIX  ?= $(HOME)/.local
DATADIR ?= $(or $(XDG_DATA_HOME),$(HOME)/.local/share)

help:            ## this list
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) \
	  | sed 's/:.*## /\t/' | expand -t18

test:            ## run the test suite
	python -m unittest discover -s tests -t . -v

lint:            ## ruff
	ruff check wallhelper tests

run:             ## the window, from the source tree
	python -m wallhelper gui

install:         ## live launcher in ~/.local for this user (no sudo)
	# One script: each run is this checkout on the system python, so
	# there is nothing to rebuild. @ROOT@ becomes the checkout that
	# installed it. Exec= gets the absolute launcher path because a
	# desktop launcher may not have $(PREFIX)/bin on its PATH.
	install -d $(PREFIX)/bin
	sed 's|^DEFAULT_ROOT="@ROOT@"|DEFAULT_ROOT="$(CURDIR)"|' \
		scripts/wallhelper-live > $(PREFIX)/bin/wallhelper
	chmod 755 $(PREFIX)/bin/wallhelper
	mkdir -p $(DATADIR)/applications
	sed 's#^Exec=wallhelper#Exec=$(PREFIX)/bin/wallhelper#' \
		packaging/dev.jaeho.Wallhelper.desktop \
		> $(DATADIR)/applications/dev.jaeho.Wallhelper.desktop
	update-desktop-database $(DATADIR)/applications 2>/dev/null || true

uninstall:       ## remove the user install (photos, config and state stay)
	# The entry has no MimeType, so mimeinfo.cache has nothing of ours
	# to drop, and it is shared with every other entry in the directory.
	rm -f $(PREFIX)/bin/wallhelper \
	      $(DATADIR)/applications/dev.jaeho.Wallhelper.desktop

package:         ## build the Arch package without installing
	cd packaging && makepkg -f

srcinfo:         ## regenerate packaging/.SRCINFO after a recipe change
	cd packaging && makepkg --printsrcinfo > .SRCINFO

clean:
	rm -rf build dist src pkg *.egg-info **/__pycache__ *.pkg.tar.zst
