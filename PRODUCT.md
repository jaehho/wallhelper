# Product

## Register

product

## Users

One person: the author — technical, on Arch + Hyprland, comfortable in a
terminal. Not a team, not a customer.

Context of use is unusual and shapes everything below: **almost all of the time
nobody is using this at all.** A systemd timer fetches a photograph while the
machine is asleep or the user is elsewhere, and the result is seen as a
wallpaper, glanced at between windows, for a day. The window is opened rarely —
when you want a different wallpaper from another source, or to tidy the
collection. Sessions are seconds long, weeks apart.

So the tool cannot rely on being remembered. Every time the window opens it has
to re-explain its own state, and the state has to be small enough to re-explain
in one glance.

## Product Purpose

wallhelper fetches Bing's picture of the day, sets it as the wallpaper, and
keeps it. The window is a gallery of everything kept, plus today's pictures
from other sources when you want a change by hand.

It succeeds `hypr-wallpaper`, which rotated a folder on a timer. That tool's
failure was that nothing ever meant anything: the wallpaper changed on its own
schedule, the same images came back around, the folder grew without limit, and
when a source broke the only symptom was that the picture stopped changing —
which looked exactly like the picture not having changed yet.

Success looks like: a photograph you have not seen before is on the screen most
mornings; every one of them is still there months later unless you delete it;
deleting is deliberate and recoverable; and when something breaks, the tool
says which source and why, in a sentence.

## Brand Personality

A wall label in a gallery. Quiet, exact, and secondary to the picture.

The voice is the voice of a museum caption: it states what is known and stops.
It never fills a gap with a placeholder — a photograph nobody titled has no
title line, not a line reading "Untitled". It never editorialises about the
photograph, and it never congratulates you for keeping one.

Emotional goal: mild, recurring pleasure. Not delight, not achievement. The
feeling of a good print you walk past every day and still notice.

## Anti-references

- **Wallpaper managers (waypaper, variety, Wallpaper Engine):** a settings
  dialog of checkboxes and the premise that choosing wallpapers is the
  activity. wallhelper is not a shop. The collection is what you already have;
  Elsewhere is a short list of today's other offerings, not an infinite feed.
- **Consumer photo app / social feed:** no hearts, no counts, no streaks, no
  infinite scroll, and above all no "like". Saving is a filing decision, not a
  sentiment you broadcast.
- **A GNOME preferences page:** a header bar, a sidebar of categories, and a
  wall of switch rows. Settings here is one question deep and lives in the
  same typographic language as the plate. If it ever needs a category, the
  answer is that it has grown something it shouldn't have.

## Design Principles

1. **Open on the collection.** The window is a grid of what you saved. The
   wallpaper is already on the desktop; this window is for choosing another
   one or tidying up. Elsewhere sits above the grid as a short row of today's
   other sources.

2. **Everything fetched is kept.** The morning photograph lands in the
   collection and stays. The only removal is the one you ask for. There is no
   keep/unkeep, no countdown, and no automatic sweep.

3. **The window answers questions; the file holds settings.** The window's job
   is the question you actually opened it to ask — which sources am I using,
   and are they working. Everything else about a source is JSON, because a file
   is better at being a file than a form is: it can hold a parameter this
   version has never heard of. Twice this panel has been the other thing — a
   raw JSON editor, and a wall of fields — and both were the same mistake, one
   putting the file's vocabulary in the window and the other putting the
   window's vocabulary in the file.

4. **Words, not icons.** DELETE, OPEN SOURCE, MORE, CHECK. A word answers
   "what does this do" where a glyph asks it, and this is a tool used seconds
   at a time, weeks apart, by someone who will not have memorised anything.
   The type is the interface: a caption face for the title, tracked mono for
   everything transcribed from a file or an API, because it reads like an
   archive card and it is one.

5. **Never state a fact you don't have.** No "Untitled", no "Unknown
   photographer", no invented date. A line with nothing to say is not shown and
   the plate shrinks to suit. The corollary: when something fails, say which
   source and what it said — `unsplash — Unauthorized`, not "couldn't fetch".

6. **Silence is the normal state.** This runs unattended every day. It must not
   notify on a flaky-wifi failure, because a notification you see weekly is one
   you learn to dismiss unread. It escalates only when there is nothing left to
   show, and otherwise fails loudly where a failure belongs — a non-zero exit
   the timer records, and a source that says so in the panel next time you look.

## Accessibility & Inclusion

A personal single-user tool, so no external WCAG mandate, but the baseline
holds and some of it is load-bearing here:

- **Contrast over an arbitrary photograph** is the hard problem, since plate
  text can sit over a thumbnail. The plate is a scrim reaching 0.97 opacity
  under the text rather than a translucent tint.
- **Keyboard-complete.** Every action has a key, `?` lists them, and opening
  settings moves focus into the panel rather than leaving it out on the grid.
  Nothing requires the pointer.
- **State is never colour alone.** The plate says what is selected. The current
  tile also carries an accent rule, which is a second channel rather than the
  only one.
- Dark by default, because it is over a photograph and at the same hue as the
  rest of the desktop. There is no light variant and no reason for one.
