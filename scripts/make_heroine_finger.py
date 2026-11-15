"""Build the female cultivator's own finger jab from SHOAIB's video of her (looks.MOTION_SHEETS "finger", web/static/fight.js
`technique`; docs/web.md "Techniques"), in place of the one made from the male's frames (make_heroine_moves.py): her
own body, robes and sleeves throughout. Every Finger technique plays it, its beam leaving from her fingertip.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six panels, 3 x 2, each about 424 x 356, on white with grey
divider lines. The top-right panel (x 858-1278, y 2-356) stands on guard, palm raised (2.0 s); she points two fingers
out (about 2.6 s), swings the arm and drops into a deep lunge thrusting them forward (held about 3.1-3.8 s), rises
drawing the arm in to her chest (to about 4.0 s), then points again and holds it to the end of the video: it never comes back to
guard. So the sheet is her guard, the first point, the lunging thrust and the rise with the arm drawn in (2.0-4.0 s),
then three frames of her guard from the start of the clip to finish on. No frame is drawn or altered; the step from
the arm drawn in back to the palm-up guard is a cut between the video's own frames.

    python -m scripts.make_heroine_finger path/to/her_finger.mp4

Writes art/portraits/fight/hero_female_finger.webp: 28 frames of 320 x 360 in an 8-wide grid, and prints her reach per
frame and where her fingertip is at the furthest, for looks.MOTION_SHEETS.
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

CELL = (420, 354, 858, 2)          # w, h, x, y: her panel, inside its divider lines
START = 2.0                        # s
THRUST = range(1, 50, 2)           # 2.00-4.00 s: guard, the first point, the lunging thrust, the rise (25 frames)
GUARD = (1, 3, 5)                  # 2.00-2.17 s: her guard again, to finish on (3 frames)


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=2.1, numbers=list(THRUST) + list(GUARD))
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place([only_her(im) for im in cut(clip)], ref)
    images = [only_her(edge_clean(im)) for im in images]
    reach = [bbox(im)[2] for im in images]
    out = 15                                                     # the lunge, fingers furthest forward (looks `release`)
    a = np.asarray(images[out].getchannel("A"))
    ys, xs = np.where(a > 128)
    tip = ys[xs > xs.max() - 8]
    rows = grid(images, "hero_female_finger.webp")
    print(f"hero_female_finger.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px\n"
          f"  reach per frame {reach}\n  furthest at frame {out}: fingertip x {xs.max()} y {int(tip.mean())}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
