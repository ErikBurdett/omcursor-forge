# Contributing to Cursor Forge

Thanks for your interest! Bug reports, art improvements, and new features
are all welcome.

## Getting set up

```bash
git clone https://github.com/ErikBurdett/omarchy-cursor-forge.git
cd omarchy-cursor-forge
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/pytest -q tests/
```

To run your working copy inside the Omarchy shell, clone it into the plugins
directory and restart the shell:

```bash
git clone . ~/.config/omarchy/plugins/io.github.erikburdett.cursorforge
omarchy plugin enable io.github.erikburdett.cursorforge right
omarchy-restart-shell
```

**Editing QML requires `omarchy-restart-shell`** — Quickshell keeps the
compiled component and a plugin disable/enable does not drop it.

## Project layout

| File | Role |
| --- | --- |
| `cursorgen.py` | All art (character grids), the XCursor/PNG encoders, Hyprcursor compilation, and the apply/reset/persist logic. Stdlib only. |
| `Service.qml` | State owner: watches the settings file and the Omarchy theme, debounces and runs the generator, exposes IPC. |
| `BarWidget.qml` | Bar entry: live cursor preview, click-to-open panel. |
| `Panel.qml` | The picker UI. |
| `tests/` | Manifest contract tests and generator tests (hermetic — they never touch your real cursor or config). |

## Working on the pixel art

Cursor art is authored as 24×24 character grids in `cursorgen.py` (`.`
transparent, `#` outline, `F/H/S` colorized fill/highlight/shade, `L/B/b/d`
bone ramp, `R` accent, `W` sparkle). Review your changes the way the
originals were reviewed — at native size, enlarged, and on both light and
dark backgrounds:

```bash
python3 cursorgen.py preview --style skeleton --color '#6b8a69' --scale 10 --dark --out /tmp/sheet.png
python3 cursorgen.py preview --style classic  --color '#6b8a69' --scale 3  --out /tmp/sheet-small.png
```

Style rules the art follows: light from the upper-left, restrained
highlights over deep readable shadows, selective warm local-color outlines
(no universal sticker-black borders), large value clusters over
salt-and-pepper noise. Every row must be exactly 24 characters — the tests
enforce it.

## Before opening a PR

- `pytest -q tests/` passes.
- `omarchy plugin validate .` passes.
- `/usr/lib/qt6/bin/qmlformat -n *.qml` parses (if you touched QML).
- No symlinks are introduced anywhere in the repo.
- The change is described in `CHANGELOG.md` under an *Unreleased* heading.
- New behavior comes with a test where the behavior is testable
  hermetically.

## Scope guardrails

- `cursorgen.py` stays standard-library-only. Optional integrations
  (ImageMagick, hyprcursor-util) must degrade gracefully when absent.
- The plugin never writes to Hyprland/GTK config files, never installs
  anything, and never touches the network. Applies go through
  `hyprctl setcursor` and `gsettings` only, and only on explicit user
  action.
- Cursor art must be original work licensed under this repo's MIT license.
