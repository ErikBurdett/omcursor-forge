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
    "HOURGLASS": cursorgen.HOURGLASS,
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
        images.append({"nominal": nominal, "w": w, "h": h,
                       "xhot": xhot, "yhot": yhot, "pixels": pixels})
    return images


def test_grids_are_well_formed():
    for name, grid in ALL_GRIDS.items():
        assert len(grid) == cursorgen.BASE, name
        for row in grid:
            assert len(row) == cursorgen.BASE, name
        for style in ("classic", "skeleton"):
            cursorgen.render_grid(grid, cursorgen.palette(style, (107, 138, 105)))


def test_hotspots_inside_canvas():
    for shape, variants in cursorgen.SHAPES.items():
        for style, (grid, xhot, yhot) in variants.items():
            assert 0 <= xhot < cursorgen.BASE, (shape, style)
            assert 0 <= yhot < cursorgen.BASE, (shape, style)


def test_parse_color():
    assert cursorgen.parse_color("#6b8a69") == (0x6B, 0x8A, 0x69)
    for bad in ("6b8a69", "#6b8a6", "#6b8a6zz", "", "#12345g"):
        with pytest.raises(ValueError):
            cursorgen.parse_color(bad)


def test_alias_map_covers_every_shape():
    assert set(cursorgen.ALIASES) == set(cursorgen.SHAPES)
    for shape, names in cursorgen.ALIASES.items():
        assert shape in names


def build(tmp_path, style, color="#6b8a69", image=None):
    code = cursorgen.main([
        "apply", "--style", style, "--color", color,
        "--out", str(tmp_path), "--no-apply", "--no-save",
    ] + (["--image", str(image)] if image else []))
    assert code == 0
    return tmp_path / cursorgen.THEME_NAME


@pytest.mark.parametrize("style", ["classic", "skeleton"])
def test_theme_builds_valid_xcursor_files(tmp_path, style):
    theme = build(tmp_path, style)
    index = (theme / "index.theme").read_text()
    assert "Inherits=Adwaita" in index

    for shape, names in cursorgen.ALIASES.items():
        for name in names:
            path = theme / "cursors" / name
            assert path.is_file(), f"{style}: missing cursor {name}"
            images = parse_xcursor(path.read_bytes())
            assert [img["nominal"] for img in images] == list(cursorgen.VALID_SIZES)
            grid_style = "skeleton" if style == "skeleton" else "classic"
            _, xhot, yhot = cursorgen.SHAPES[shape][grid_style]
            for img, factor in zip(images, cursorgen.SCALES):
                assert img["w"] == img["h"] == cursorgen.BASE * factor
                assert (img["xhot"], img["yhot"]) == (xhot * factor, yhot * factor)


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
    for name in ("current.png", "classic.png", "skeleton.png"):
        data = (theme / "previews" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", name
        width, height = struct.unpack_from(">II", data, 16)
        assert width == height == cursorgen.BASE


def test_no_save_leaves_config_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    build(tmp_path, "classic")
    assert not (tmp_path / "config").exists()


def test_settings_roundtrip_whitelists_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    cursorgen.save_settings({
        "style": "skeleton", "colorMode": "theme", "customColor": "#123456",
        "size": 24, "imagePath": "", "active": True,
        "restore": {"theme": "Adwaita", "size": 24},
        "junk": "dropped",
    })
    loaded = cursorgen.load_settings()
    assert loaded["style"] == "skeleton"
    assert loaded["active"] is True
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


def test_missing_image_fails_cleanly(tmp_path, capsys):
    code = cursorgen.main([
        "apply", "--style", "image", "--image", str(tmp_path / "nope.png"),
        "--color", "#6b8a69", "--out", str(tmp_path),
        "--no-apply", "--no-save",
    ])
    assert code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and "not found" in report["error"]
