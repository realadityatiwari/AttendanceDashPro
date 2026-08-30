#!/usr/bin/env python3
"""Generate the AttendanceDash Pro brand assets from one geometry spec.

This script is the SINGLE authoritative source for the AttendanceDash Pro
brand mark. It emits:

  Vector masters (in-repo source of truth)
    public/brand/logo-mark.svg        - mark only, transparent background
    public/brand/logo-mark-tile.svg   - mark on the slate brand tile

  Raster exports
    public/brand/icon-512.png         - 512 rounded tile (manifest "any")
    public/brand/icon-192.png         - 192 rounded tile (manifest "any")
    public/brand/icon-maskable-512.png- 512 full-bleed tile (manifest "maskable")
    public/brand/icon-maskable-192.png- 192 full-bleed tile (manifest "maskable")
    public/brand/apple-touch-icon.png - 180 rounded tile (iOS)
    public/brand/logo-mark.png        - 256 transparent mark (in-app header/auth)
    public/brand/logo-mark-tile.png   - 256 tile version (auth pages)
    src/app/favicon.ico               - 16/32/48 multi-size ICO

Design: a bold geometric "A" monogram whose crossbar is a checkmark (the
attendance tick). Primary blue legs on the slate tile with a light check
reads as a distinct glyph at 16px and stays clean on masked PWA icons.

Regenerate with:
    python frontend/scripts/generate_brand_icons.py

Requires only Pillow (dev-time; not a runtime dependency).
"""

import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # frontend/
PUBLIC_BRAND = os.path.join(ROOT, "public", "brand")
SRC_APP = os.path.join(ROOT, "src", "app")

CANVAS = 512
SUPERSAMPLE = 8  # render at 8x, downscale with LANCZOS for smooth edges

# ---------------------------------------------------------------------------
# Brand palette - mirrors the existing dark design tokens (globals.css).
# ---------------------------------------------------------------------------
TILE_BG = (15, 23, 42, 255)          # slate-900 (#0F172A), manifest background
LEG = (59, 130, 246, 255)            # primary blue (#3B82F6)
CHECK = (248, 250, 252, 255)         # foreground white (#F8FAFC)

# ---------------------------------------------------------------------------
# Mark geometry (512-space). One spec shared by SVG + rasters.
# ---------------------------------------------------------------------------
APEX = (256, 112)
LEFT_FOOT = (112, 404)
RIGHT_FOOT = (400, 404)
LEG_WIDTH = 58
# Asymmetric check: left end on the left leg, deep valley, right tail rising
# past the right leg - reads as a verified/attendance tick integrated into the
# "A" crossbar. Both ends sit on the letterform; the tail's round cap slightly
# overshoots for a dynamic, modern finish.
CHECK_POINTS = [(161, 304), (252, 364), (337, 276)]
CHECK_WIDTH = 50
TILE_RADIUS = 112  # rounded-tile corner radius for non-maskable icons


def _leg_points():
    return [LEFT_FOOT, APEX, RIGHT_FOOT]


def _rounded_rect(size, radius):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=TILE_BG)
    return img


def _draw_mark(img):
    """Draw the mark (no tile) onto an RGBA image of any size."""
    s = img.size[0] / CANVAS
    d = ImageDraw.Draw(img)

    def pt(p):
        return (round(p[0] * s), round(p[1] * s))

    # "A" legs - thick rounded strokes.
    leg_w = max(1, round(LEG_WIDTH * s))
    r_leg = max(1, round(LEG_WIDTH * s / 2))
    d.line([pt(LEFT_FOOT), pt(APEX)], fill=LEG, width=leg_w)
    d.line([pt(APEX), pt(RIGHT_FOOT)], fill=LEG, width=leg_w)
    for p in (LEFT_FOOT, APEX, RIGHT_FOOT):
        d.ellipse(
            (pt(p)[0] - r_leg, pt(p)[1] - r_leg, pt(p)[0] + r_leg, pt(p)[1] + r_leg),
            fill=LEG,
        )

    # Checkmark crossbar - rounded stroke, slightly asymmetric tick.
    check_w = max(1, round(CHECK_WIDTH * s))
    r_check = max(1, round(CHECK_WIDTH * s / 2))
    pts = [pt(p) for p in CHECK_POINTS]
    d.line([pts[0], pts[1]], fill=CHECK, width=check_w)
    d.line([pts[1], pts[2]], fill=CHECK, width=check_w)
    for p in pts:
        d.ellipse(
            (p[0] - r_check, p[1] - r_check, p[0] + r_check, p[1] + r_check),
            fill=CHECK,
        )


def render_icon(size, rounded=False):
    """Render the full icon tile (background + mark) at a target size."""
    hi = size * SUPERSAMPLE
    tile = _rounded_rect(hi, round(TILE_RADIUS * SUPERSAMPLE)) if rounded else Image.new(
        "RGBA", (hi, hi), TILE_BG
    )
    _draw_mark(tile)
    return tile.resize((size, size), Image.LANCZOS)


def render_mark(size):
    """Render only the mark (transparent background)."""
    hi = size * SUPERSAMPLE
    img = Image.new("RGBA", (hi, hi), (0, 0, 0, 0))
    _draw_mark(img)
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------------------
# SVG masters
# ---------------------------------------------------------------------------
def _svg_path(points, width, color, cap="round", join="round"):
    coords = " ".join(f"{p[0]},{p[1]}" for p in points)
    return (
        f'<polyline points="{coords}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="{cap}" stroke-linejoin="{join}"/>'
    )


def write_svg(path, tile_bg=False):
    legs = _svg_path(_leg_points(), LEG_WIDTH, "#3B82F6")
    check = _svg_path(CHECK_POINTS, CHECK_WIDTH, "#F8FAFC")
    tile = ""
    if tile_bg:
        tile = (
            f'<rect width="{CANVAS}" height="{CANVAS}" rx="{TILE_RADIUS}" '
            f'fill="#0F172A"/>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS}" '
        f'height="{CANVAS}" viewBox="0 0 {CANVAS} {CANVAS}">'
        f"{tile}{legs}{check}</svg>"
    )
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg + "\n")


# ---------------------------------------------------------------------------
# Raster exports
# ---------------------------------------------------------------------------
def save_png(img, path):
    img.save(path, format="PNG")


def write_favicon(path):
    """Multi-size .ico (16/32/48) from the same geometry."""
    sizes = [16, 32, 48]
    frames = [render_icon(s, rounded=True) for s in sizes]
    frames[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )


def main():
    os.makedirs(PUBLIC_BRAND, exist_ok=True)
    os.makedirs(SRC_APP, exist_ok=True)

    write_svg(os.path.join(PUBLIC_BRAND, "logo-mark.svg"), tile_bg=False)
    write_svg(os.path.join(PUBLIC_BRAND, "logo-mark-tile.svg"), tile_bg=True)

    for name, size, rounded in [
        ("icon-512.png", 512, True),
        ("icon-192.png", 192, True),
        ("icon-maskable-512.png", 512, False),
        ("icon-maskable-192.png", 192, False),
        ("apple-touch-icon.png", 180, True),
        ("logo-mark.png", 256, None),  # mark only, no tile
        ("logo-mark-tile.png", 256, True),  # tile version
    ]:
        if rounded is None:
            img = render_mark(size)
        else:
            img = render_icon(size, rounded=rounded)
        save_png(img, os.path.join(PUBLIC_BRAND, name))

    write_favicon(os.path.join(SRC_APP, "favicon.ico"))

    print("Generated brand assets under", PUBLIC_BRAND)
    print("Generated favicon at", os.path.join(SRC_APP, "favicon.ico"))


if __name__ == "__main__":
    main()
