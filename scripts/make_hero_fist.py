"""Build the male cultivator's punch, played by every Fist technique (and Rolling Thunder Palm), from SHOAIB's punch
video (web/static/fight.js `technique`, docs/web.md "Techniques").

The video (Gemini, 1280 x 720, 24 fps) is a 4 x 2 grid of the same fighter, each cell 320 x 360 like our frames.
The top-right cell (x 960-1280, y 0-360) stands on guard, then from 1.5 s throws one full lunging punch and comes
back on guard by 4.4 s. He fights bare-handed in darker robes, so his colours are matched to the sword-attack
video's cultivator (scripts/make_hero_attack.py) and he is scaled and placed so his feet stand where the attack
frames' feet do.

    python -m scripts.make_hero_fist path/to/punch.mp4

Writes art/portraits/fight/hero_male_fist.webp: 36 frames of 320 x 360 in an 8-wide grid, and prints the
frame where the fist is furthest out (the release, where the blow lands), for looks.MOTION_SHEETS.
Needs ffmpeg, numpy, Pillow and rembg, as make_hero_attack does.
"""
import os
import sys
import tempfile

import numpy as np
from PIL import Image

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid, match_colours

CELL = (320, 360, 960, 0)          # w, h, x, y of the punching cell in the video
START, LENGTH = 1.5, 3.0           # on guard, the punch, back on guard
STEP = 2                           # every 2nd video frame: 36 frames over 3 s


def bbox(im):
    return im.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()


def place(images, ref, room=8):
    """Scale the punch so he stands as tall as the sword cultivator, feet on the same line, body over the same spot;
    then, if his furthest punch would run past the cell's right edge, move him left by just enough (`shift`, in cell
    pixels; the fight moves the frames right by as much, so he still stands on the same spot)."""
    rx0, ry0, rx1, ry1 = bbox(ref)
    px0, py0, px1, py1 = bbox(images[0])
    s = (ry1 - ry0) / (py1 - py0)
    dx = (rx0 + rx1) / 2 - (px0 + px1) / 2 * s
    dy = ry1 - py1 * s
    reach = max(bbox(im)[2] for im in images) * s + dx
    shift = min(0, ref.width - room - reach)
    dx += shift
    out = []
    for im in images:
        big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        cell = Image.new("RGBA", ref.size, (0, 0, 0, 0))
        x, y = round(dx), round(dy)
        cell.alpha_composite(big.crop((max(0, -x), max(0, -y), big.width, big.height)), (max(0, x), max(0, y)))
        out.append(cell)
    return out, s, round(-shift)


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    sheet = Image.open(os.path.join(OUT, "hero_male_attack.webp")).convert("RGBA")
    ref = sheet.crop((0, 0, 320, 360))
    images = match_colours(cut(clip), ref)
    images, scale, shift = place(images, ref)
    reach = [bbox(im)[2] if bbox(im) else 0 for im in images]
    rows = grid(images, "hero_male_fist.webp")
    print(f"hero_male_fist.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"fist furthest out at frame {int(np.argmax(reach))} (reach per frame: {reach})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
