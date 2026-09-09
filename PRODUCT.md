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
when a photograph is worth keeping, when one is not worth looking at, or when a
source has stopped working. Sessions are seconds long, weeks apart.

So the tool cannot rely on being remembered. Every time the window opens it has
to re-explain its own state, and the state has to be small enough to re-explain
in one glance.

## Product Purpose

wallhelper fetches one photograph a day from a source you chose, sets it as the
wallpaper, and remembers who took it. Photographs you keep go into a permanent
collection; photographs you don't are deleted when the next one arrives.

It succeeds `hypr-wallpaper`, which rotated a folder on a timer. That tool's
failure was that nothing ever meant anything: the wallpaper changed on its own
schedule, the same images came back around, the folder grew without limit, and
when a source broke the only symptom was that the picture stopped changing —
which looked exactly like the picture not having changed yet.

Success looks like: a photograph you have not seen before is on the screen most
mornings; the ones you liked are still there months later; the ones you didn't
are gone without you doing anything; and when something breaks, the tool says
which source and why, in a sentence.

## Brand Personality

A wall label in a gallery. Quiet, exact, and secondary to the picture.

The voice is the voice of a museum caption: it states what is known and stops.
It never fills a gap with a placeholder — a photograph nobody titled has no
title line, not a line reading "Untitled". It never editorialises about the
photograph, and it never congratulates you for keeping one.

Emotional goal: mild, recurring pleasure. Not delight, not achievement. The
feeling of a good print you walk past every day and still notice.

## Anti-references

- **Wallpaper managers (waypaper, variety, Wallpaper Engine):** a folder
  browser with a thumbnail grid, a settings dialog of checkboxes, and the
  premise that choosing wallpapers is the activity. wallhelper is not a picker.
  Choosing is what it does *for* you; the strip along the bottom is a record of
  what you kept, not a gallery to shop in.
- **Consumer photo app / social feed:** no hearts, no counts, no streaks, no
  infinite scroll, and above all no "like" — see principle 2. Keeping is a
  filing decision with a consequence, not a sentiment you broadcast.
- **A GNOME preferences page:** a header bar, a sidebar of categories, and a
  wall of switch rows. Settings here is one question deep and lives in the
  same typographic language as the plate. If it ever needs a category, the
  answer is that it has grown something it shouldn't have.

## Design Principles

1. **The photograph is the window.** It bleeds to all four edges, cropped
   exactly the way hyprpaper will crop it, so what you are looking at is the
   wallpaper rather than a preview of it. There is no header bar; framing a
   picture in application chrome is the one thing a picture frame exists not to
   do. Every control is laid over the image, and the image is never inset,
   letterboxed, or given a border.

2. **Keeping is the only signal.** There is exactly one thing you can say about
   a photograph, and it has a consequence: keep it, or it goes when the next
   one arrives. No countdown, no second grade of liking, no archive to tidy
   later, no way to switch the deletion off — a second signal would make the
   first one mean nothing. This is the principle that wins trade-offs, and it
   is why the plate has one button rather than two.

3. **The window answers questions; the file holds settings.** The window's job
   is the question you actually opened it to ask — which sources am I using,
   and are they working. Everything else about a source is JSON, because a file
   is better at being a file than a form is: it can hold a parameter this
   version has never heard of. Twice this panel has been the other thing — a
   raw JSON editor, and a wall of fields — and both were the same mistake, one
   putting the file's vocabulary in the window and the other putting the
   window's vocabulary in the file.

4. **Words, not icons.** KEEP, DELETE, NEXT, CHECK. A word answers "what does
   this do" where a glyph asks it, and this is a tool used seconds at a time,
   weeks apart, by someone who will not have memorised anything. The type is
   the interface: a caption face for the title, tracked mono for everything
   transcribed from a file or an API, because it reads like an archive card and
   it is one.

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

- **Contrast over an arbitrary photograph** is the hard problem, since the text
  sits on an image nobody chose for legibility. The plate is a scrim reaching
  0.97 opacity under the text rather than a translucent tint, and the corner
  controls — which sit on bare photograph and can land on white cloud — use
  full-strength text plus a shadow rather than the plate's mid-grey.
- **Keyboard-complete.** Every action has a key, `?` lists them, and opening
  settings moves focus into the panel rather than leaving it out on the photo.
  Nothing requires the pointer.
- **State is never colour alone.** The button says KEEP or DELETE in words. The
  strip is a secondary view and does lean on two visual channels — opacity for
  kept, an accent rule for on-screen — which is the weakest point here; both
  are also available as text in the tooltip.
- Dark by default, because it is over a photograph and at the same hue as the
  rest of the desktop. There is no light variant and no reason for one.
