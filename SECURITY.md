# Security Policy

## Reporting

Please report suspected vulnerabilities via
[GitHub private vulnerability reporting](https://github.com/ErikBurdett/omarchy-cursor-forge/security/advisories/new)
rather than a public issue. You should receive a response within a week.

## Security posture

Cursor Forge is designed to have a small, auditable surface:

- **No network access.** Nothing is downloaded, ever.
- **No privilege escalation.** No sudo, no polkit, no setuid helpers.
- **Standard-library-only Python.** `cursorgen.py` imports nothing outside
  the Python standard library and is invoked with `python3 -I` (isolated
  mode) by the shell service.
- **Bounded writes.** The generator writes only to
  `$XDG_DATA_HOME/icons/CursorForge/` and
  `$XDG_CONFIG_HOME/cursorforge/settings.json`, atomically via temp file +
  rename.
- **Bounded external commands.** It executes only `hyprctl setcursor`,
  `gsettings set org.gnome.desktop.interface …`, and optionally `magick`
  (custom-image style) and `hyprcursor-util` (Hyprcursor output), all
  resolved with `shutil.which`, with timeouts, and never through a shell.
- **Consent model.** Nothing changes until the user's first explicit apply;
  the prior cursor theme is recorded then and can always be restored.
- **Settings hygiene.** The watched settings file is parsed defensively and
  unknown keys are dropped on save.

## Supported versions

Only the latest release receives fixes.
