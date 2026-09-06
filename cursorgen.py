#!/usr/bin/env python3
"""Cursor Forge — generate and apply pixel-art XCursor themes for Omarchy.

Renders retro pixel-art cursor shapes (classic arrow, skeletal pointing hand,
or a user-supplied image), recolors them with a theme or custom color, writes
a standards-compliant XCursor theme to $XDG_DATA_HOME/icons/CursorForge, and
applies it live via `hyprctl setcursor` and GTK's gsettings.

Standard library only. The optional custom-image style shells out to
ImageMagick (`magick`) because decoding arbitrary PNGs is out of scope for a
plugin helper.

Subcommands:
  apply    generate the theme, apply it, persist settings
  reset    restore the cursor theme that was active before Cursor Forge
  preview  render an enlarged contact sheet PNG for art review (dev tool)

Exit codes: 0 ok, 2 invalid arguments, 3 generation failure.
A single-line JSON status report is printed on stdout for the shell service.
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

THEME_NAME = "CursorForge"
BASE = 24                # art is drawn on a 24x24 grid
SCALES = (1, 2, 3)       # emit nominal sizes 24, 48, 72
VALID_SIZES = tuple(BASE * s for s in SCALES)
STYLES = ("classic", "skeleton", "image")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

XCURSOR_IMAGE_TYPE = 0xFFFD0002

# ---------------------------------------------------------------------------
# Pixel art
#
# Grids are strings of BASE columns. Role characters:
#   .  transparent
#   #  outline (fixed near-black)
#   F  fill        H  highlight       S  shade      (derived from the color)
#   B  bone        L  bone highlight  b  bone shade (fixed ivory tones)
#   R  accent      (always the chosen color, even on the skeleton)
# In the skeleton style F/H/S resolve to bone tones so shared shapes render
# as bone; R is where the theme color shows through.
# ---------------------------------------------------------------------------

ARROW = [
    "........................",
    ".#......................",
    ".##.....................",
    ".#H#....................",
    ".#HF#...................",
    ".#HFF#..................",
    ".#HFFF#.................",
    ".#HFFFF#................",
    ".#HFFFFS#...............",
    ".#HFFFFFS#..............",
    ".#HFFFFFFS#.............",
    ".#HFFFFFFFS#............",
    ".#HFFFFFFFFS#...........",
    ".#HFFFFSSSSSS#..........",
    ".#HFFFFS######..........",
    ".#HFF#SFS#..............",
    ".#HF#.#FFS#.............",
    ".#F#..#FFS#.............",
    ".##....#FFS#............",
    ".#.....#FFS#............",
    "........#FS#............",
    ".........##.............",
    "........................",
    "........................",
]

HAND_CLASSIC = [
    "........##..............",
    ".......#HF#.............",
    ".......#HF#.............",
    ".......#HF#.............",
    ".......#HF##............",
    ".......#HF#F##..........",
    ".......#HF#FF##.........",
    ".......#HF#FFFF##.......",
    ".......#HF#FFFFFF#......",
    "..##...#HFFFFFFFFF#.....",
    ".#HF#..#HFFFFFFFFF#.....",
    ".#HFF#.#HFFFFFFFFS#.....",
    ".#HFF##HFFFFFFFFFS#.....",
    "..#HF#HFFFFFFFFFFS#.....",
    "..#HFFFFFFFFFFFFFS#.....",
    "...#HFFFFFFFFFFFFS#.....",
    "...#HFFFFFFFFFFFS#......",
    "....#HFFFFFFFFFFS#......",
    "....#HFFFFFFFFFS#.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "........................",
    "........................",
    "........................",
]

# Authored to the Theandril pixel-art style standard: light from the
# upper-left (L highlights lead every bone's left edge), restrained
# highlights over deep readable shadows, and selective warm local-color
# outlines — joints are drawn with the deep bone shade (d), not black gaps.
HAND_SKELETON = [
    "........##..............",
    ".......#LB#.............",
    ".......#LB#.............",
    ".......#Lb#.............",
    ".......#dd#.............",
    ".......#LB#.............",
    ".......#LB#.............",
    ".......#Lb#.............",
    ".......#dd#.............",
    ".......#RR#.............",
    ".......#LB#.##..##......",
    ".......#LB##LB##LB#.....",
    ".......#LB##Bd##Bd#.....",
    "......#LBBBBBbBBBd#.....",
    "....###LBBbBBbBBbd#.....",
    "...#LB#LBBbBBbBBbd#.....",
    "..#LB##LBBBBBBBBd#......",
    "...##..#LBBBBBBd#.......",
    ".......#dddddddd#.......",
    ".......#LB#.#LB#........",
    ".......#Lb#.#Lb#........",
    "........##...##.........",
    "........................",
    "........................",
]

TEXT_BEAM = [
    "........................",
    "........................",
    "........................",
    "......##..##............",
    ".....#HF##FS#...........",
    "......#HFFS#............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    ".......#FS#.............",
    "......#HFFS#............",
    ".....#HF##FS#...........",
    "......##..##............",
    "........................",
    "........................",
    "........................",
]

HOURGLASS = [
    "........................",
    "........................",
    ".....############.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "......#........#........",
    "......#FFFFFFFF#........",
    ".......#FFFFFF#.........",
    "........#FFFF#..........",
    ".........#FF#...........",
    ".........#FF#...........",
    "........#.FF.#..........",
    ".......#..FF..#.........",
    "......#...FF...#........",
    "......#..FFFF..#........",
    "......#.FFFFFF.#........",
    ".....############.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

# shape -> (grid per style, hotspot x, hotspot y) at BASE scale
SHAPES = {
    "default": {"classic": (ARROW, 1, 1), "skeleton": (HAND_SKELETON, 9, 0)},
    "pointer": {"classic": (HAND_CLASSIC, 8, 0), "skeleton": (HAND_SKELETON, 9, 0)},
    "text": {"classic": (TEXT_BEAM, 8, 12), "skeleton": (TEXT_BEAM, 8, 12)},
    "wait": {"classic": (HOURGLASS, 10, 10), "skeleton": (HOURGLASS, 10, 10)},
}

# Every name each shape is installed under. Shapes not listed here fall back
# to the theme named in index.theme's Inherits line.
ALIASES = {
    "default": ["default", "left_ptr", "arrow", "top_left_arrow"],
    "pointer": ["pointer", "hand1", "hand2", "pointing_hand"],
    "text": ["text", "xterm", "ibeam"],
    "wait": ["wait", "watch", "progress", "left_ptr_watch"],
}

OUTLINE_RGB = (18, 14, 10)
# Bone ramp, light to deep. Warm ivory per the weathered-material standard.
BONE = {"L": (247, 242, 226), "B": (226, 214, 186), "b": (183, 166, 131),
        "d": (122, 104, 74)}
BONE_OUTLINE_RGB = (46, 34, 22)  # warm local-color outline, not sticker black


def parse_color(value):
    if not COLOR_RE.match(value or ""):
        raise ValueError(f"invalid color {value!r}; expected #RRGGBB")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def lighten(rgb, f):
    return tuple(min(255, int(round(c + (255 - c) * f))) for c in rgb)


def darken(rgb, f):
    return tuple(max(0, int(round(c * (1 - f)))) for c in rgb)


def palette(style, rgb):
    """Resolve role characters to RGBA tuples for one style + color."""
    roles = {
        ".": (0, 0, 0, 0),
        "R": (*rgb, 255),
        "B": (*BONE["B"], 255),
        "L": (*BONE["L"], 255),
        "b": (*BONE["b"], 255),
        "d": (*BONE["d"], 255),
    }
    if style == "skeleton":
        roles.update({
            "#": (*BONE_OUTLINE_RGB, 255),
            "F": (*BONE["B"], 255),
            "H": (*BONE["L"], 255),
            "S": (*BONE["b"], 255),
        })
    else:
        roles.update({
            "#": (*OUTLINE_RGB, 255),
            "F": (*rgb, 255),
            "H": (*lighten(rgb, 0.40), 255),
            "S": (*darken(rgb, 0.35), 255),
            "d": (*darken(rgb, 0.55), 255),
        })
    return roles


def render_grid(grid, roles):
    """Grid of role chars -> flat list of RGBA tuples, BASE x BASE."""
    if len(grid) != BASE:
        raise ValueError(f"grid has {len(grid)} rows, expected {BASE}")
    pixels = []
    for y, row in enumerate(grid):
        if len(row) != BASE:
            raise ValueError(f"grid row {y} has {len(row)} columns, expected {BASE}")
        for ch in row:
            if ch not in roles:
                raise ValueError(f"unknown role character {ch!r} in grid row {y}")
            pixels.append(roles[ch])
    return pixels


def scale_pixels(pixels, width, height, factor):
    """Integer nearest-neighbor upscale, preserving hard pixel edges."""
    if factor == 1:
        return pixels
    out = []
    for y in range(height * factor):
        row = pixels[(y // factor) * width:(y // factor + 1) * width]
        for x in range(width * factor):
            out.append(row[x // factor])
    return out


# ---------------------------------------------------------------------------
# XCursor + PNG encoders
# ---------------------------------------------------------------------------

def xcursor_bytes(images):
    """images: list of (nominal, w, h, xhot, yhot, rgba_pixels). -> file bytes.

    Pixels are stored premultiplied ARGB little-endian, as libXcursor expects.
    """
    ntoc = len(images)
    header_size = 16 + ntoc * 12
    toc = b""
    chunks = b""
    position = header_size
    for nominal, w, h, xhot, yhot, pixels in images:
        body = bytearray(struct.pack("<9I", 36, XCURSOR_IMAGE_TYPE, nominal, 1,
                                     w, h, xhot, yhot, 0))
        for r, g, b, a in pixels:
            body += struct.pack("<I", (a << 24)
                                | ((r * a // 255) << 16)
                                | ((g * a // 255) << 8)
                                | (b * a // 255))
        toc += struct.pack("<III", XCURSOR_IMAGE_TYPE, nominal, position)
        chunks += body
        position += len(body)
    return b"Xcur" + struct.pack("<III", 16, 0x10000, ntoc) + toc + chunks


def png_bytes(pixels, width, height):
    """Straight-alpha RGBA pixel list -> PNG file bytes."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        for r, g, b, a in pixels[y * width:(y + 1) * width]:
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        with contextlib_suppress():
            os.unlink(tmp)
        raise


class contextlib_suppress:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return True


# ---------------------------------------------------------------------------
# Custom image style (needs ImageMagick)
# ---------------------------------------------------------------------------

def load_image_pixels(image_path, size):
    """Decode + fit an arbitrary image to size x size RGBA via ImageMagick."""
    magick = shutil.which("magick")
    if not magick:
        raise RuntimeError("the image style needs ImageMagick (`magick`) installed")
    result = subprocess.run(
        [magick, str(image_path), "-background", "none", "-resize",
         f"{size}x{size}", "-gravity", "northwest", "-extent", f"{size}x{size}",
         "-depth", "8", "rgba:-"],
        capture_output=True, timeout=30)
    if result.returncode != 0 or len(result.stdout) != size * size * 4:
        detail = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ImageMagick could not render {image_path}: {detail}")
    data = result.stdout
    return [tuple(data[i:i + 4]) for i in range(0, len(data), 4)]


# ---------------------------------------------------------------------------
# Theme build
# ---------------------------------------------------------------------------

def data_home():
    return Path(os.environ.get("XDG_DATA_HOME")
                or Path.home() / ".local" / "share")


def config_path():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "cursorforge" / "settings.json"


def build_theme(out_dir, style, rgb, image_path=None):
    """Write the full XCursor theme + previews. Returns the theme directory."""
    theme_dir = Path(out_dir) / THEME_NAME
    cursors_dir = theme_dir / "cursors"
    cursors_dir.mkdir(parents=True, exist_ok=True)

    grid_style = "skeleton" if style == "skeleton" else "classic"
    roles = palette(grid_style, rgb)

    image_base = None
    if style == "image":
        if not image_path or not Path(image_path).is_file():
            raise RuntimeError(f"image file not found: {image_path!r}")

    for shape, variants in SHAPES.items():
        grid, xhot, yhot = variants[grid_style]
        base_pixels = render_grid(grid, roles)
        if style == "image" and shape in ("default", "pointer"):
            images = []
            for factor in SCALES:
                size = BASE * factor
                images.append((size, size, size, 0, 0,
                               load_image_pixels(image_path, size)))
            if shape == "default":
                image_base = images[0][5]
        else:
            images = [(BASE * f, BASE * f, BASE * f, xhot * f, yhot * f,
                       scale_pixels(base_pixels, BASE, BASE, f))
                      for f in SCALES]
        data = xcursor_bytes(images)
        for name in ALIASES[shape]:
            atomic_write(cursors_dir / name, data)

    atomic_write(theme_dir / "index.theme",
                 ("[Icon Theme]\n"
                  f"Name={THEME_NAME}\n"
                  "Comment=Pixel-art cursor theme generated by Cursor Forge\n"
                  "Inherits=Adwaita\n").encode())

    # Previews for the shell UI: both styles at the current color, plus the
    # active style as current.png (the bar widget's icon).
    previews = theme_dir / "previews"
    for preview_style, grid in (("classic", ARROW), ("skeleton", HAND_SKELETON)):
        pixels = render_grid(grid, palette(preview_style, rgb))
        atomic_write(previews / f"{preview_style}.png",
                     png_bytes(pixels, BASE, BASE))
    if style == "image":
        current = image_base
    else:
        grid, _, _ = SHAPES["default"][grid_style]
        current = render_grid(grid, roles)
    atomic_write(previews / "current.png", png_bytes(current, BASE, BASE))
    return theme_dir


# ---------------------------------------------------------------------------
# Applying + settings
# ---------------------------------------------------------------------------

def run_quiet(argv, timeout=10):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout)
        return result.returncode == 0, result.stdout.decode(errors="replace").strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)


def read_gtk_cursor():
    gsettings = shutil.which("gsettings")
    if not gsettings:
        return None, None
    ok_theme, theme = run_quiet([gsettings, "get",
                                 "org.gnome.desktop.interface", "cursor-theme"])
    ok_size, size = run_quiet([gsettings, "get",
                               "org.gnome.desktop.interface", "cursor-size"])
    theme = theme.strip("'") if ok_theme else None
    try:
        size = int(size) if ok_size else None
    except ValueError:
        size = None
    return theme, size


def apply_cursor(theme, size):
    """Point GTK and Hyprland at the theme. Returns list of warnings."""
    warnings = []
    gsettings = shutil.which("gsettings")
    if gsettings:
        current, _ = read_gtk_cursor()
        # gsettings only notifies on change; bounce through the inherited
        # theme when re-applying under the same name so live GTK apps reload.
        if current == theme:
            run_quiet([gsettings, "set", "org.gnome.desktop.interface",
                       "cursor-theme", "Adwaita"])
        for key, value in (("cursor-theme", theme), ("cursor-size", str(size))):
            ok, out = run_quiet([gsettings, "set",
                                 "org.gnome.desktop.interface", key, value])
            if not ok:
                warnings.append(f"gsettings {key}: {out}")
    else:
        warnings.append("gsettings not found; GTK apps keep their cursor theme")
    hyprctl = shutil.which("hyprctl")
    if hyprctl:
        ok, out = run_quiet([hyprctl, "setcursor", theme, str(size)])
        if not ok or out.lower().startswith("invalid"):
            warnings.append(f"hyprctl setcursor: {out}")
    else:
        warnings.append("hyprctl not found; compositor cursor not updated")
    return warnings


def load_settings():
    try:
        with open(config_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    allowed = ("style", "colorMode", "customColor", "size", "imagePath",
               "active", "restore")
    clean = {key: settings[key] for key in allowed if key in settings}
    atomic_write(config_path(),
                 (json.dumps(clean, indent=2) + "\n").encode())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_apply(args):
    rgb = parse_color(args.color)
    if args.size not in VALID_SIZES:
        raise ValueError(f"size must be one of {VALID_SIZES}")
    theme_dir = build_theme(args.out or data_home() / "icons",
                            args.style, rgb, args.image)

    settings = load_settings()
    warnings = []
    if not args.no_apply:
        if "restore" not in settings:
            prev_theme, prev_size = read_gtk_cursor()
            if prev_theme and prev_theme != THEME_NAME:
                settings["restore"] = {"theme": prev_theme,
                                       "size": prev_size or 24}
        warnings = apply_cursor(THEME_NAME, args.size)

    if not args.no_save:
        settings.update({
            "style": args.style,
            "colorMode": args.color_mode,
            "customColor": args.custom_color or args.color,
            "size": args.size,
            "imagePath": args.image or "",
            "active": not args.no_apply,
        })
        save_settings(settings)

    return {"ok": True, "themeDir": str(theme_dir), "applied": not args.no_apply,
            "warnings": warnings}


def cmd_reset(args):
    settings = load_settings()
    restore = settings.get("restore") or {}
    theme = str(restore.get("theme") or "default")
    try:
        size = int(restore.get("size") or 24)
    except (TypeError, ValueError):
        size = 24
    warnings = apply_cursor(theme, size)
    settings.pop("restore", None)
    settings["active"] = False
    save_settings(settings)
    return {"ok": True, "restored": {"theme": theme, "size": size},
            "warnings": warnings}


def cmd_preview(args):
    """Dev tool: render every shape of a style, enlarged, into one PNG."""
    rgb = parse_color(args.color)
    grid_style = "skeleton" if args.style == "skeleton" else "classic"
    roles = palette(grid_style, rgb)
    factor = args.scale
    gap = 4 * factor
    tile = BASE * factor
    shapes = list(SHAPES)
    width = len(shapes) * tile + (len(shapes) + 1) * gap
    height = tile + 2 * gap
    background = (40, 40, 48, 255) if args.dark else (200, 200, 200, 255)
    canvas = [background] * (width * height)
    for index, shape in enumerate(shapes):
        grid, _, _ = SHAPES[shape][grid_style]
        pixels = scale_pixels(render_grid(grid, roles), BASE, BASE, factor)
        ox = gap + index * (tile + gap)
        for y in range(tile):
            for x in range(tile):
                pixel = pixels[y * tile + x]
                if pixel[3] > 0:
                    canvas[(gap + y) * width + ox + x] = pixel
    atomic_write(args.out, png_bytes(canvas, width, height))
    return {"ok": True, "out": args.out}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    apply_p = sub.add_parser("apply", help="generate, apply, and persist")
    apply_p.add_argument("--style", choices=STYLES, default="classic")
    apply_p.add_argument("--color", default="#7aa2f7",
                         help="#RRGGBB fill/accent color")
    apply_p.add_argument("--color-mode", choices=("theme", "custom"),
                         default="theme", help="persisted color mode")
    apply_p.add_argument("--custom-color", default="",
                         help="persisted custom color (defaults to --color)")
    apply_p.add_argument("--size", type=int, default=BASE)
    apply_p.add_argument("--image", default="",
                         help="image file for the image style")
    apply_p.add_argument("--out", default="",
                         help="icons directory override (for tests)")
    apply_p.add_argument("--no-apply", action="store_true")
    apply_p.add_argument("--no-save", action="store_true")

    sub.add_parser("reset", help="restore the previous cursor theme")

    preview_p = sub.add_parser("preview", help="render an art contact sheet")
    preview_p.add_argument("--style", choices=("classic", "skeleton"),
                           default="classic")
    preview_p.add_argument("--color", default="#7aa2f7")
    preview_p.add_argument("--scale", type=int, default=8)
    preview_p.add_argument("--dark", action="store_true")
    preview_p.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    try:
        result = {"apply": cmd_apply, "reset": cmd_reset,
                  "preview": cmd_preview}[args.command](args)
    except ValueError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 2
    except RuntimeError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 3
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
