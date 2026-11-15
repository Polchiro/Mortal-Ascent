"""Build the female cultivator's deflection from SHOAIB's video of her (web/static/fight.js `deflected`, docs/web.md
"Techniques"): the one movement every deflection technique shares (web/technique_fx.py "deflect"). Hers only: the
male cultivator keeps his own looks for those techniques.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six panels, 3 x 2, each about 427 x 360, on white. The
top-middle panel (x 427-853, y 0-360) stands on guard, palm raised; from about 1.8 s she turns into the blow, reaches
out to meet it, carries it round and aside with a swirl of her sleeve (about 2.5-4.2 s) and settles back on guard by
about 4.8 s. At its widest the sleeve runs a little past the panel's left edge, so a wider strip is cut and anything
not joined to her (the next panel's fighter) is dropped.

    python -m scripts.make_heroine_deflect path/to/her_deflect.mp4

Writes art/portraits/fight/hero_female_deflect.webp: 36 frames of 320 x 360 in an 8-wide grid, and prints her figure's
box on guard and how far the sleeve reaches on each frame, for looks.MOTION_SHEETS "deflect".
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

CELL = (448, 360, 405, 0)          # w, h, x, y: her panel, with room on the left for the sleeve
START, LENGTH, STEP = 1.0, 4.5, 3  # every 3rd video frame: 36 frames, on guard to on guard


def only_her(im):
    """Keep the largest solid shape (her) and what touches it; drop strays such as the next panel's sleeve."""
    from scipy import ndimage
    a = np.asarray(im).copy()
    solid = a[..., 3] > 40
    labels, n = ndimage.label(ndimage.binary_dilation(solid, iterations=3))
    if n > 1:
        sizes = ndimage.sum(solid, labels, range(1, n + 1))
        keep = labels == (1 + int(np.argmax(sizes)))
        a[..., 3] = np.where(keep, a[..., 3], 0)
    return Image.fromarray(a, "RGBA")


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place([only_her(im) for im in cut(clip)], ref)
    reach = [bbox(im)[0] if bbox(im) else 0 for im in images]          # left edge: the sleeve sweeping behind her
    right = [bbox(im)[2] if bbox(im) else 0 for im in images]          # right edge: the hand reaching to the beast
    a = np.asarray(images[0].getchannel("A"))
    ys, xs = np.where(a > 128)
    rows = grid(images, "hero_female_deflect.webp")
    print(f"hero_female_deflect.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"on-guard box x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}\n  left edge per frame {reach}\n"
          f"  right edge per frame {right}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
