"""Turn SHOAIB's Gemini designs for the sidestep techniques into the effect pictures the fight plays (web/static/fight.js
`sidestepped`; docs/web.md "Techniques"), cleaned of their painted checkerboard and Gemini's sparkle like the others.

    python -m scripts.make_sidestep_fx mist.png cloud.png

    mist.png    Drifting Mist Steps: three mist afterimages of her running, the oldest dissolving into sparkles. Its
                title is painted across the top ("DRIFTING MIST STEPS - MIST AFTERIMAGES"); that band is dropped.
    cloud.png   Cloud-Walking Shadow: three cloud afterimages of her running, joined by curling cloud ribbons.

Both are see-through figures on a dark checker of pure black and grey squares (`key_dark`). Alpha comes from
brightness above the grey squares and from colour (the checker has none). In the faint, see-through parts the checker
shows through as a pattern, so there the picture is averaged over one checker period, as make_fist_fx `key_glow`
does; unlike `key_glow`, the averaged haze is held inside the design's own outline, so the gaps between the figures
stay open. The bright core keeps its full detail.

Writes art/fx/tech/<technique id>.webp.
"""
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from scripts.make_deflect_fx import main_part
from scripts.make_fist_fx import PERIOD, SPARKLE, save
from scripts.make_palm_fx import trim

TITLE = 60                       # the painted title's band at the top of the mist design, in px of the 1024 x 559 picture
GREY = 70                        # the checker's grey squares are no brighter than this; its black ones are 0
MEAN = 33.0                      # the checker's average over one period


def key_dark(path, title=0):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    smooth = np.asarray(im.filter(ImageFilter.BoxBlur(PERIOD // 2))).astype(np.float32)
    v, sat = a.max(-1), a.max(-1) - a.min(-1)
    sharp = np.maximum(np.clip((v - GREY) / 120, 0, 1), np.clip((sat - 12) / 70, 0, 1))
    soft = np.clip((smooth.max(-1) - MEAN + 3) / 140, 0, 1)                 # above the averaged checker: the design
    shape = ndimage.binary_dilation(ndimage.binary_closing(sharp > 0.12, iterations=2), iterations=2)
    core = np.clip((v - GREY - 90) / 60, 0, 1)                              # only the truly bright core stays sharp
    alpha = (sharp * core + soft * (1 - core)) * shape
    src = a * core[..., None] + smooth * (1 - core[..., None])
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0
    rgb = (src - (1 - alpha[..., None]) * MEAN) / np.maximum(alpha[..., None], 0.05)
    h, w = alpha.shape
    alpha[h - SPARKLE[1]:h - SPARKLE[3], w - SPARKLE[0]:w - SPARKLE[2]] = 0     # Gemini's mark
    alpha[:title] = 0
    alpha = np.where(alpha < 0.05, 0, alpha)
    return Image.fromarray(np.dstack([rgb.clip(0, 255), alpha * 255]).astype(np.uint8), "RGBA")


def main(paths):
    if len(paths) != 2:
        sys.exit(__doc__)
    mist, cloud = paths
    save(trim(main_part(key_dark(mist, TITLE), 0.02)), "drifting_mist_steps")
    save(trim(main_part(key_dark(cloud), 0.02)), "cloud_walking_shadow")


if __name__ == "__main__":
    main(sys.argv[1:])
