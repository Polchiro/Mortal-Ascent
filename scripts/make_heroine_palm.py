"""Build the female cultivator's own palm push from SHOAIB's video of her (looks.MOTION_SHEETS "palm", web/static/fight.js
`technique`; docs/web.md "Techniques"), in place of the one made from the male's frames (make_heroine_moves.py): her
own body, robes and sleeves throughout. Every Palm attack technique plays it.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six panels, 3 x 2, each about 427 x 360, on pale grey with
thin grid lines. The top-right panel (x 853-1280, y 0-360) stands on guard (2.5 s), sweeps both arms and sleeves back
(drawn back by about 3.5 s), lunges forward pushing both palms out (furthest at about 3.95 s), holds the push to about
6.9 s and rises back to standing by about 8.3 s. Its frames are taken unevenly: every 2nd through the draw-back and
the lunge, every 8th through the long hold, every 3rd on the way back.

    python -m scripts.make_heroine_palm path/to/her_palm.mp4

Writes art/portraits/fight/hero_female_palm.webp: 40 frames of 320 x 360 in an 8-wide grid, and prints the palms'
reach per frame and where they are at the release, for looks.MOTION_SHEETS.
Needs ffmpeg, numpy, Pillow, scipy and rembg, as make_hero_attack does.
"""
import os
import sys
import tempfile

import numpy as np

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid
from scripts.make_hero_fist import bbox, place
from scripts.make_heroine_deflect import only_her
from scripts.make_heroine_guard import edge_clean
from scripts.make_heroine_moves import in_cells

CELL = (424, 357, 856, 0)          # w, h, x, y: her panel, inside its grid lines
START, LENGTH = 2.5, 5.95          # on guard to standing again
NUMBERS = (list(range(1, 27, 2))   # 2.50-3.50 s: on guard, the arms swept back (13)
           + list(range(27, 40, 2))  # 3.58-4.08 s: the lunge, palms out (7)
           + list(range(47, 108, 8))  # 4.42-6.75 s: the push held (8)
           + list(range(108, 143, 3)))  # 6.96-8.42 s: rising back to standing (12)


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=NUMBERS)
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place([only_her(im) for im in cut(clip)], ref)
    images = [only_her(edge_clean(im)) for im in images]
    reach = [bbox(im)[2] for im in images]
    out = int(np.argmax(reach))
    a = np.asarray(images[out].getchannel("A"))
    ys, xs = np.where(a > 128)
    tip = ys[xs > xs.max() - 12]
    rows = grid(images, "hero_female_palm.webp")
    print(f"hero_female_palm.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px\n"
          f"  reach per frame {reach}\n  furthest at frame {out}: palms x {xs.max()} y {int(tip.mean())}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
