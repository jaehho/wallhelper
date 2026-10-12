# wallhelper - one new photograph a day, and the ones you kept.

.PHONY: help test lint run install uninstall package clean

help:            ## this list
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) \
	  | sed 's/:.*## /\t/' | expand -t18

test:            ## run the test suite
	python -m unittest discover -s tests -t . -v

lint:            ## ruff
	ruff check wallhelper tests

run:             ## the window, from the source tree
	python -m wallhelper gui

install:         ## build and install the Arch package (asks for sudo)
	cd packaging && makepkg -si --noconfirm

uninstall:       ## remove the Arch package
	sudo pacman -Rns wallhelper-git

package:         ## build the Arch package without installing
	cd packaging && makepkg -f

srcinfo:         ## regenerate packaging/.SRCINFO after a recipe change
	cd packaging && makepkg --printsrcinfo > .SRCINFO

clean:
	rm -rf build dist src pkg *.egg-info **/__pycache__ *.pkg.tar.zst
