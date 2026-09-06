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
    "HAND_SKELETON_GLINT": cursorgen.HAND_SKELETON_GLINT,
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
        for style in ("classic", "skeleton"):
            cursorgen.render_grid(grid, cursorgen.palette(style, (107, 138, 105)))


def test_every_shape_resolves_for_both_styles():
    for shape in cursorgen.SHAPES:
        for grid_style in ("classic", "skeleton"):
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
    glint, _, _ = cursorgen.shape_spec("default", "skeleton", False)
    assert len(glint) == 2


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


@pytest.mark.parametrize("style", ["classic", "skeleton"])
def test_theme_builds_valid_xcursor_files(tmp_path, style):
    theme = build(tmp_path, style)
    index = (theme / "index.theme").read_text()
    assert "Inherits=Adwaita" in index

    grid_style = "skeleton" if style == "skeleton" else "classic"
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
    theme = build(tmp_path, "skeleton", extra=("--no-animation",))
    for name in ("wait", "default", "progress"):
        images = parse_xcursor((theme / "cursors" / name).read_bytes())
        assert len(images) == len(cursorgen.SCALES)
        assert all(img["delay"] == 0 for img in images)


def test_left_handed_theme_mirrors_hotspot(tmp_path):
    theme = build(tmp_path, "skeleton", extra=("--left-handed",))
    images = parse_xcursor((theme / "cursors" / "default").read_bytes())
    assert images[0]["xhot"] == cursorgen.BASE - 1 - 9


def test_transparent_pixels_are_fully_zero(tmp_path):
    theme = build(tmp_path, "skeleton")
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
    for name in ("current.png", "classic.png", "skeleton.png", "shapes.png"):
        data = (theme / "previews" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", name
        width, height = struct.unpack_from(">II", data, 16)
        if name == "shapes.png":
            assert width > height
        else:
            assert width == height == cursorgen.BASE


def test_hyprcursor_meta_generation(tmp_path, monkeypatch):
    """The hyprcursor working set is exercised end to end when the utility
    exists on the machine running the tests; otherwise the build must simply
    skip it without failing."""
    theme = build(tmp_path, "skeleton")
    import shutil as shutil_module
    if shutil_module.which("hyprcursor-util"):
        assert (theme / "manifest.hl").is_file()
        assert (theme / "hyprcursors").is_dir()
    else:
        assert not (theme / "manifest.hl").exists()


def test_no_save_leaves_config_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    build(tmp_path, "classic")
    assert not (tmp_path / "config").exists()


def test_settings_roundtrip_whitelists_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    cursorgen.save_settings({
        "style": "skeleton", "colorMode": "theme", "customColor": "#123456",
        "size": 24, "imagePath": "", "imageHotspot": "0,0",
        "leftHanded": False, "animated": True, "active": True,
        "restore": {"theme": "Adwaita", "size": 24},
        "junk": "dropped",
    })
    loaded = cursorgen.load_settings()
    assert loaded["style"] == "skeleton"
    assert loaded["active"] is True and loaded["animated"] is True
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


def test_missing_image_fails_cleanly(tmp_path, capsys):
    code = cursorgen.main([
        "apply", "--style", "image", "--image", str(tmp_path / "nope.png"),
        "--color", "#6b8a69", "--out", str(tmp_path),
        "--no-apply", "--no-save",
    ])
    assert code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and "not found" in report["error"]
