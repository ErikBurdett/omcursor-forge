# Changelog

All notable changes to Cursor Forge are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-09-05

### Added

- Full shape coverage: `progress`, `crosshair`, `ew/ns/nwse/nesw-resize`,
  `move`/fleur, `not-allowed`, `grab`, and `grabbing`, each with its common
  X11/CSS alias names — fourteen shapes total, so mixed-theme fallback
  moments are rare.
- **Animation**: the wait hourglass drains over three frames, the progress
  cursor's mini hourglass flips, and the skeleton hand's accent ring glints
  on a slow loop. A single *Animated* toggle (panel, settings file, or
  `toggleAnimation` IPC) turns every animation off for a fully static theme.
- **Native Hyprcursor output**: when `hyprcursor-util` is installed the same
  art is also compiled into a Hyprcursor theme alongside the XCursor files,
  which Hyprland prefers automatically. Without the tool, the XCursor
  fallback is used — no hard dependency.
- **Left-handed mode**: mirrors the hand and arrow shapes (and their
  hotspots) while leaving direction-meaningful shapes like the diagonal
  resizes alone.
- Custom-image hotspot control (`imageHotspot` setting,
  `--image-hotspot x,y`, `setImageHotspot` IPC).
- A shape gallery in the panel showing every generated shape at native
  pixel size.

### Changed

- `progress` and `left_ptr_watch` are now a real arrow-with-hourglass shape
  instead of aliasing the wait hourglass.

## [1.0.0] - 2026-09-05

### Added

- Initial release: classic arrow, skeletal pointing hand, and custom-image
  styles; theme-accent or custom color; sizes 24/48/72; live bar-widget
  preview; panel picker; watched settings file at
  `~/.config/cursorforge/settings.json`; IPC control; restore of the
  previous system cursor.
