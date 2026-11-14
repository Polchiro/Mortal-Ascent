"""Build the male cultivator's finger jab, played by every Finger technique, from SHOAIB's finger-jab video
(web/static/fight.js `technique`, docs/web.md "Techniques"). Made like the punch (scripts/make_hero_fist.py).

The video (Gemini, 1280 x 720, 24 fps) is a 4 x 2 grid of 320 x 360 cells on white. The top-right cell
(x 960-1280, y 0-360) plays one clean jab: on guard at 2.5 s, a lunge with two fingers thrust forward (out at
about 4.2 s), held, and back on guard by 8.5 s. Bare-handed in black robes, so his colours are matched to his sword
frames. The female cultivator's frames are made from these (scripts/make_heroine_moves.py).

    python -m scripts.make_hero_finger path/to/finger.mp4

Writes art/portraits/fight/hero_male_finger.webp: 48 frames of 320 x 360 in an 8-wide grid, and prints the frame
where the fingertip is furthest out (the release, where the beam leaves), for looks.MOTION_SHEETS.
Needs ffmpeg, numpy, Pillow and rembg, as make_hero_attack does.
"""
import os
import sys
import tempfile

import numpy as np
from PIL import Image

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid, match_colours

CELL = (320, 360, 960, 0)          # w, h, x, y of the jabbing cell in the video
START, LENGTH = 2.5, 6.0           # on guard, the jab, back on guard
STEP = 3                           # every 3rd video frame: 48 frames over 6 s
BROKEN = {8: 7}                    # frame 8 has the arm torn off by the video: shown as frame 7


def bbox(im):
    return im.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()


def place(images, ref, room=8):
    """Scale the strike so he stands as tall as the sword cultivator, feet on the same line, body over the same spot;
    then, if his furthest fingertip would run past the cell's right edge, move him left by just enough (`shift`, in cell
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
    images = [images[BROKEN.get(i, i)] for i in range(len(images))]
    reach = [bbox(im)[2] if bbox(im) else 0 for im in images]
    rows = grid(images, "hero_male_finger.webp")
    print(f"hero_male_finger.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"fingertip furthest out at frame {int(np.argmax(reach))} (reach per frame: {reach})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
