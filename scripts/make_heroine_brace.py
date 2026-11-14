"""Build the female cultivator's own brace from SHOAIB's video of her (web/static/fight.js `braced`, docs/web.md
"Techniques"), in place of the one made from the male's frames: her own body, robes and sleeves throughout. Same use
as his (looks.MOTION_SHEETS "brace"): the effects are placed around her braced figure (`body`).

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six panels, 3 x 2, each about 427 x 360, on white. The
top-right panel (x 853-1280, y 0-360) stands, raises her hands into guard and sinks into a wide stance, both palms
up, settled by about 5.2 s and held to the end. Its corners are whited out (panel numbers).

    python -m scripts.make_heroine_brace path/to/her_brace.mp4

Writes art/portraits/fight/hero_female_brace.webp: 38 frames of 320 x 360 in an 8-wide grid, and prints her braced
figure's box at the last frame, for looks.MOTION_SHEETS.
Needs ffmpeg, numpy, Pillow and rembg, as make_hero_attack does.
"""
import os
import sys
import tempfile

import numpy as np
from PIL import Image

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid
from scripts.make_hero_fist import bbox, place
from scripts.make_heroine_moves import in_cells

CELL = (427, 360, 853, 0)          # w, h, x, y of her bracing panel in the video
LABELS = ((0, 0, 36, 30), (390, 325, 427, 360))   # painted panel numbers, top-left and bottom-right
START, LENGTH, STEP = 0.4, 6.4, 4  # every 4th video frame: 38 frames


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    for im in clip:
        for box in LABELS:
            im.paste((246, 247, 248), box)
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place(cut(clip), ref)
    a = np.asarray(images[-1].getchannel("A"))
    ys, xs = np.where(a > 128)
    rows = grid(images, "hero_female_brace.webp")
    print(f"hero_female_brace.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"braced box x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
