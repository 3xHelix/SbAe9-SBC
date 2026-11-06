# SPDX-License-Identifier: GPL-2.0-only
"""Make the app icon PNGs (appicon/sbae9-sbc-<size>.png) from the artwork.

    python3 tools/make_icons.py "Neon Purple Audio Mixer Icon.png"

The artwork is a rounded tile on a dark, grainy backdrop with no
transparency. This cuts the tile out along a rounded square (drawn 4x and
scaled down, so the edge is smooth) and saves it at the sizes desktops ask
for. Re-measure TILE if the artwork changes.
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "appicon")
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
TILE = (76, 74, 1101, 196)          # left, top, side, corner radius in the 1254 px artwork


def cut(src):
    left, top, side, radius = TILE
    im = Image.open(src).convert("RGBA")
    k = 4
    mask = Image.new("L", (im.width * k, im.height * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (left * k, top * k, (left + side) * k - 1, (top + side) * k - 1), radius * k, fill=255)
    im.putalpha(mask.resize(im.size, Image.LANCZOS))
    return im.crop((left, top, left + side, top + side))


def main(src):
    tile = cut(src)
    os.makedirs(OUT, exist_ok=True)
    for size in SIZES:
        path = os.path.join(OUT, f"sbae9-sbc-{size}.png")
        tile.resize((size, size), Image.LANCZOS).save(path, optimize=True)
        print(path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
