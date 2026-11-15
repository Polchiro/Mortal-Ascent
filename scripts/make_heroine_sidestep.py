"""Build the female cultivator's sidestep from SHOAIB's video of her (looks.MOTION_SHEETS "sidestep", web/static/fight.js
`sidestepped`; docs/web.md "Techniques"): what she plays when Drifting Mist Steps or Cloud-Walking Shadow slips her
away from the beast's Break. Hers only.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six panels, 3 x 2, each about 424 x 357, on white with dark
divider lines. The top-right panel (x 857-1280, y 0-357) stands on guard, palm raised; from about 0.5 s she sweeps her
sleeve and drops into a deep side lunge, leaning away from the attacker (deepest at about 1.05-1.15 s), then rises
back into the same guard by about 2.4 s. Every 2nd video frame is kept, so the page plays it at the video's own pace
(12 frames a second): nothing is sped up, stretched or cut.

    python -m scripts.make_heroine_sidestep path/to/her_sidestep.mp4

Writes art/portraits/fight/hero_female_sidestep.webp: 27 frames of 320 x 360 in an 8-wide grid, and prints her box on
guard and how far she leans away on each frame, for looks.MOTION_SHEETS.
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

CELL = (423, 357, 857, 0)          # w, h, x, y: her panel, inside its divider lines
START, LENGTH, STEP = 0.25, 2.25, 2  # on guard to on guard again: 27 frames, 12 a second


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place([only_her(im) for im in cut(clip)], ref)
    images = [only_her(edge_clean(im)) for im in images]
    boxes = [bbox(im) for im in images]
    mids = [round((b[0] + b[2]) / 2) for b in boxes]
    tops = [b[1] for b in boxes]
    a = np.asarray(images[0].getchannel("A"))
    ys, xs = np.where(a > 128)
    rows = grid(images, "hero_female_sidestep.webp")
    print(f"hero_female_sidestep.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"on guard x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}\n  middle per frame {mids}\n  top per frame {tops}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
