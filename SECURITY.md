# Security Policy

## Reporting

Please report suspected vulnerabilities via
[GitHub private vulnerability reporting](https://github.com/ErikBurdett/omcursor-forge/security/advisories/new)
rather than a public issue. You should receive a response within a week.

## Security posture

OmCursor Forge is designed to have a small, auditable surface:

- **No network access.** Nothing is downloaded, ever.
- **No privilege escalation.** No sudo, no polkit, no setuid helpers.
- **Standard-library-only Python.** `cursorgen.py` imports nothing outside
  the Python standard library and is invoked with `python3 -I` (isolated
  mode) by the shell service.
- **Bounded writes.** The generator writes only to
  `$XDG_DATA_HOME/icons/OmCursorForge/` and
  `$XDG_CONFIG_HOME/cursorforge/settings.json`, atomically via temp file +
  rename.
- **Bounded external commands.** It executes only `hyprctl setcursor`,
  `gsettings set org.gnome.desktop.interface …`, and optionally `magick`
  (custom-image style), all
  resolved with `shutil.which`, with timeouts, and never through a shell.
- **Consent model.** Nothing changes until the user's first explicit apply;
  the prior cursor theme is recorded then and can always be restored.
- **Settings hygiene.** The watched settings file is parsed defensively and
  unknown keys are dropped on save.

## The optional click-ripple bind, disclosed

The click ripple is **opt-in** and installed only by the user running
`./install-click-ripple` (the plugin never touches keybindings itself).
What it does, exactly:

- Appends one clearly marked, `non_consuming` + `transparent` Hyprland
  bind for `mouse:272` (left button) to `~/.config/hypr/bindings.lua`,
  after backing the file up. It observes button presses; it cannot delay,
  reorder, or swallow them, and it sees **no keyboard input and no click
  coordinates** — on each press it merely runs the shell IPC command
  `omarchy-shell … click`, and the shell service then reads the pointer
  position itself via `hyprctl cursorpos`.
- The ripple overlay window is visual-only: empty input region, no
  keyboard focus, no exclusion zone — it can never intercept a click.
- `./uninstall-click-ripple` removes the marked block (with a backup).

## Notes for marketplace reviewers

- The automated baseline may flag the `installer` capability for
  `install-click-ripple` / `uninstall-click-ripple` /
  `fix-fractional-cursor`. The plugin never runs
  them itself; they are user-invoked, back up the file they edit, refuse
  to double-install, and are fully reversible.
- `CONTRIBUTING.md` contains `git clone` commands for developing this
  repository itself; the plugin's install path is the standard
  `omarchy plugin add`.
- None of the blocking baseline patterns apply: no piped-shell downloads,
  no unpinned remote builds, no sudoers rules, no privilege wrappers, no
  predictable `/tmp` state (runtime writes go to `$XDG_DATA_HOME` and
  `$XDG_CONFIG_HOME` atomically).

## Supported versions

Only the latest release receives fixes.
