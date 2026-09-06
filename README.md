# Cursor Forge

Forge retro pixel-art mouse cursors for [Omarchy](https://omarchy.org), right
from the bar. Pick a style — a classic pixel arrow, a **skeletal pointing
hand**, or any image of your own — and a color that either follows your
Omarchy theme accent automatically or stays fixed to a custom hex. Cursor
Forge renders a real XCursor theme on the spot and applies it live to
Hyprland and GTK apps.

![Cursor Forge preview](preview.png)

## What you get

- **Bar widget** showing a live preview of your current cursor. Click it to
  open the panel; scroll on it to cycle styles.
- **Theme-matched color**: when your Omarchy theme changes, the cursor is
  re-forged in the new accent automatically.
- **Custom color**: swatches or any `#rrggbb` hex.
- **Skeleton hand**: a hand-authored, retro pixel-art skeletal hand pointing
  its index finger — segmented phalanges, knuckle bones, a theme-colored
  ring, and twin wrist bones.
- **Fourteen shapes**, one family: arrow, hand, text beam, wait, progress,
  crosshair, all four resize arrows, move, not-allowed, grab, and grabbing —
  with their common alias names, so apps rarely fall back to another theme.
- **Animated**: the wait hourglass drains, the progress hourglass flips, and
  the skeleton's ring glints. One toggle makes everything static if you
  prefer.
- **Left-handed mode**: mirrors the hand and arrow shapes and their
  hotspots.
- **Custom image style**: point it at any image file and it becomes your
  cursor, with a configurable hotspot (requires ImageMagick).
- **Native Hyprcursor + XCursor output**: when `hyprcursor-util` is
  installed the theme is compiled for Hyprland's preferred format too;
  otherwise the XCursor files serve everything.
- **Sizes** 24, 48, and 72 px, pixel-perfect integer scales.
- **File-driven**: everything is stored in
  `~/.config/cursorforge/settings.json`. Edit it by hand and the change
  applies live.
- **Reversible**: "Restore system cursor" puts back whatever theme you had
  before the first apply.

## Install

```bash
omarchy plugin add https://github.com/ErikBurdett/omarchy-cursor-forge.git --enable
```

Then add the widget to your bar if it did not appear automatically:

```bash
omarchy plugin enable io.github.erikburdett.cursorforge right
```

Cursor Forge changes nothing until you click something in its panel: the
first apply is your consent, and the previous cursor theme is recorded so it
can be restored.

## Usage

- **Click** the bar widget to open the panel; pick a style, color, and size.
  Changes apply immediately.
- **Scroll** on the bar widget to cycle styles.
- **Edit the file**: `~/.config/cursorforge/settings.json` is watched;
  hand edits apply live. Keys: `style` (`classic` | `skeleton` | `image`),
  `colorMode` (`theme` | `custom`), `customColor`, `size` (24/48/72),
  `imagePath`, `imageHotspot` (`"x,y"` on the 24px grid), `leftHanded`,
  `animated`, `active`.
- **Script it** over the shell IPC:

  ```bash
  omarchy-shell io.github.erikburdett.cursorforge status
  omarchy-shell io.github.erikburdett.cursorforge setStyle skeleton
  omarchy-shell io.github.erikburdett.cursorforge setColor "#c05a4a"
  omarchy-shell io.github.erikburdett.cursorforge matchTheme
  omarchy-shell io.github.erikburdett.cursorforge cycle
  omarchy-shell io.github.erikburdett.cursorforge toggleLeftHanded
  omarchy-shell io.github.erikburdett.cursorforge toggleAnimation
  omarchy-shell io.github.erikburdett.cursorforge setImage /path/to/img.png
  omarchy-shell io.github.erikburdett.cursorforge setImageHotspot "3,1"
  omarchy-shell io.github.erikburdett.cursorforge reset
  ```

## How it works

`cursorgen.py` (Python standard library only) renders the pixel-art shapes,
recolors them, and writes a standards-compliant XCursor theme to
`~/.local/share/icons/CursorForge` — fourteen shapes with their common
aliases, at 24/48/72 px with premultiplied alpha, correct hotspots, and
multi-frame animation where a shape animates. Anything else inherits from
Adwaita. When `hyprcursor-util` is present, the same art is compiled into a
native Hyprcursor theme in the same directory, which Hyprland picks up
first. It then applies the theme with `hyprctl setcursor` and GTK's
`org.gnome.desktop.interface cursor-theme`/`cursor-size` settings, and the
service re-asserts it when the shell starts, so it survives logins without
touching any Hyprland or GTK config files.

## Dependencies

- `python3` (required; part of a stock Omarchy install)
- `hyprctl` and `gsettings` (used when present; part of a stock install)
- `hyprcursor-util` (optional; enables the native Hyprcursor output, present
  on stock Omarchy)
- ImageMagick `magick` (optional; only for the custom image style)

Nothing is downloaded or installed by the plugin at any point.

## Removal

Restore your previous cursor first, then remove the plugin:

```bash
omarchy-shell io.github.erikburdett.cursorforge reset
omarchy plugin remove io.github.erikburdett.cursorforge
```

Optional cleanup of everything Cursor Forge ever wrote:

```bash
rm -rf ~/.local/share/icons/CursorForge ~/.config/cursorforge
```

## Development

```bash
python3 -m pytest tests/            # manifest contract + generator tests
python3 cursorgen.py preview --style skeleton --color '#6b8a69' \
  --scale 10 --dark --out /tmp/sheet.png   # art contact sheet
omarchy plugin validate .
```

## License

MIT — see [LICENSE](LICENSE).
