"""
The special openings of Epic, Legendary and Mythic chests (docs/web.md "Opening a chest"): SHOAIB's Nano Banana
pictures cut for the vault, into art/chest/rite/.

Light on black (seal, dragon, beam, crack, galaxy): Gemini's sparkle painted black, cropped round what glows, and
every edge faded to black (a round fade for the round ones) so nothing ends on a straight line: the page adds them
onto the scene ("lighter"), where black is nothing. Saved as JPG (black needs no transparency).
The red 天 stamp (on grey): its red kept, the grey made see-through, saved as WebP with alpha.

    python -m scripts.make_chest_rite_art seal.png dragon.png beam.png crack.png galaxy.png stamp.png
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "chest", "rite")
SPARKLE = (1246, 640, 34)          # Gemini's mark on a 1376 x 768 picture: middle and a radius that covers it


def smooth(e):
    e = np.clip(e, 0, 1)
    return e * e * (3 - 2 * e)


def light(path):
    im = Image.open(path).convert("RGB")
    k = im.width / 1376
    x, y, r = (round(v * k) for v in SPARKLE)
    d = ImageDraw.Draw(im)
    d.ellipse((x - r, y - r, x + r, y + r), fill=(0, 0, 0))
    return np.asarray(im).astype(np.float32)


def save_jpg(a, name, size):
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize(size, Image.LANCZOS)
    im.save(os.path.join(OUT, name), quality=88)
    print("wrote", name, im.size, os.path.getsize(os.path.join(OUT, name)) // 1024, "KB")


def round_fade(a, cx, cy, side, inner, outer):
    """A square of `side` round (cx, cy), padded with black where it leaves the picture, faded to black between
    `inner` and `outer` (shares of half the side) from its middle."""
    h, w = a.shape[:2]
    half = side // 2
    out = np.zeros((side, side, 3), np.float32)
    x0, y0 = cx - half, cy - half
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(w, x0 + side), min(h, y0 + side)
    out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = a[sy0:sy1, sx0:sx1]
    yy, xx = np.mgrid[0:side, 0:side]
    d = np.hypot(xx - half, yy - half) / half
    out *= smooth((outer - d) / (outer - inner))[..., None]
    # the picture's own top and bottom edge (the seal runs off it): faded too, so no straight cut shows
    band = side * 0.06
    top, bot = sy0 - y0, sy1 - y0
    ys = np.arange(side)
    ey = smooth((ys - top) / band) * smooth((bot - 1 - ys) / band)
    out *= ey[:, None, None]
    return out


def box_fade(a, fx, fy):
    """Fade the left/right `fx` and top/bottom `fy` shares of the picture to black."""
    h, w = a.shape[:2]
    xs, ys = np.arange(w) / w, np.arange(h) / h
    ex = smooth(np.minimum(xs, 1 - xs) / fx) if fx else np.ones(w)
    ey = smooth(np.minimum(ys, 1 - ys) / fy) if fy else np.ones(h)
    return a * ex[None, :, None] * ey[:, None, None]


def main(seal, dragon, beam, crack, galaxy, stamp):
    os.makedirs(OUT, exist_ok=True)
    a = light(seal)                                  # the rune seal: a circle, its outer ring runs off top and bottom
    save_jpg(round_fade(a, a.shape[1] // 2, a.shape[0] // 2, a.shape[0], 0.80, 1.0), "seal.jpg", (720, 720))
    # the same circle as a see-through picture (light kept as colour, black gone) for Epic's circle drawn behind the
    # chest, where adding light onto the scene can't be used
    ring = round_fade(a, a.shape[1] // 2, a.shape[0] // 2, a.shape[0], 0.80, 1.0)
    al = np.clip(ring.max(axis=2) / 255 * 1.15, 0, 1)
    rgb = np.clip(ring / np.maximum(al, 1e-3)[..., None], 0, 255)
    Image.fromarray(np.dstack([rgb, al * 255]).astype(np.uint8), "RGBA").resize((720, 720), Image.LANCZOS) \
        .save(os.path.join(OUT, "ring.webp"), quality=90)
    print("wrote ring.webp")
    a = light(dragon)                                # the dragon coiled in a ring
    save_jpg(round_fade(a, round(a.shape[1] * 0.485), a.shape[0] // 2, a.shape[0], 0.82, 1.0), "dragon.jpg", (720, 720))
    a = light(beam)                                  # the beam: its middle column, fading left, right and at the top
    w = a.shape[1]
    col = a[:, round(w * 0.28):round(w * 0.72)]
    col = box_fade(col, 0.30, 0)
    ys = np.arange(col.shape[0]) / col.shape[0]
    col *= smooth(ys / 0.12)[:, None, None]          # it comes out of nothing at the top; its foot stays bright
    save_jpg(col, "beam.jpg", (480, 600))
    a = light(crack)                                 # the sky crack: its upper part, edges faded
    a = a[:round(a.shape[0] * 0.78)]
    save_jpg(box_fade(a, 0.08, 0.10), "crack.jpg", (1100, 480))
    a = light(galaxy)                                # the galaxy: round, faded well inside the frame
    save_jpg(round_fade(a, a.shape[1] // 2, a.shape[0] // 2, a.shape[0], 0.70, 1.0), "galaxy.jpg", (720, 720))
    im = Image.open(stamp).convert("RGB")            # the stamp: red kept, grey gone
    k = im.width / 1376
    im = im.crop((round(500 * k), round(195 * k), round(876 * k), round(571 * k)))
    c = np.asarray(im).astype(np.float32)
    red = c[..., 0] - (c[..., 1] + c[..., 2]) / 2
    alpha = np.clip((red - 40) / 45, 0, 1)
    c = np.dstack([np.maximum(c[..., 0], 150), c[..., 1] * 0.8, c[..., 2] * 0.8])    # no grey fringe at its edge
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)))
    rgba = np.dstack([c.astype(np.uint8), alpha])
    Image.fromarray(rgba, "RGBA").resize((360, 360), Image.LANCZOS).save(os.path.join(OUT, "stamp.webp"), quality=92)
    print("wrote stamp.webp")


if __name__ == "__main__":
    if len(sys.argv) != 7:
        sys.exit(__doc__)
    main(*sys.argv[1:])
