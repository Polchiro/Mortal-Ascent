"""Turn SHOAIB's Gemini designs for the kick techniques into the effect pictures the fight plays (web/static/fight.js,
`technique`; docs/web.md "Techniques").

Unlike the punch and palm designs, these four were drawn over a painted scene (a dark ruined city, fog, orange embers)
with the technique's name written across the top and Gemini's sparkle in the corner. Each glowing design is keyed out
by how much brighter (white designs) or more vividly coloured (leaves, fire) it is than the dark scene; the name and
the sparkle are cleared, and only what joins the design itself is kept, so loose embers of the scene drop out.

    python -m scripts.make_kick_fx crescent.png swallow.png autumn.png meteor.png

Writes art/fx/tech/<technique id>.webp. The leaves and the meteor share their colours with the scene's embers and
firelight, so some of it can stay at their edges; a version on plain black can replace them by re-running this.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from scripts.make_fist_fx import SPARKLE, save

DESIGNS = ("crescent_sweep", "swift_swallow_kick", "autumn_wind_kick", "meteor_falling_kick")
TITLE = (370, 30, 660, 74)                 # the technique's name, written across the top: x0 y0 x1 y1
# per design: how alpha is read (white: brightness; vivid: colour and brightness), and its threshold and range
KEY = {"crescent_sweep": ("white", 95, 110), "swift_swallow_kick": ("white", 95, 110),
       "autumn_wind_kick": ("vivid", 0, 0), "meteor_falling_kick": ("vivid", 0, 0)}


def key(im, how, lo, span):
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    v, sat = a.max(-1), a.max(-1) - a.min(-1)
    scene = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(40))).astype(np.float32)   # the scene's own light
    if how == "white":
        alpha = np.clip((v - np.maximum(lo, scene + 45)) / span, 0, 1)
    else:                                  # leaves and fire: vivid and brighter than the fog around them
        alpha = np.clip((sat - 70) / 90, 0, 1) * np.clip((v - scene - 40) / 90, 0, 1)
        alpha = np.maximum(alpha, np.clip((v - 200) / 40, 0, 1))          # white-hot core and light streaks
    x0, y0, x1, y1 = TITLE
    alpha[y0:y1, x0:x1] = 0
    h, w = alpha.shape
    alpha[h - SPARKLE[1]:h - SPARKLE[3], w - SPARKLE[0]:w - SPARKLE[2]] = 0
    # keep what joins the design: the biggest pieces of the solid part, with a margin for its glow and sparks
    solid = alpha > 0.35
    lab, n = ndimage.label(ndimage.binary_closing(solid, iterations=4))
    if n:
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * 0.04))
        alpha *= ndimage.gaussian_filter(ndimage.binary_dilation(keep, iterations=22).astype(np.float32), 6)
    bg = np.asarray(im.convert("RGB").filter(ImageFilter.GaussianBlur(40))).astype(np.float32)   # un-mix the scene
    rgb = (a - (1 - alpha[..., None]) * bg) / np.maximum(alpha[..., None], 0.05)
    out = Image.fromarray(np.dstack([rgb.clip(0, 255), alpha * 255]).astype(np.uint8), "RGBA")
    box = out.getchannel("A").point(lambda q: 255 if q > 24 else 0).getbbox()
    return out.crop((max(0, box[0] - 16), max(0, box[1] - 16), min(w, box[2] + 16), min(h, box[3] + 16)))


def main(paths):
    if len(paths) != len(DESIGNS):
        sys.exit(__doc__)
    for tid, path in zip(DESIGNS, paths):
        save(key(Image.open(path), *KEY[tid]), tid)


if __name__ == "__main__":
    main(sys.argv[1:])
