"""
The art of the Dantian screen and of swallowing pills (docs/web.md "The Dantian"), cut from SHOAIB's Flow videos and
Gemini picture.

  python -m scripts.make_dantian_art sea <video>        the inner sea of Qi: a still, a loop, its sound looped
  python -m scripts.make_dantian_art absorb <video>     a pill dissolving into a point of light (light on black: the
                                                        page adds it onto the scene and tints it to the pill)
  python -m scripts.make_dantian_art gourd <picture>    the toxicity icon (art/icons/attr/toxicity.webp, beside qi.webp)

Gemini's sparkle and Flow's "Veo" are painted out, like scripts/make_breakthrough_art.py does. Needs ffmpeg, numpy,
Pillow, scipy and OpenCV.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from . import make_breakthrough_art as bt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "dantian")
SEA_SPARKLE = (1700, 862, 1850, 1010)                   # Gemini's sparkle on the water (1920x1080)


def sea(video):
    os.makedirs(OUT, exist_ok=True)
    fixed = os.path.join(OUT, "_sea.mp4")
    bt.refilm(video, fixed, lambda f: np.asarray(bt.lift(Image.fromarray(f), SEA_SPARKLE, dx=170, feather=16)))
    bt.still(fixed, 0.05, bt.VEO, os.path.join(OUT, "sea.jpg"))
    body = bt.loop(fixed, bt.VEO, os.path.join(OUT, "sea.mp4"), None, fade=1.6, crf=27)
    os.remove(fixed)
    bt.loop(video, "null", os.path.join(OUT, "_x.mp4"), os.path.join(OUT, "sea.mp3"), fade=1.6, gain=-5)
    os.remove(os.path.join(OUT, "_x.mp4"))
    print("sea loop", body)


def absorb(video):
    os.makedirs(OUT, exist_ok=True)
    bt.once(video, bt.BLACK_VEO, os.path.join(OUT, "absorb.mp4"), 0, 5.4, crf=29, size="1280:720")
    bt.sound(video, 0, 5.4, os.path.join(OUT, "absorb.mp3"), fade=0.8)
    print("absorb done")


def gourd(picture):
    """Off the flat grey: the gourd solid, its wisp of smoke as see-through as it is faint."""
    im = np.asarray(Image.open(picture).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    bg = np.median(np.concatenate([im[:40, :40].reshape(-1, 3), im[:40, -40:].reshape(-1, 3),
                                   im[-40:, :40].reshape(-1, 3)]), axis=0)
    im[round(h * 0.84):, round(w * 0.84):] = bg                          # the sparkle
    d = np.abs(im - bg).max(axis=2)
    body = ndi.binary_fill_holes(ndi.binary_closing(d > 40, iterations=3))
    lab, n = ndi.label(body)
    if n > 1:
        sizes = ndi.sum(body, lab, range(1, n + 1))
        body = lab == 1 + int(np.argmax(sizes))
    soft = np.clip((ndi.gaussian_filter(d, 1.2) - 6) / 40, 0, 1)
    a = np.maximum(ndi.gaussian_filter(body.astype(np.float32), 1.0), soft)
    aa = np.clip(a, 0.1, 1)[..., None]
    col = np.where(a[..., None] > 0.97, im, np.clip((im - bg * (1 - aa)) / aa, 0, 255))
    ys, xs = np.nonzero(a > 0.06)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    side = max(x1 - x0, y1 - y0) + 16
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    out = Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8), "RGBA")
    sq = Image.new("RGBA", (side, side))
    sq.paste(out.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)), (0, 0))
    sq = sq.resize((128, 128), Image.LANCZOS)
    path = os.path.join(ROOT, "art", "icons", "attr", "toxicity.webp")
    sq.save(path, quality=92, method=6)
    print("gourd", path)


def main(args):
    if len(args) != 2 or args[0] not in ("sea", "absorb", "gourd"):
        sys.exit(__doc__)
    {"sea": sea, "absorb": absorb, "gourd": gourd}[args[0]](args[1])


if __name__ == "__main__":
    main(sys.argv[1:])
