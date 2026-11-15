"""Build the female cultivator's own Guard from SHOAIB's video of her (looks.GUARD_SHEETS, web/static/fight.js `block`;
docs/web.md "Guard"): the Guard button's frame-by-frame block, as the male cultivator has his.

The video (Gemini, 1280 x 720, 24 fps) is one full-size figure on a pale grey backdrop. She stands; from about 1.4 s
she sweeps her arms up and round, crosses them into a side-on guard (about 2.4 s), takes the blow at about 3.25 s
(a white shock wave comes in from the right) with her sleeves whipping round, and by about 4.9 s is steady again
behind her crossed arms. The clip taken runs from her arms closing in (2.25 s) to steady (5.0 s). The painted shock
wave is white on the white backdrop and can't be cut out cleanly, so it is left out: the fight draws its own flash
where the blow lands (`flash` in looks.GUARD_SHEETS). Gemini's sparkle mark sits outside the crop.

    python -m scripts.make_heroine_guard path/to/her_guard.mp4

Writes art/portraits/fight/hero_female_guard.webp: 33 frames of 320 x 360 in an 8-wide grid, and prints her guard's
box at the blow and how far she was moved left, for looks.GUARD_SHEETS.
Needs ffmpeg, numpy, Pillow, scipy and rembg, as make_hero_attack does.
"""
import os
import sys
import tempfile

import numpy as np
from PIL import Image

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid
from scripts.make_hero_fist import bbox, place
from scripts.make_heroine_deflect import only_her
from scripts.make_heroine_moves import in_cells

CELL = (680, 720, 260, 0)           # w, h, x, y: her, with room for the sleeves both ways
START, LENGTH, STEP = 2.25, 2.75, 2  # every 2nd video frame: 33 frames, arms closing in to steady again
BLOW = 12                           # the frame the blow lands (3.25 s)


def edge_clean(im, floor=32):
    """Drop faint alpha left along the crop's edge after scaling (a pale column well away from her)."""
    from scipy import ndimage
    a = np.asarray(im).copy()
    near = ndimage.binary_dilation(a[..., 3] > floor, iterations=6)
    a[..., 3] = np.where(near, a[..., 3], 0)
    return Image.fromarray(a, "RGBA")


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place([only_her(im) for im in cut(clip)], ref)
    images = [only_her(edge_clean(im)) for im in images]           # once more in the cell: the crop's own edge
    a = np.asarray(images[BLOW].getchannel("A"))
    ys, xs = np.where(a > 128)
    edges = [bbox(im) for im in images]
    rows = grid(images, "hero_female_guard.webp")
    print(f"hero_female_guard.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"at the blow x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}\n  boxes {edges}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
