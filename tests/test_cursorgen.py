"""Tests for the cursor theme generator.

Everything here is hermetic: themes are built into temp directories with
--no-apply/--no-save, and nothing ever calls hyprctl or gsettings.
"""

import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cursorgen  # noqa: E402

ALL_GRIDS = {
    "ARROW": cursorgen.ARROW,
    "HAND_CLASSIC": cursorgen.HAND_CLASSIC,
    "HAND_SKELETON": cursorgen.HAND_SKELETON,
    "TEXT_BEAM": cursorgen.TEXT_BEAM,
    "HOURGLASS_FULL": cursorgen.HOURGLASS_FULL,
    "HOURGLASS_HALF": cursorgen.HOURGLASS_HALF,
    "HOURGLASS_DRAINED": cursorgen.HOURGLASS_DRAINED,
    "RESIZE_EW": cursorgen.RESIZE_EW,
    "RESIZE_NS": cursorgen.RESIZE_NS,
    "RESIZE_NWSE": cursorgen.RESIZE_NWSE,
    "RESIZE_NESW": cursorgen.RESIZE_NESW,
    "MOVE_FLEUR": cursorgen.MOVE_FLEUR,
    "CROSSHAIR": cursorgen.CROSSHAIR,
    "NOT_ALLOWED": cursorgen.NOT_ALLOWED,
    "PROGRESS_ARROW": cursorgen.PROGRESS_ARROW,
    "PROGRESS_ARROW_DRAINED": cursorgen.PROGRESS_ARROW_DRAINED,
    "GRAB_HAND": cursorgen.GRAB_HAND,
    "GRABBING_HAND": cursorgen.GRABBING_HAND,
    "HAND_LICH": cursorgen.HAND_LICH,
    "HAND_LICH_GLINT": cursorgen.HAND_LICH_GLINT,
    "SWORD": cursorgen.SWORD,
    "SWORD_GLINT": cursorgen.SWORD_GLINT,
    "WAND": cursorgen.WAND,
    "WAND_GLINT": cursorgen.WAND_GLINT,
    "MODERN": cursorgen.MODERN,
    "D20": cursorgen.D20,
    "D20_GLINT": cursorgen.D20_GLINT,
    "TERMINAL_ON": cursorgen.TERMINAL_ON,
    "TERMINAL_OFF": cursorgen.TERMINAL_OFF,
}


def parse_xcursor(data):
    assert data[:4] == b"Xcur"
    header, version, ntoc = struct.unpack_from("<III", data, 4)
    assert header == 16 and version == 0x10000
    images = []
    for index in range(ntoc):
        ctype, nominal, position = struct.unpack_from("<III", data, 16 + index * 12)
        assert ctype == cursorgen.XCURSOR_IMAGE_TYPE
        chunk = struct.unpack_from("<9I", data, position)
        size, _, chunk_nominal, chunk_version, w, h, xhot, yhot, delay = chunk
        assert size == 36 and chunk_version == 1 and chunk_nominal == nominal
        assert position + 36 + w * h * 4 <= len(data)
        pixels = data[position + 36:position + 36 + w * h * 4]
        images.append({"nominal": nominal, "w": w, "h": h, "xhot": xhot,
                       "yhot": yhot, "delay": delay, "pixels": pixels})
    return images


def test_grids_are_well_formed():
    for name, grid in ALL_GRIDS.items():
        assert len(grid) == cursorgen.BASE, name
        for row in grid:
            assert len(row) == cursorgen.BASE, f"{name}: {row!r}"
        for style in ("classic", "lich"):
            cursorgen.render_grid(grid, cursorgen.palette(style, (107, 138, 105)))


def test_every_shape_resolves_for_all_styles():
    for shape in cursorgen.SHAPES:
        for grid_style in cursorgen.ART_STYLES:
            for left_handed in (False, True):
                frames, xhot, yhot = cursorgen.shape_spec(
                    shape, grid_style, left_handed)
                assert frames, (shape, grid_style)
                assert 0 <= xhot < cursorgen.BASE
                assert 0 <= yhot < cursorgen.BASE


def test_left_handed_mirrors_handed_shapes_only():
    frames_r, xhot_r, _ = cursorgen.shape_spec("default", "classic", False)
    frames_l, xhot_l, _ = cursorgen.shape_spec("default", "classic", True)
    assert xhot_l == cursorgen.BASE - 1 - xhot_r
    assert frames_l[0][0] == cursorgen.mirror_grid(frames_r[0][0])
    for shape in ("nwse-resize", "nesw-resize", "crosshair", "text"):
        right = cursorgen.shape_spec(shape, "classic", False)
        left = cursorgen.shape_spec(shape, "classic", True)
        assert right == left


def test_animation_flag_flattens_to_one_frame():
    frames, _, _ = cursorgen.shape_spec("wait", "classic", False, animated=True)
    assert len(frames) == 3 and frames[0][1] > 0
    frames, _, _ = cursorgen.shape_spec("wait", "classic", False, animated=False)
    assert frames == [(cursorgen.HOURGLASS_FULL, 0)]
    motion, _, _ = cursorgen.shape_spec("default", "lich", False)
    assert len(motion) == 5


def test_grid_motion_helpers():
    grid = ["F...", ".F..", "..F.", "...F"]
    assert cursorgen.shift_grid(grid, 1, 0) == [".F..", "..F.", "...F", "...."]
    assert cursorgen.shift_grid(grid, 0, 1) == ["....", "F...", ".F..", "..F."]
    assert cursorgen.shift_grid(grid, -1, -1) == ["F...", ".F..", "..F.", "...."]
    bent = cursorgen.bend_finger(cursorgen.HAND_SKELETON, 2)
    assert len(bent) == cursorgen.BASE
    assert bent[0] == bent[1] == "." * cursorgen.BASE
    assert bent[2] == cursorgen.HAND_SKELETON[0]      # tip moved down
    assert bent[4:] == cursorgen.HAND_SKELETON[4:]    # body planted


def test_motion_frames_move_and_flag_disables_them():
    moving, xhot, yhot = cursorgen.shape_spec("default", "lich", False,
                                              motion=True)
    still, _, _ = cursorgen.shape_spec("default", "lich", False,
                                       motion=False)
    assert (xhot, yhot) == (9, 0)  # hotspot never follows the sprite
    assert len({tuple(grid) for grid, _ in moving}) >= 3
    assert still == cursorgen.LICH_HAND_FRAMES
    # sword bobs diagonally
    sword_motion, _, _ = cursorgen.shape_spec("default", "sword", False)
    assert any(grid == cursorgen.SWORD_BOB for grid, _ in sword_motion)


def test_speed_scales_delays(tmp_path):
    for speed, expected in (("lively", 210), ("calm", 595)):
        theme = build(tmp_path / speed, "classic", extra=("--speed", speed))
        images = parse_xcursor((theme / "cursors" / "wait").read_bytes())
        first = next(img for img in images if img["nominal"] == 24)
        assert first["delay"] == expected


def test_ripple_shapes_differ(tmp_path):
    frames = {shape: cursorgen.ripple_frames((210, 164, 20), shape)
              for shape in cursorgen.RIPPLE_SHAPES}
    assert frames["diamond"] != frames["circle"]
    assert frames["circle"] != frames["burst"]
    theme = build(tmp_path, "classic", extra=("--ripple-shape", "burst"))
    assert (theme / "previews" / "ripple_0.png").is_file()


def test_pointer_is_distinct_from_default_for_hand_styles():
    for grid_style in ("lich",):
        default, _, _ = cursorgen.shape_spec("default", grid_style, False)
        pointer, _, _ = cursorgen.shape_spec("pointer", grid_style, False)
        assert default != pointer, grid_style
        # hover state pulses fast: every frame carries a short delay
        assert all(delay <= 400 for _, delay in pointer)


def test_hand_48_grids_are_well_formed():
    roles = cursorgen.palette("skeleton", (210, 164, 20))
    for grid in (cursorgen.HAND_LICH_48, cursorgen.HAND_LICH_48_GLINT):
        assert len(grid) == cursorgen.HIRES
        assert all(len(row) == cursorgen.HIRES for row in grid)
        cursorgen.render_grid(grid, roles, cursorgen.HIRES)
    # the glint frame differs only around the ring gem
    diff = sum(a != b for row_a, row_b in zip(cursorgen.HAND_LICH_48,
                                              cursorgen.HAND_LICH_48_GLINT)
               for a, b in zip(row_a, row_b))
    assert 1 <= diff <= 8


def test_hidpi_96_nominal_scales_the_hires_art(tmp_path):
    theme = build(tmp_path, "lich")
    images = parse_xcursor((theme / "cursors" / "default").read_bytes())
    img48 = next(i for i in images if i["nominal"] == 48)
    img96 = next(i for i in images if i["nominal"] == 96)
    assert (img96["xhot"], img96["yhot"]) == (36, 0)
    upscaled = bytearray()
    for y in range(96):
        for x in range(96):
            src = ((y // 2) * 48 + (x // 2)) * 4
            upscaled += img48["pixels"][src:src + 4]
    assert bytes(upscaled) == img96["pixels"], \
        "96px should be an exact 2x of the native 48px art"


def test_lich_48_nominal_has_native_art(tmp_path):
    theme = build(tmp_path, "lich")
    images = parse_xcursor((theme / "cursors" / "default").read_bytes())
    img24 = next(i for i in images if i["nominal"] == 24)
    img48 = next(i for i in images if i["nominal"] == 48)
    assert (img48["xhot"], img48["yhot"]) == (18, 0)
    upscaled = bytearray()
    for y in range(48):
        for x in range(48):
            src = ((y // 2) * 24 + (x // 2)) * 4
            upscaled += img24["pixels"][src:src + 4]
    assert bytes(upscaled) != img48["pixels"], \
        "48px lich should be native art, not a 2x upscale"


def test_parse_color():
    assert cursorgen.parse_color("#6b8a69") == (0x6B, 0x8A, 0x69)
    for bad in ("6b8a69", "#6b8a6", "#6b8a6zz", "", "#12345g"):
        with pytest.raises(ValueError):
            cursorgen.parse_color(bad)


def test_parse_hotspot():
    assert cursorgen.parse_hotspot("0,0") == (0, 0)
    assert cursorgen.parse_hotspot("11,23") == (11, 23)
    for bad in ("", "1", "1,", "24,0", "0,24", "-1,0", "a,b"):
        with pytest.raises(ValueError):
            cursorgen.parse_hotspot(bad)


def test_alias_map_covers_every_shape():
    assert set(cursorgen.ALIASES) == set(cursorgen.SHAPES)
    seen = set()
    for shape, names in cursorgen.ALIASES.items():
        assert shape == names[0]
        for name in names:
            assert name not in seen, f"alias {name} claimed twice"
            seen.add(name)


def build(tmp_path, style, color="#6b8a69", image=None, extra=()):
    code = cursorgen.main([
        "apply", "--style", style, "--color", color,
        "--out", str(tmp_path), "--no-apply", "--no-save", *extra,
    ] + (["--image", str(image)] if image else []))
    assert code == 0
    return tmp_path / cursorgen.THEME_NAME


@pytest.mark.parametrize("style", list(cursorgen.ART_STYLES))
def test_theme_builds_valid_xcursor_files(tmp_path, style):
    theme = build(tmp_path, style)
    index = (theme / "index.theme").read_text()
    assert "Inherits=Adwaita" in index

    grid_style = cursorgen.grid_style_for(style)
    for shape, names in cursorgen.ALIASES.items():
        frames, xhot, yhot = cursorgen.shape_spec(shape, grid_style, False)
        for name in names:
            path = theme / "cursors" / name
            assert path.is_file(), f"{style}: missing cursor {name}"
            images = parse_xcursor(path.read_bytes())
            expected = [cursorgen.BASE * f for f in cursorgen.SCALES
                        for _ in frames]
            assert [img["nominal"] for img in images] == expected
            for img in images:
                factor = img["nominal"] // cursorgen.BASE
                assert img["w"] == img["h"] == img["nominal"]
                assert (img["xhot"], img["yhot"]) == (xhot * factor,
                                                      yhot * factor)


def test_wait_cursor_animates(tmp_path):
    theme = build(tmp_path, "classic")
    images = parse_xcursor((theme / "cursors" / "wait").read_bytes())
    per_size = [img for img in images if img["nominal"] == cursorgen.BASE]
    assert len(per_size) == 3
    assert [img["delay"] for img in per_size] == [350, 350, 550]


def test_no_animation_builds_static_theme(tmp_path):
    theme = build(tmp_path, "lich", extra=("--no-animation",))
    for name in ("wait", "default", "progress"):
        images = parse_xcursor((theme / "cursors" / name).read_bytes())
        assert len(images) == len(cursorgen.SCALES)
        assert all(img["delay"] == 0 for img in images)


def test_left_handed_theme_mirrors_hotspot(tmp_path):
    theme = build(tmp_path, "lich", extra=("--left-handed",))
    images = parse_xcursor((theme / "cursors" / "default").read_bytes())
    assert images[0]["xhot"] == cursorgen.BASE - 1 - 9


def test_transparent_pixels_are_fully_zero(tmp_path):
    theme = build(tmp_path, "lich")
    images = parse_xcursor((theme / "cursors" / "default").read_bytes())
    pixels = images[0]["pixels"]
    seen_transparent = seen_opaque = False
    for at in range(0, len(pixels), 4):
        value = struct.unpack_from("<I", pixels, at)[0]
        alpha = value >> 24
        if alpha == 0:
            # Premultiplied ARGB: zero alpha must mean a zero pixel.
            assert value == 0
            seen_transparent = True
        else:
            assert alpha == 255
            seen_opaque = True
    assert seen_transparent and seen_opaque


def test_previews_are_valid_pngs(tmp_path):
    theme = build(tmp_path, "classic")
    for name in ("current.png", "classic.png", "lich.png", "modern.png",
                 "d20.png", "terminal.png",
                 "sword.png", "wand.png", "shapes.png", "ripple_0.png",
                 "ripple_3.png"):
        data = (theme / "previews" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", name
        width, height = struct.unpack_from(">II", data, 16)
        if name == "shapes.png":
            assert width > height
        elif name.startswith("ripple_"):
            assert width == height == cursorgen.HIRES
        else:
            assert width == height == cursorgen.BASE


def test_no_hyprcursor_files_ever(tmp_path):
    """Single rendering lane by design: only XCursor ships (the Hyprcursor
    lane was removed after size/scale mis-rendering), and stale files from
    old builds are scrubbed."""
    theme = build(tmp_path, "lich", extra=("--no-animation",))
    (theme / "manifest.hl").write_text("stale")
    (theme / "hyprcursors").mkdir()
    theme = build(tmp_path, "lich")
    assert not (theme / "manifest.hl").exists()
    assert not (theme / "hyprcursors").exists()


def test_no_save_leaves_config_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    build(tmp_path, "classic")
    assert not (tmp_path / "config").exists()


def test_settings_roundtrip_whitelists_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    cursorgen.save_settings({
        "style": "lich", "colorMode": "theme", "customColor": "#123456",
        "size": 24, "imagePath": "", "imageHotspot": "0,0",
        "imageTint": True,
        "leftHanded": False, "animated": True, "motion": False,
        "speed": "lively", "rippleShape": "burst", "clickRipple": True,
        "active": True,
        "restore": {"theme": "Adwaita", "size": 24},
        "junk": "dropped",
    })
    loaded = cursorgen.load_settings()
    assert loaded["style"] == "lich"
    assert loaded["active"] is True and loaded["animated"] is True
    assert loaded["motion"] is False and loaded["speed"] == "lively"
    assert loaded["rippleShape"] == "burst"
    assert loaded["imageTint"] is True
    assert "junk" not in loaded
    raw = json.loads(cursorgen.config_path().read_text())
    assert raw == loaded


def test_scale_pixels_nearest():
    pixels = [(1, 2, 3, 255), (4, 5, 6, 255),
              (7, 8, 9, 255), (10, 11, 12, 255)]
    scaled = cursorgen.scale_pixels(pixels, 2, 2, 2)
    assert len(scaled) == 16
    assert scaled[0] == scaled[1] == scaled[4] == scaled[5] == pixels[0]
    assert scaled[15] == pixels[3]


def test_grid_helpers():
    grid = ["FF..", "#...", "....", "...S"]
    assert cursorgen.mirror_grid(grid) == ["..FF", "...#", "....", "S..."]
    assert cursorgen.transpose_grid(grid)[0] == "F#.."
    merged = cursorgen.merge_grids(["F#."], [".FF"])
    assert merged == ["FFF"]
    stamped = cursorgen.compose_grid(["....", "....", "....", "...."],
                                     ["FF", "FF"], 1, 2)
    assert stamped[2] == ".FF." and stamped[3] == ".FF."


def test_tint_pixels_colorizes_by_luminance():
    rgb = (210, 164, 20)
    tinted = cursorgen.tint_pixels(
        [(255, 255, 255, 255), (0, 0, 0, 255), (128, 128, 128, 60)], rgb)
    assert tinted[0] == (210, 164, 20, 255)     # white -> full accent
    assert tinted[1] == (0, 0, 0, 255)          # black stays black
    assert tinted[2][3] == 60                   # alpha preserved
    assert 0 < tinted[2][0] < 210


def test_modern_style_is_static_and_antialiased(tmp_path):
    frames, xhot, yhot = cursorgen.shape_spec("default", "modern", False)
    assert len(frames) == 1 and frames[0][1] == 0
    assert (xhot, yhot) == (2, 1)
    roles = cursorgen.palette("classic", (210, 164, 20))
    pixels = cursorgen.render_grid(cursorgen.MODERN, roles)
    alphas = {a for _, _, _, a in pixels}
    assert 96 in alphas and 255 in alphas  # AA edge + solid pixels


def test_terminal_caret_blinks():
    frames, _, _ = cursorgen.shape_spec("default", "terminal", False)
    assert len(frames) == 2
    assert frames[0][0] != frames[1][0]


def test_missing_image_fails_cleanly(tmp_path, capsys):
    code = cursorgen.main([
        "apply", "--style", "image", "--image", str(tmp_path / "nope.png"),
        "--color", "#6b8a69", "--out", str(tmp_path),
        "--no-apply", "--no-save",
    ])
    assert code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and "not found" in report["error"]
