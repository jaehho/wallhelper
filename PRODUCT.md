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
when you want a different wallpaper, or to tidy the collection. Sessions are
seconds long, weeks apart.

So the tool cannot rely on being remembered. Every time the window opens it has
to re-explain its own state, and the state has to be small enough to re-explain
in one glance.

## Product Purpose

wallhelper fetches Bing's picture of the day, sets it as the wallpaper, and keeps it. Opening it shows the desktop with a strip of everything kept along its bottom edge, and the desktop is the preview.

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
  activity. wallhelper is not a shop. The collection is what you already have, and there is no feed of other offerings.
- **Consumer photo app / social feed:** no hearts, no counts, no streaks, no
  infinite scroll, and above all no "like". Saving is a filing decision, not a
  sentiment you broadcast.
- **A preferences page of any kind:** a header bar, a sidebar of categories, a wall of switch rows. wallhelper has no settings: the defaults are the product, and the rare change (a source of your own, no morning fetch) is a file or a timer, in the README. The settings panel was a JSON editor once and a wall of fields once; the third answer was to need none (#24).

## Design Principles

1. **Open on the desktop.** The window is a strip along the bottom edge of an empty workspace, and the wallpaper above it is the preview: moving the selection sets the wall, and closing keeps it. There is no SET, because what you see is what you get.

2. **Everything fetched is kept.** The morning photograph lands in the
   collection and stays. The only removal is the one you ask for. There is no
   keep/unkeep, no countdown, and no automatic sweep.

3. **Nothing to configure, nothing to learn.** There is no settings panel and no guide, because the strip says what they did where you already look: the morning's place says whether today's photograph came and why not, TODAY and BEFORE mark the two tiles that matter, and every delete offers Undo. A source of your own is JSON, because a file is better at being a file than a form is: it can hold a parameter this version has never heard of.

4. **Words, not icons.** DELETE, DONE, and the source's name as its link. A word answers
   "what does this do" where a glyph asks it, and this is a tool used seconds
   at a time, weeks apart, by someone who will not have memorised anything.
   The type is the interface: a caption face for the title, tracked mono for
   everything transcribed from a file or an API, because it reads like an
   archive card and it is one.

5. **Never state a fact you don't have.** No "Untitled", no "Unknown
   photographer", no invented date. A line with nothing to say is not shown and
   the caption shrinks to suit. The corollary: when something fails, say which
   source and what it said — `bing — Unauthorized`, not "couldn't fetch".

6. **Silence is the normal state.** This runs unattended every day. It must not
   notify on a flaky-wifi failure, because a notification you see weekly is one
   you learn to dismiss unread. It escalates only when there is nothing left to
   show, and otherwise fails loudly where a failure belongs — a non-zero exit
   the timer records, and a source that says so in the strip's first place the next time you open it.

## Accessibility & Inclusion

A personal single-user tool, so no external WCAG mandate, but the baseline
holds and some of it is load-bearing here:

- **Contrast over an arbitrary photograph** is the hard problem, since the strip sits on the wallpaper. It is a mat, solid under the caption, rather than a translucent tint.
- **Keyboard-complete.** Every action has a key, `?` lists them, and the arrows start from the selection. The buttons take no focus, so the arrows always belong to the strip. Nothing requires the pointer.
- **State is never colour alone.** The caption says what is selected, and the selected tile also carries the accent rule, a second channel rather than the only one. TODAY and BEFORE are words.
- Dark by default, because it is over a photograph and at the same hue as the
  rest of the desktop. There is no light variant and no reason for one.
