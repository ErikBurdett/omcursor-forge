#!/usr/bin/env python3
"""OmCursor Forge — generate and apply pixel-art cursor themes for Omarchy.

Renders retro pixel-art cursor shapes (classic arrow, skeletal pointing hand,
or a user-supplied image), recolors them with a theme or custom color, writes
a standards-compliant XCursor theme — plus a native Hyprcursor theme when
hyprcursor-util is available — to $XDG_DATA_HOME/icons/CursorForge, and
applies it live via `hyprctl setcursor` and GTK's gsettings.

Standard library only. The optional custom-image style shells out to
ImageMagick (`magick`); the optional Hyprcursor output shells out to
`hyprcursor-util`. Both degrade gracefully when missing.

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

THEME_NAME = "OmCursorForge"
BASE = 24                # art is drawn on a 24x24 grid
SCALES = (1, 2, 3, 4)    # emit nominal sizes 24, 48, 72, 96 (96 for HiDPI:
                         # Hyprland requests size x ceil(scale) from libXcursor)
VALID_SIZES = tuple(BASE * s for s in SCALES)
STYLES = ("classic", "lich", "sword", "wand", "image")
ART_STYLES = ("classic", "lich", "sword", "wand")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
HOTSPOT_RE = re.compile(r"^\d{1,2},\d{1,2}$")

XCURSOR_IMAGE_TYPE = 0xFFFD0002

# ---------------------------------------------------------------------------
# Pixel art
#
# Grids are strings of BASE columns. Role characters:
#   .  transparent
#   #  outline (near-black; warm bone-brown in the skeleton style)
#   F  fill        H  highlight       S  shade      (derived from the color)
#   B  bone        L  bone highlight  b  bone shade (fixed ivory tones)
#   d  deep shade  R  accent          (R is always the chosen color)
# In the skeleton style F/H/S resolve to bone tones so shared shapes render
# as bone; R is where the theme color shows through.
#
# Authored to the Theandril pixel-art style standard: light from the
# upper-left, restrained highlights over deep readable shadows, selective
# warm local-color outlines, joints drawn with the deep shade rather than
# black gaps.
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

# Animated hourglass: sand drains over three frames, then the loop restart
# reads as the flip. Frame delays live in the shape table.
HOURGLASS_FULL = [
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

HOURGLASS_HALF = [
    "........................",
    "........................",
    ".....############.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "......#........#........",
    "......#........#........",
    ".......#FFFFFF#.........",
    "........#FFFF#..........",
    ".........#FF#...........",
    ".........#FF#...........",
    "........#.FF.#..........",
    ".......#.FFFF.#.........",
    "......#..FFFF..#........",
    "......#.FFFFFF.#........",
    "......#FFFFFFFF#........",
    ".....############.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

HOURGLASS_DRAINED = [
    "........................",
    "........................",
    ".....############.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "......#........#........",
    "......#........#........",
    ".......#......#.........",
    "........#FFFF#..........",
    ".........#FF#...........",
    ".........#..#...........",
    "........#FFFF#..........",
    ".......#FFFFFF#.........",
    "......#FFFFFFFF#........",
    "......#FFFFFFFF#........",
    "......#FFFFFFFF#........",
    ".....############.......",
    ".....#SSSSSSSSSS#.......",
    ".....############.......",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

# Slim double-ended horizontal resize arrow; the vertical one is its
# transpose and the diagonals mirror each other.
RESIZE_EW = [
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    ".....#............#.....",
    "....##............##....",
    "...#F##############F#...",
    "..#FFFFFFFFFFFFFFFFFF#..",
    "...#F##############F#...",
    "....##............##....",
    ".....#............#.....",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

RESIZE_NWSE = [
    "........................",
    ".#####..................",
    ".#FFF#..................",
    ".#FF#...................",
    ".#F#FF#.................",
    ".##.#FF#................",
    ".....#FF#...............",
    "......#FF#..............",
    ".......#FF#.............",
    "........#FF#............",
    ".........#FF#...........",
    "..........#FF#..........",
    "...........#FF#.........",
    "............#FF#........",
    ".............#FF#.......",
    "..............#FF#......",
    "...............#FF#.....",
    "................#FF#....",
    "................#FF#.##.",
    ".................#FF#F#.",
    "...................#FF#.",
    "..................#FFF#.",
    "..................#####.",
    "........................",
]

# One arm of the four-way move cursor; the full fleur is this merged with
# its transpose. The crosshair works the same way from a plain bar.
FLEUR_ARM = [
    "........................",
    "..........###...........",
    ".........#FFF#..........",
    "........#FFFFF#.........",
    "........###F###.........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "........###F###.........",
    "........#FFFFF#.........",
    ".........#FFF#..........",
    "..........###...........",
    "........................",
    "........................",
]

CROSS_BAR = [
    "........................",
    "........................",
    "........................",
    "..........###...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........#F#...........",
    "..........###...........",
    "........................",
    "........................",
    "........................",
    "........................",
]

GRAB_HAND = [
    "........................",
    "........................",
    "........................",
    "........................",
    "....##.##.##.##.........",
    "...#FF#FF#FF#FF#........",
    "...#FF#FF#FF#FF#........",
    "...#FFFFFFFFFFF#........",
    "..##FFFFFFFFFFF#........",
    ".#FFFFFFFFFFFFF#........",
    ".#FFFFFFFFFFFFF#........",
    "..#FFFFFFFFFFFF#........",
    "...#FFFFFFFFFF#.........",
    "...#FFFFFFFFFF#.........",
    "....#FFFFFFFF#..........",
    "....##########..........",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

GRABBING_HAND = [
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "....##.##.##.##.........",
    "...#FF#FF#FF#FF#........",
    "..##FF#FF#FF#FF#........",
    ".#FFFFFFFFFFFFF#........",
    ".#FFFFFFFFFFFFF#........",
    "..#FFFFFFFFFFF#.........",
    "...#FFFFFFFFF#..........",
    "...###########..........",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

MINI_HOURGLASS = [
    "########",
    "#SSSSSS#",
    ".#FFFF#.",
    "..#FF#..",
    "...##...",
    "..#..#..",
    ".#.FF.#.",
    ".#FFFF#.",
    "#SSSSSS#",
    "########",
]

MINI_HOURGLASS_DRAINED = [
    "########",
    "#SSSSSS#",
    ".#....#.",
    "..#FF#..",
    "...##...",
    "..#FF#..",
    ".#FFFF#.",
    ".#FFFF#.",
    "#SSSSSS#",
    "########",
]

# HAND_SKELETON is internal source art: the lich style reuses its hand rows
# and the tests exercise it, but it is not exposed as a style of its own.

# The lich variant: the same hand emerging from a wizard-robe sleeve that
# droops off the wrist in tattered points. Cloth roles: C dark, c fold.
HAND_LICH = HAND_SKELETON[:14] + [
    "......#LBBbBBbBBbd#.....",
    "......#LBBbBBbBBbd#.....",
    "...#RRdRRRRdRRRRdR#.....",
    "...#CcCCCcCCCCcCCC#.....",
    "...#CcCCCcCCCCcCCC#.....",
    "...#CcCCCcCCCC####......",
    "..#CcC#.#CcC#...........",
    "..#Cc#..#Cc#............",
    "..#C#....##.............",
    "...#....................",
]
HAND_LICH_GLINT = [row.replace("#RR#", "#WR#") for row in HAND_LICH]
LICH_HAND_FRAMES = [(HAND_LICH, 1200), (HAND_LICH_GLINT, 140),
                    (HAND_LICH, 140), (HAND_LICH_GLINT, 140)]
HAND_LICH_POINT_A = [row.replace("#LB#", "#WB#") if at == 1 else row
                     for at, row in enumerate(HAND_LICH_GLINT)]
LICH_POINT_FRAMES = [(HAND_LICH_POINT_A, 300), (HAND_LICH_GLINT, 300)]

HIRES = 48  # the 48px nominal gets native art instead of a 2x upscale


def make_hand_48(base, glint=False):
    """Native 48x48 hand art from a proven 24px silhouette.

    The base grid is doubled, then refined for the larger canvas: convex
    outline corners are beveled away so curves read as curves, the ring
    gains a gem (which sparkles on the glint frame), the fingertip gets a
    nail highlight, and the palm a couple of hairline cracks.
    """
    grid = [[ch for ch in row for _ in (0, 1)]
            for row in base for _ in (0, 1)]

    def at(x, y):
        if 0 <= x < HIRES and 0 <= y < HIRES:
            return grid[y][x]
        return "."

    # Bevel pass: cut an outline pixel sitting on a convex stair corner —
    # two orthogonally transparent sides while the two remaining orthogonal
    # neighbors are outline, so no interior is ever exposed.
    cuts = []
    for y in range(HIRES):
        for x in range(HIRES):
            if grid[y][x] != "#":
                continue
            sides = {(0, -1): at(x, y - 1), (0, 1): at(x, y + 1),
                     (-1, 0): at(x - 1, y), (1, 0): at(x + 1, y)}
            transparent = [d for d, ch in sides.items() if ch == "."]
            outline = [d for d, ch in sides.items() if ch == "#"]
            if len(transparent) == 2 and len(outline) == 2:
                dx = transparent[0][0] + transparent[1][0]
                dy = transparent[0][1] + transparent[1][1]
                if dx != 0 and dy != 0:  # a true corner, not a strait
                    cuts.append((x, y))
    for x, y in cuts:
        grid[y][x] = "."

    # Ring gem: the doubled ring is a 2x2 R block per original pixel; set a
    # bright gem that swaps position on the glint frame. The count ceiling
    # keeps wide accent bands (the lich cuff braid) from matching.
    ring_rows = [y for y in range(HIRES)
                 if 4 <= grid[y].count("R") <= 8]
    if ring_rows:
        y = ring_rows[0]
        first = grid[y].index("R")
        gem, spark = (first + 1, first + 3) if not glint else (first + 2, first)
        grid[y][gem] = "W"
        if glint:
            grid[y][spark] = "W"
            grid[ring_rows[-1]][first + 1] = "W"

    # Nail highlight at the fingertip's lit corner.
    for y in (2, 3):
        for x in range(HIRES):
            if grid[y][x] == "L":
                grid[y][x] = "W" if y == 2 else "L"
                break

    # Hairline cracks across the back of the hand.
    for x, y in ((21, 31), (22, 32), (23, 32), (30, 34), (31, 35)):
        if grid[y][x] == "B":
            grid[y][x] = "d"

    return ["".join(line) for line in grid]


HAND_LICH_48 = make_hand_48(HAND_LICH, False)
HAND_LICH_48_GLINT = make_hand_48(HAND_LICH, True)
LICH_HAND_48_FRAMES = [(HAND_LICH_48, 1200), (HAND_LICH_48_GLINT, 140),
                       (HAND_LICH_48, 140), (HAND_LICH_48_GLINT, 140)]
LICH_HIRES = {"frames": LICH_HAND_48_FRAMES, "hotspot": (18, 0)}

LICH_POINT_48_FRAMES = [(make_hand_48(HAND_LICH_POINT_A), 300),
                        (make_hand_48(HAND_LICH_GLINT), 300)]
LICH_POINT_HIRES = {"frames": LICH_POINT_48_FRAMES, "hotspot": (18, 0)}

# A blade pointing to the hotspot, guard and pommel in the accent color.
SWORD = [
    "##......................",
    "#H#.....................",
    "#HF#....................",
    ".#HF#...................",
    "..#HF#..................",
    "...#HF#.................",
    "....#HF#................",
    ".....#HF#...............",
    "......#HF#....##........",
    ".......#HF#..#LB#.......",
    "........#HF#LB#.........",
    ".........#HLB#..........",
    ".........#LB#...........",
    "........#LB##bb#........",
    "........##...#bb#.......",
    "..............#bb#......",
    "...............#RR#.....",
    "...............#RR#.....",
    "................##......",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

# A wand whose starred tip is the hotspot; the star glints on a slow loop.
WAND = [
    "........................",
    "....#.....#F............",
    "...#R#..................",
    "..#RWR#.................",
    ".#RWWWR#................",
    "..#RWR#.................",
    ".F.#R#..................",
    "....#.#bd#..............",
    ".......#bd#.............",
    "........#bd#............",
    ".........#bd#...........",
    "..........#bd#..........",
    "...........#bd#.........",
    "............#bd#........",
    ".............#bd#.......",
    "..............#bd#......",
    "...............#bd#.....",
    "................#bd#....",
    ".................#bd#...",
    "..................#bd#..",
    "...................###..",
    "........................",
    "........................",
    "........................",
]

WAND_GLINT = [row.replace("#RWWWR#", "#WRRRW#").replace("#RWR#", "#WRW#")
              .replace("#R#", "#W#") for row in WAND]
SWORD_GLINT = [row.replace("#HF#", "#WF#") if index in (2, 3, 4)
               else row for index, row in enumerate(SWORD)]
SWORD_FRAMES = [(SWORD, 1400), (SWORD_GLINT, 140), (SWORD, 140),
                (SWORD_GLINT, 140)]
WAND_FRAMES = [(WAND, 650), (WAND_GLINT, 300)]


def mirror_grid(grid):
    return [row[::-1] for row in grid]


def shift_grid(grid, dx, dy):
    """Translate a grid inside its canvas, filling with transparency."""
    size = len(grid)
    blank = "." * size
    rows = [blank] * dy + list(grid[:size - dy]) if dy >= 0 \
        else list(grid[-dy:]) + [blank] * -dy
    out = []
    for row in rows:
        if dx >= 0:
            out.append(("." * dx + row)[:size])
        else:
            out.append((row[-dx:] + "." * -dx)[:size])
    return out


def bend_finger(hand, lift):
    """Retract the pointing finger's distal phalanx by `lift` rows.

    The hand's tip row is base[0], the distal phalanx base[1:4], the first
    joint base[4]. Bending compresses the distal segment downward while the
    rest of the hand stays planted, so the return frame reads as a tap that
    strikes exactly at the hotspot.
    """
    blank = "." * len(hand[0])
    if lift <= 0:
        return list(hand)
    if lift == 1:
        return [blank, hand[0], hand[1], hand[3]] + list(hand[4:])
    return [blank, blank, hand[0], hand[3]] + list(hand[4:])


def transpose_grid(grid):
    return ["".join(grid[x][y] for x in range(len(grid))) for y in range(len(grid))]


def merge_grids(first, second):
    """Cell-wise union: fill beats outline beats transparent."""
    rank = {".": 0, "#": 1}
    merged = []
    for row_a, row_b in zip(first, second):
        row = ""
        for cell_a, cell_b in zip(row_a, row_b):
            row += cell_a if rank.get(cell_a, 2) >= rank.get(cell_b, 2) else cell_b
        merged.append(row)
    return merged


def compose_grid(base, patch, offset_x, offset_y):
    """Stamp a smaller grid onto a copy of `base` at the given offset."""
    rows = [list(row) for row in base]
    for y, patch_row in enumerate(patch):
        for x, cell in enumerate(patch_row):
            if cell != ".":
                rows[offset_y + y][offset_x + x] = cell
    return ["".join(row) for row in rows]


def make_not_allowed():
    """Ring with a NW-SE slash, generated so the circle stays round."""
    grid = []
    center = (BASE - 1) / 2
    for y in range(BASE):
        row = ""
        for x in range(BASE):
            radius = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
            on_ring = 7.4 <= radius <= 9.2
            on_slash = abs(x - y) <= 1.1 and radius <= 8.8
            near_ring = 6.4 <= radius <= 10.2
            near_slash = abs(x - y) <= 2.2 and radius <= 9.6
            if on_ring or on_slash:
                row += "F"
            elif near_ring or near_slash:
                row += "#"
            else:
                row += "."
        grid.append(row)
    return grid


RESIZE_NS = transpose_grid(RESIZE_EW)
RESIZE_NESW = mirror_grid(RESIZE_NWSE)
MOVE_FLEUR = merge_grids(FLEUR_ARM, transpose_grid(FLEUR_ARM))
CROSSHAIR = merge_grids(CROSS_BAR, transpose_grid(CROSS_BAR))
NOT_ALLOWED = make_not_allowed()
PROGRESS_ARROW = compose_grid(ARROW, MINI_HOURGLASS, 14, 12)
PROGRESS_ARROW_DRAINED = compose_grid(ARROW, MINI_HOURGLASS_DRAINED, 14, 12)

WAIT_FRAMES = [(HOURGLASS_FULL, 350), (HOURGLASS_HALF, 350),
               (HOURGLASS_DRAINED, 550)]
PROGRESS_FRAMES = [(PROGRESS_ARROW, 500), (PROGRESS_ARROW_DRAINED, 500)]

# ---------------------------------------------------------------------------
# Sprite motion: the cursor art itself moves. The hands periodically tap
# (finger retracts, then strikes back at the hotspot with a ring flash);
# sword and wand bob as if floating. Disabled by --no-motion, which falls
# back to the in-place glint sequences.
# ---------------------------------------------------------------------------


HAND_LICH_HALF_TAP = bend_finger(HAND_LICH, 1)
HAND_LICH_TAP = bend_finger(HAND_LICH_GLINT, 2)
LICH_MOTION_FRAMES = [(HAND_LICH, 1000), (HAND_LICH_HALF_TAP, 90),
                      (HAND_LICH_TAP, 170), (HAND_LICH_HALF_TAP, 90),
                      (HAND_LICH_GLINT, 150)]
LICH_MOTION_48 = [(make_hand_48(HAND_LICH), 1000),
                  (make_hand_48(HAND_LICH_HALF_TAP), 90),
                  (make_hand_48(HAND_LICH_TAP, True), 170),
                  (make_hand_48(HAND_LICH_HALF_TAP), 90),
                  (make_hand_48(HAND_LICH, True), 150)]

# Hover: rapid eager tapping with the charged fingertip.
LICH_POINT_MOTION = [(HAND_LICH_POINT_A, 260),
                     (bend_finger(HAND_LICH_POINT_A, 1), 130),
                     (HAND_LICH_GLINT, 260),
                     (bend_finger(HAND_LICH_POINT_A, 1), 130)]
LICH_POINT_MOTION_48 = [(make_hand_48(HAND_LICH_POINT_A), 260),
                        (make_hand_48(bend_finger(HAND_LICH_POINT_A, 1)), 130),
                        (make_hand_48(HAND_LICH, True), 260),
                        (make_hand_48(bend_finger(HAND_LICH_POINT_A, 1)), 130)]

SWORD_BOB = shift_grid(SWORD, 1, 1)
SWORD_MOTION_FRAMES = [(SWORD, 1000), (SWORD_BOB, 200), (SWORD_GLINT, 150),
                       (SWORD_BOB, 200)]
WAND_BOB = shift_grid(WAND, 0, 1)
WAND_MOTION_FRAMES = [(WAND, 550), (WAND_BOB, 300), (WAND_GLINT, 300),
                      (WAND_BOB, 300)]


def static(grid, xhot, yhot):
    return {"frames": [(grid, 0)], "hotspot": (xhot, yhot)}


# shape -> {style: spec}; shapes without a per-style entry share the classic
# grid, which the skeleton palette renders in bone tones.
SHAPES = {
    "default": {"classic": static(ARROW, 1, 1),
                "lich": {"frames": LICH_HAND_FRAMES, "hotspot": (9, 0),
                         "motion": LICH_MOTION_FRAMES,
                         "hires": dict(LICH_HIRES, motion=LICH_MOTION_48)},
                "sword": {"frames": SWORD_FRAMES, "hotspot": (1, 1),
                          "motion": SWORD_MOTION_FRAMES},
                "wand": {"frames": WAND_FRAMES, "hotspot": (4, 4),
                         "motion": WAND_MOTION_FRAMES}},
    "pointer": {"classic": static(HAND_CLASSIC, 8, 0),
                "lich": {"frames": LICH_POINT_FRAMES, "hotspot": (9, 0),
                         "motion": LICH_POINT_MOTION,
                         "hires": dict(LICH_POINT_HIRES,
                                       motion=LICH_POINT_MOTION_48)},
                "sword": {"frames": SWORD_FRAMES, "hotspot": (1, 1),
                          "motion": SWORD_MOTION_FRAMES},
                "wand": {"frames": WAND_FRAMES, "hotspot": (4, 4),
                         "motion": WAND_MOTION_FRAMES}},
    "text": {"classic": static(TEXT_BEAM, 8, 12)},
    "wait": {"classic": {"frames": WAIT_FRAMES, "hotspot": (10, 10)}},
    "progress": {"classic": {"frames": PROGRESS_FRAMES, "hotspot": (1, 1)}},
    "crosshair": {"classic": static(CROSSHAIR, 11, 11)},
    "ew-resize": {"classic": static(RESIZE_EW, 11, 11)},
    "ns-resize": {"classic": static(RESIZE_NS, 11, 11)},
    "nwse-resize": {"classic": static(RESIZE_NWSE, 11, 11)},
    "nesw-resize": {"classic": static(RESIZE_NESW, 12, 11)},
    "move": {"classic": static(MOVE_FLEUR, 11, 11)},
    "not-allowed": {"classic": static(NOT_ALLOWED, 11, 11)},
    "grab": {"classic": static(GRAB_HAND, 9, 10)},
    "grabbing": {"classic": static(GRABBING_HAND, 9, 11)},
}

# Shapes that depict a right hand or right-leaning tool; these are mirrored
# in left-handed mode. Diagonal resizes stay put — mirroring would swap them.
HANDED_SHAPES = {"default", "pointer", "grab", "grabbing", "progress"}

# Every name each shape is installed under (first entry is canonical).
# Shapes not listed fall back to the theme named in index.theme's Inherits.
ALIASES = {
    "default": ["default", "left_ptr", "arrow", "top_left_arrow"],
    "pointer": ["pointer", "hand1", "hand2", "pointing_hand"],
    "text": ["text", "xterm", "ibeam"],
    "wait": ["wait", "watch"],
    "progress": ["progress", "left_ptr_watch", "half-busy"],
    "crosshair": ["crosshair", "cross", "tcross"],
    "ew-resize": ["ew-resize", "sb_h_double_arrow", "size_hor", "col-resize",
                  "e-resize", "w-resize", "split_h"],
    "ns-resize": ["ns-resize", "sb_v_double_arrow", "size_ver", "row-resize",
                  "n-resize", "s-resize", "split_v"],
    "nwse-resize": ["nwse-resize", "size_fdiag", "nw-resize", "se-resize",
                    "bd_double_arrow"],
    "nesw-resize": ["nesw-resize", "size_bdiag", "ne-resize", "sw-resize",
                    "fd_double_arrow"],
    "move": ["move", "fleur", "all-scroll", "size_all"],
    "not-allowed": ["not-allowed", "crossed_circle", "forbidden", "no-drop",
                    "dnd-no-drop"],
    "grab": ["grab", "openhand"],
    "grabbing": ["grabbing", "closedhand", "dnd-move", "dnd-none"],
}

OUTLINE_RGB = (18, 14, 10)
# Bone ramp, light to deep. Warm ivory per the weathered-material standard.
BONE = {"L": (247, 242, 226), "B": (226, 214, 186), "b": (183, 166, 131),
        "d": (122, 104, 74)}
BONE_OUTLINE_RGB = (46, 34, 22)  # warm local-color outline, not sticker black
# Robe cloth for the lich sleeve: dark violet with a lighter fold, kept
# clearly above black so the sleeve still reads over dark apps.
CLOTH = {"C": (38, 28, 50), "c": (76, 60, 102)}


def parse_color(value):
    if not COLOR_RE.match(value or ""):
        raise ValueError(f"invalid color {value!r}; expected #RRGGBB")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def parse_hotspot(value):
    if not HOTSPOT_RE.match(value or ""):
        raise ValueError(f"invalid hotspot {value!r}; expected x,y")
    x, y = (int(part) for part in value.split(","))
    if x >= BASE or y >= BASE:
        raise ValueError(f"hotspot {value!r} outside the 0-{BASE - 1} range")
    return x, y


def lighten(rgb, f):
    return tuple(min(255, int(round(c + (255 - c) * f))) for c in rgb)


def darken(rgb, f):
    return tuple(max(0, int(round(c * (1 - f)))) for c in rgb)


def palette(style, rgb):
    """Resolve role characters to RGBA tuples for one style + color."""
    roles = {
        ".": (0, 0, 0, 0),
        "R": (*rgb, 255),
        "W": (255, 255, 248, 255),
        "B": (*BONE["B"], 255),
        "L": (*BONE["L"], 255),
        "b": (*BONE["b"], 255),
        "d": (*BONE["d"], 255),
        "C": (*CLOTH["C"], 255),
        "c": (*CLOTH["c"], 255),
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


def render_grid(grid, roles, size=BASE):
    """Grid of role chars -> flat list of RGBA tuples, size x size."""
    if len(grid) != size:
        raise ValueError(f"grid has {len(grid)} rows, expected {size}")
    pixels = []
    for y, row in enumerate(grid):
        if len(row) != size:
            raise ValueError(f"grid row {y} has {len(row)} columns, expected {size}")
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
    """images: (nominal, w, h, xhot, yhot, delay_ms, rgba_pixels) list.

    Multiple entries under the same nominal size are animation frames.
    Pixels are stored premultiplied ARGB little-endian, as libXcursor expects.
    """
    ntoc = len(images)
    header_size = 16 + ntoc * 12
    toc = b""
    chunks = b""
    position = header_size
    for nominal, w, h, xhot, yhot, delay, pixels in images:
        body = bytearray(struct.pack("<9I", 36, XCURSOR_IMAGE_TYPE, nominal, 1,
                                     w, h, xhot, yhot, delay))
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


def grid_style_for(style):
    return style if style in ART_STYLES else "classic"


def palette_style_for(style):
    return "skeleton" if style in ("skeleton", "lich") else "classic"


def resolve_frames(spec, size, mirrored, animated, motion):
    frames = spec.get("motion") if motion and animated else None
    if not frames:
        frames = spec["frames"]
    xhot, yhot = spec["hotspot"]
    if not animated:
        frames = [(frames[0][0], 0)]
    if mirrored:
        frames = [(mirror_grid(grid), delay) for grid, delay in frames]
        xhot = size - 1 - xhot
    return frames, xhot, yhot


def shape_spec(shape, grid_style, left_handed, animated=True, motion=True):
    variants = SHAPES[shape]
    spec = variants.get(grid_style) or variants["classic"]
    mirrored = left_handed and shape in HANDED_SHAPES
    return resolve_frames(spec, BASE, mirrored, animated, motion)


def shape_hires_spec(shape, grid_style, left_handed, animated=True,
                     motion=True):
    """Native art for the HIRES nominal, or None to upscale the base grid."""
    variants = SHAPES[shape]
    spec = variants.get(grid_style) or variants["classic"]
    hires = spec.get("hires")
    if not hires:
        return None
    mirrored = left_handed and shape in HANDED_SHAPES
    return resolve_frames(hires, HIRES, mirrored, animated, motion)


def shape_images(shape, style, roles, left_handed, image_path, image_hotspot,
                 animated=True, motion=True, speed=1.0):
    """Resolve one shape to [(nominal, w, h, xhot, yhot, delay, pixels)]."""
    grid_style = grid_style_for(style)
    if style == "image" and shape in ("default", "pointer"):
        hx, hy = image_hotspot
        return [(BASE * f, BASE * f, BASE * f, hx * f, hy * f, 0,
                 load_image_pixels(image_path, BASE * f)) for f in SCALES]
    frames, xhot, yhot = shape_spec(shape, grid_style, left_handed, animated,
                                    motion)
    hires = shape_hires_spec(shape, grid_style, left_handed, animated, motion)

    def paced(delay):
        return max(30, int(round(delay * speed))) if delay > 0 else 0

    images = []
    for factor in SCALES:
        nominal = BASE * factor
        # The hires art serves its own nominal and integer multiples of it.
        if hires and nominal % HIRES == 0:
            hi_factor = nominal // HIRES
            hi_frames, hi_xhot, hi_yhot = hires
            for grid, delay in hi_frames:
                images.append((nominal, nominal, nominal,
                               hi_xhot * hi_factor, hi_yhot * hi_factor,
                               paced(delay),
                               scale_pixels(render_grid(grid, roles, HIRES),
                                            HIRES, HIRES, hi_factor)))
            continue
        for grid, delay in frames:
            images.append((nominal, nominal, nominal,
                           xhot * factor, yhot * factor, paced(delay),
                           scale_pixels(render_grid(grid, roles),
                                        BASE, BASE, factor)))
    return images


def build_hyprcursor(theme_dir, shapes_images, animated=True):
    """Compile a native Hyprcursor theme into theme_dir, when possible.

    Only for fully static themes: Hyprland's cursor manager animates the
    XCursor lane solely when NO hyprcursor theme is loaded, and the
    hyprcursor lane renders a single frame in practice — so shipping
    hyprcursor files alongside an animated theme freezes every animation
    (verified empirically on Hyprland 0.56). With animation on, we remove
    the hyprcursor files and let the animated XCursor lane serve Hyprland.
    """
    if animated:
        manifest = Path(theme_dir) / "manifest.hl"
        hyprcursors = Path(theme_dir) / "hyprcursors"
        if manifest.exists():
            manifest.unlink()
        if hyprcursors.exists():
            shutil.rmtree(hyprcursors)
        return []
    util = shutil.which("hyprcursor-util")
    if not util:
        return []
    with tempfile.TemporaryDirectory(prefix="cursorforge-hc-") as tmp:
        work = Path(tmp) / "work"
        out = Path(tmp) / "out"
        work.mkdir()
        out.mkdir()
        (work / "manifest.hl").write_text(
            f"name = {THEME_NAME}\n"
            "description = Pixel-art cursor theme generated by OmCursor Forge\n"
            "version = 1.0\n"
            "cursors_directory = hyprcursors\n")
        for shape, images in shapes_images.items():
            names = ALIASES[shape]
            shape_dir = work / "hyprcursors" / names[0]
            shape_dir.mkdir(parents=True)
            meta = ["resize_algorithm = nearest"]
            first = images[0]
            meta.append(f"hotspot_x = {first[3] / first[1]:.4f}")
            meta.append(f"hotspot_y = {first[4] / first[2]:.4f}")
            for alias in names[1:]:
                meta.append(f"define_override = {alias}")
            for index, (nominal, w, h, _x, _y, delay, pixels) in enumerate(images):
                file_name = f"{nominal}_{index}.png"
                (shape_dir / file_name).write_bytes(png_bytes(pixels, w, h))
                if delay > 0:
                    meta.append(f"define_size = {nominal}, {file_name}, {delay}")
                else:
                    meta.append(f"define_size = {nominal}, {file_name}")
            (shape_dir / "meta.hl").write_text("\n".join(meta) + "\n")
        result = subprocess.run(
            [util, "--create", str(work), "--output", str(out)],
            capture_output=True, timeout=60)
        compiled = out / f"theme_{THEME_NAME}"
        if result.returncode != 0 or not (compiled / "manifest.hl").is_file():
            detail = (result.stderr or result.stdout).decode(errors="replace")
            return [f"hyprcursor-util failed; XCursor fallback stays active: "
                    f"{detail.strip()[:200]}"]
        target = Path(theme_dir) / "hyprcursors"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(compiled / "hyprcursors", target)
        shutil.copy2(compiled / "manifest.hl", Path(theme_dir) / "manifest.hl")
    return []


def build_theme(out_dir, style, rgb, image_path=None, left_handed=False,
                image_hotspot=(0, 0), animated=True, motion=True, speed=1.0,
                ripple_shape="diamond"):
    """Write the full cursor theme + previews. Returns (dir, warnings)."""
    theme_dir = Path(out_dir) / THEME_NAME
    cursors_dir = theme_dir / "cursors"
    cursors_dir.mkdir(parents=True, exist_ok=True)

    roles = palette(palette_style_for(style), rgb)

    if style == "image" and (not image_path or not Path(image_path).is_file()):
        raise RuntimeError(f"image file not found: {image_path!r}")

    shapes_images = {}
    for shape in SHAPES:
        images = shape_images(shape, style, roles, left_handed,
                              image_path, image_hotspot, animated, motion,
                              speed)
        shapes_images[shape] = images
        data = xcursor_bytes(images)
        for name in ALIASES[shape]:
            atomic_write(cursors_dir / name, data)

    atomic_write(theme_dir / "index.theme",
                 ("[Icon Theme]\n"
                  f"Name={THEME_NAME}\n"
                  "Comment=Pixel-art cursor theme generated by OmCursor Forge\n"
                  "Inherits=Adwaita\n").encode())

    warnings = build_hyprcursor(theme_dir, shapes_images, animated)

    # Previews for the shell UI: both styles at the current color, the active
    # style as current.png (the bar widget's icon), and a one-row gallery of
    # every shape for the panel.
    previews = theme_dir / "previews"
    for preview_style in ART_STYLES:
        style_roles = palette(palette_style_for(preview_style), rgb)
        grid = SHAPES["default"][preview_style]["frames"][0][0]
        source = mirror_grid(grid) if left_handed else grid
        atomic_write(previews / f"{preview_style}.png",
                     png_bytes(render_grid(source, style_roles), BASE, BASE))
    current = shapes_images["default"][0][6]
    atomic_write(previews / "current.png", png_bytes(current, BASE, BASE))
    atomic_write(previews / "shapes.png", shape_gallery_png(shapes_images))
    for index, frame in enumerate(ripple_frames(rgb, ripple_shape)):
        atomic_write(previews / f"ripple_{index}.png",
                     png_bytes(frame, HIRES, HIRES))
    return theme_dir, warnings


RIPPLE_SHAPES = ("diamond", "circle", "burst")


def ripple_frames(rgb, shape="diamond", count=4):
    """Expanding pixel-art rings for the click-ripple overlay."""
    accent = (*rgb, 255)
    soft = (*darken(rgb, 0.35), 255)
    core = (255, 255, 248, 255)
    frames = []
    center = (HIRES - 1) / 2
    for index in range(count):
        radius = 5 + index * 6
        thickness = 2.4 - index * 0.45
        frame = [(0, 0, 0, 0)] * (HIRES * HIRES)
        for y in range(HIRES):
            for x in range(HIRES):
                dx, dy = x - center, y - center
                if shape == "circle":
                    distance = (dx * dx + dy * dy) ** 0.5
                elif shape == "burst":
                    # eight radial rays instead of a closed ring
                    distance = max(abs(dx), abs(dy))
                    on_ray = abs(dx) < 1.3 or abs(dy) < 1.3 \
                        or abs(abs(dx) - abs(dy)) < 1.3
                    if not on_ray:
                        continue
                else:
                    distance = abs(dx) + abs(dy)
                if abs(distance - radius) <= thickness:
                    if index >= 2 and (x + y) % 2 == 0:
                        continue
                    frame[y * HIRES + x] = soft if index >= 2 else accent
        if index == 0:
            frame[int(center) * HIRES + int(center)] = core
        frames.append(frame)
    return frames


def shape_gallery_png(shapes_images, gap=2):
    """One row of every shape's first frame at native size, transparent bg."""
    order = list(SHAPES)
    width = len(order) * BASE + (len(order) + 1) * gap
    height = BASE + 2 * gap
    canvas = [(0, 0, 0, 0)] * (width * height)
    for index, shape in enumerate(order):
        pixels = shapes_images[shape][0][6]
        ox = gap + index * (BASE + gap)
        for y in range(BASE):
            for x in range(BASE):
                pixel = pixels[y * BASE + x]
                if pixel[3] > 0:
                    canvas[(gap + y) * width + ox + x] = pixel
    return png_bytes(canvas, width, height)


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
        # Hyprland caches the loaded theme by name; bounce through the
        # inherited theme so a regenerated CursorForge is re-read from disk.
        run_quiet([hyprctl, "setcursor", "Adwaita", str(size)])
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
               "imageHotspot", "leftHanded", "animated", "motion", "speed",
               "rippleShape", "clickRipple", "active", "restore")
    clean = {key: settings[key] for key in allowed if key in settings}
    atomic_write(config_path(),
                 (json.dumps(clean, indent=2) + "\n").encode())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

SPEEDS = {"calm": 1.7, "normal": 1.0, "lively": 0.6}


def exclusive_lock():
    """Serialize theme builds/applies across processes (flock, held until
    exit). Two concurrent runs — e.g. overlapping shell restarts — would
    otherwise interleave atomic-per-file writes into a mixed theme set."""
    import fcntl
    lock_path = data_home() / "icons" / ".omcursorforge.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "w")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def cmd_apply(args):
    lock = exclusive_lock()  # noqa: F841 — held until process exit
    rgb = parse_color(args.color)
    image_hotspot = parse_hotspot(args.image_hotspot)
    if args.size not in VALID_SIZES:
        raise ValueError(f"size must be one of {VALID_SIZES}")
    theme_dir, warnings = build_theme(
        args.out or data_home() / "icons", args.style, rgb, args.image,
        left_handed=args.left_handed, image_hotspot=image_hotspot,
        animated=not args.no_animation, motion=not args.no_motion,
        speed=SPEEDS[args.speed], ripple_shape=args.ripple_shape)

    settings = load_settings()
    if not args.no_apply:
        if "restore" not in settings:
            prev_theme, prev_size = read_gtk_cursor()
            if prev_theme and prev_theme != THEME_NAME:
                settings["restore"] = {"theme": prev_theme,
                                       "size": prev_size or 24}
        warnings += apply_cursor(THEME_NAME, args.size)

    if not args.no_save:
        settings.update({
            "style": args.style,
            "colorMode": args.color_mode,
            "customColor": args.custom_color or args.color,
            "size": args.size,
            "imagePath": args.image or "",
            "imageHotspot": args.image_hotspot,
            "leftHanded": bool(args.left_handed),
            "animated": not args.no_animation,
            "motion": not args.no_motion,
            "speed": args.speed,
            "rippleShape": args.ripple_shape,
            "clickRipple": not args.no_click_ripple,
            "active": not args.no_apply,
        })
        save_settings(settings)

    legacy = Path(args.out or data_home() / "icons") / "CursorForge"
    if legacy.is_dir():
        shutil.rmtree(legacy, ignore_errors=True)

    return {"ok": True, "themeDir": str(theme_dir), "applied": not args.no_apply,
            "warnings": warnings}


def cmd_reset(args):
    lock = exclusive_lock()  # noqa: F841 — held until process exit
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
    grid_style = grid_style_for(args.style)
    roles = palette(palette_style_for(args.style), rgb)
    factor = args.scale
    gap = 4 * factor
    tile = BASE * factor
    shapes = list(SHAPES)
    width = len(shapes) * tile + (len(shapes) + 1) * gap
    height = tile + 2 * gap
    background = (40, 40, 48, 255) if args.dark else (200, 200, 200, 255)
    canvas = [background] * (width * height)
    for index, shape in enumerate(shapes):
        frames, _, _ = shape_spec(shape, grid_style, False)
        pixels = scale_pixels(render_grid(frames[0][0], roles),
                              BASE, BASE, factor)
        ox = gap + index * (tile + gap)
        for y in range(tile):
            for x in range(tile):
                pixel = pixels[y * tile + x]
                if pixel[3] > 0:
                    canvas[(gap + y) * width + ox + x] = pixel
    atomic_write(args.out, png_bytes(canvas, width, height))
    return {"ok": True, "out": args.out, "shapes": shapes}


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
    apply_p.add_argument("--image-hotspot", default="0,0",
                         help="hotspot x,y on the 24px grid for the image style")
    apply_p.add_argument("--left-handed", action="store_true",
                         help="mirror the hand and arrow shapes")
    apply_p.add_argument("--no-animation", action="store_true",
                         help="build every shape as a single static frame")
    apply_p.add_argument("--no-motion", action="store_true",
                         help="keep animation but without sprite movement")
    apply_p.add_argument("--speed", choices=tuple(SPEEDS), default="normal",
                         help="animation pacing")
    apply_p.add_argument("--ripple-shape", choices=RIPPLE_SHAPES,
                         default="diamond", help="click-ripple ring shape")
    apply_p.add_argument("--no-click-ripple", action="store_true",
                         help="persist the click ripple as disabled")
    apply_p.add_argument("--out", default="",
                         help="icons directory override (for tests)")
    apply_p.add_argument("--no-apply", action="store_true")
    apply_p.add_argument("--no-save", action="store_true")

    sub.add_parser("reset", help="restore the previous cursor theme")

    preview_p = sub.add_parser("preview", help="render an art contact sheet")
    preview_p.add_argument("--style", choices=ART_STYLES, default="classic")
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
