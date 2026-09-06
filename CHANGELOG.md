# Changelog

All notable changes to OmCursor Forge (formerly Cursor Forge) are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.2.0] - 2026-09-06

### Added

- Three nerd styles: **Modern** (sleek white-bordered arrow with
  anti-aliased edges and theme-colored fill — deliberately static),
  **D20** (geometric twenty-sider with a real 20 on its face, glints and
  bobs), and **Terminal** (prompt chevron with a blinking block caret).
- **Theme tint for custom images**: a panel toggle (and `toggleImageTint`
  IPC / `imageTint` setting) colorizes any custom cursor image toward the
  active cursor color by luminance, so image cursors can follow the theme
  too.
- `fix-fractional-cursor`: one command that fixes cropped cursors on
  fractionally scaled monitors (switches Hyprland to software cursors,
  persisted via a marked, backed-up config block; `remove` undoes it).
  Applies detect the fractional-scale + hardware-cursor combination and
  point at the fix.

### Changed

- **Single rendering lane.** Hyprcursor output is gone entirely; only the
  byte-verified XCursor theme ships. Two format lanes meant two scaling
  behaviors that could disagree — the cut-off-at-24px report traced to
  size handling outside the XCursor path.
- Theme builds now hold an exclusive lock (carried from 2.1.0's QA).

## [2.1.0] - 2026-09-06

### Changed

- **Renamed to OmCursor Forge** (display name, generated icon-theme
  directory `OmCursorForge`, repository slug). The plugin id, settings
  path, and click-ripple marker are permanent identifiers and keep their
  original names; the old `CursorForge` icon directory is cleaned up on
  the next apply.

### Fixed

- Theme builds and resets now take an exclusive file lock, so overlapping
  runs (for example during a shell restart) can never interleave writes
  into a mixed theme set.

## [2.0.0] - 2026-09-06

### Changed

- **Breaking: the standalone `skeleton` style folded into `lich`.** The
  skeletal hand now always wears its wizard-robe sleeve; existing
  settings with `"style": "skeleton"` migrate to `lich` automatically.
  The styles are now classic, lich, sword, wand, and image.

## [1.7.0] - 2026-09-06

### Added

- **Mode presets**: `setMode static|glints|full` over IPC (and reported in
  `status`) — *static* is a completely animation-free theme that just
  applies the style, *glints* keeps in-place sparkles without sprite
  movement, *full* is everything. The panel's Animated/Motion toggles map
  onto the same switches.
- **96 px HiDPI nominal**: themes now also ship 96 px images (an exact 2x
  of the native 48 px art for the hand styles), so scaled monitors get
  crisp cursors, and 96 is available as a size for accessibility.

### Fixed

- QA pass for marketplace readiness: a Restore pressed while the generator
  was busy is now queued instead of silently ignored, and a newer apply
  correctly supersedes a queued reset. Stress-tested click floods and
  rapid recolors leak-free. SECURITY.md now documents exactly what the
  optional click-ripple bind can and cannot observe, plus notes for
  marketplace reviewers.

## [1.6.0] - 2026-09-06

### Added

- **Sprite motion — the cursor itself moves.** The skeleton and lich hands
  periodically retract the pointing finger and tap back down at the
  hotspot (with a ring flash on the strike); on links the charged hand
  taps eagerly at double rate; the sword and wand bob as if floating. The
  hotspot never moves — clicks always land where the extended tip points.
- **Customization controls** in the panel, the settings file, and IPC:
  *Motion* toggle (sprite movement on/off, independent of the in-place
  glints), *Speed* (calm / normal / lively — scales every animation
  delay), and *Ripple shape* (diamond / circle / burst). New settings
  keys: `motion`, `speed`, `rippleShape`; new IPC: `toggleMotion`,
  `setSpeed`, `setRippleShape`.

## [1.5.0] - 2026-09-06

### Fixed

- **Animations now actually play on Hyprland.** Root cause found in
  Hyprland's cursor manager: it animates the XCursor lane only when no
  hyprcursor theme is loaded, and the hyprcursor lane renders a single
  frame — so our own Hyprcursor output was freezing every animation.
  Animated builds no longer ship hyprcursor files (and scrub stale ones);
  fully static builds still get them. Note: Wayland apps using the
  cursor-shape protocol and Hyprland-owned surfaces animate; XWayland apps
  and games that draw their own cursors cannot, by design of the protocol.

### Added

- **Click ripple**: an accent-colored pixel-art ring bursts at the pointer
  on every left click, via a new click-through overlay plus an optional
  NON-CONSUMING Hyprland mouse bind (run `./install-click-ripple`; remove
  with `./uninstall-click-ripple`; toggle in the panel or with
  `toggleClickRipple`). The bind observes clicks without intercepting them.
- **Hover state for the hand styles**: on links and buttons the skeleton
  and lich hands charge up — fingertip spark and lit ring pulsing at
  600 ms — so the cursor visibly reacts to interactive elements.
- Stronger idle animations: ring and sword glints are now double-blinks,
  and the wand star pulses on a faster cycle.

## [1.4.0] - 2026-09-06

### Added

- **Lich sleeve style**: the skeletal hand emerging from a dark violet
  wizard-robe sleeve with a braided cuff in the accent color and tattered
  cloth drooping off the wrist. Native 24px and 48px art, animated ring
  gem, left-handed support.

### Fixed

- Re-applying a regenerated theme now also bounces `hyprctl setcursor`
  through the inherited theme. Hyprland caches the loaded cursor theme by
  name, so new art under the same theme name could keep rendering stale
  frames until relog — this was why art updates sometimes looked
  unchanged.

## [1.3.0] - 2026-09-06

### Changed

- **The skeletal hand got a native 48px remaster.** The 48 nominal size
  (the default on many setups, including HiDPI) is no longer a 2× upscale
  of the 24px grid: it is its own 48×48 art — the proven silhouette with
  outline corners beveled into real curves, a gold ring with a gem that
  sparkles on the glint frame, a nail highlight, and hairline cracks
  across the back of the hand. The 24 and 72 sizes keep the crisp 24px
  grid. The cursor format's per-size image support makes this free —
  other styles will follow.

## [1.2.0] - 2026-09-06

### Added

- Two new default styles: **Sword** (theme-colored blade with a bone
  crossguard and gem pommel; the blade edge glints) and **Wand** (dark wood
  shaft with a starred accent tip that sparkles). Both follow the theme
  accent, animate under the existing *Animated* toggle, and appear in the
  panel's style tiles, the style cycle, and the previews.

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
