"""Build the female cultivator's own punch from SHOAIB's video of her (web/static/fight.js `technique`, docs/web.md
"Techniques"), in place of the one made from the male's frames (scripts/make_heroine_moves.py): her own body, robes
and sleeves throughout. Same layout as his (looks.MOTION_SHEETS "fist"), so every Fist technique lines up for her.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six numbered panels, 3 x 2, each about 427 x 360, on
white. The bottom-left panel (x 0-427, y 360-720) plays on guard, a jab (out at about 1.3 s), a lunging punch held
from about 2.5 s, and the fist drawn back by about 5.2 s. Its painted number (bottom-right corner) is whited out.

    python -m scripts.make_heroine_fist path/to/her_punch.mp4

Writes art/portraits/fight/hero_female_fist.webp: 40 frames of 320 x 360 in an 8-wide grid, placed so she stands
where her idle picture stands, and prints the jab and release frames and her hand there, for looks.MOTION_SHEETS.
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

CELL = (427, 360, 0, 360)          # w, h, x, y of her punching panel in the video
LABEL = (390, 325, 427, 360)       # its painted panel number: x0 y0 x1 y1
START, LENGTH, STEP = 0.25, 5.0, 3  # every 3rd video frame: 40 frames


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    for im in clip:
        im.paste((236, 238, 240), LABEL)
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, shift = place(cut(clip), ref)
    reach = [bbox(im)[2] if bbox(im) else 0 for im in images]
    half = len(images) // 3
    jab = int(np.argmax(reach[:half]))
    release = half + int(np.argmax(reach[half:]))
    a = np.asarray(images[release].getchannel("A"))
    x = reach[release] - 1
    y = float(np.where(a[:, x - 4:x + 1].max(1) > 128)[0].mean())
    rows = grid(images, "hero_female_fist.webp")
    print(f"hero_female_fist.webp: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"jab {jab}, release {release}, hand at x {x} y {y:.0f} (reach per frame: {reach})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
