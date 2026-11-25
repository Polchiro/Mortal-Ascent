"""
The website's chests (docs/web.md "Opening a chest"): SHOAIB's painted chests, closed and open, cut off their grey
and lined up, into art/chest/<tier>.webp and art/chest/<tier>_open.webp. (art/chests/*.png, the bot's own, stay
as they are for Discord.)

  python -m scripts.make_chest_art <common closed> <common open> <uncommon closed> <uncommon open> ... <mythic open>

Cutting: the grey is modelled from the picture's border (it is a soft gradient), Gemini's sparkle is painted over,
the chest is solid (but not its cast shadow: the grey evenly darkened, which becomes see-through black), and what is lighter or darker than the grey (the open chest's light, the shadow under it) is
kept as see-through as it is faint.

Lining up: the open chest is drawn a little bigger or smaller and higher or lower than the closed one, so it is
scaled and moved until its base (the lowest solid rows: the body, which doesn't move when the lid opens) has the
closed chest's width and sits where the closed chest's base sits. Both are written on the same canvas, so the page
can swap one for the other in place.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "chest")
TIERS = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
SIZE = 720                                    # the canvas both pictures of a chest share


def backdrop(im, ring=36):
    """The grey as a smooth surface (a quadratic in x and y per colour), fitted to the picture's border."""
    h, w = im.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    m = np.zeros((h, w), bool)
    m[:ring], m[-ring:], m[:, :ring], m[:, -ring:] = True, True, True, True
    m[int(h * 0.75):, int(w * 0.75):] = False                       # not the sparkle's corner
    x, y = xs[m] / w, ys[m] / h
    A = np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], 1)
    X, Y = xs / w, ys / h
    full = np.stack([np.ones_like(X), X, Y, X * X, Y * Y, X * Y], -1)
    out = np.zeros_like(im)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(A, im[..., c][m], rcond=None)
        out[..., c] = full @ coef
    return out


def cut(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    bg = backdrop(im)
    sx0, sy0, sx1, sy1 = int(w * 0.74), int(h * 0.74), int(w * 0.95), int(h * 0.95)   # Gemini's sparkle(s)
    corner = np.zeros((h, w), bool)
    corner[sy0:sy1, sx0:sx1] = True
    lighter = (im - bg).mean(axis=2)
    sat = (im.max(axis=2) - im.min(axis=2)) / np.maximum(im.max(axis=2), 1)
    spark = ndi.binary_dilation(corner & (lighter > 14) & (sat < 0.12), iterations=4)
    im[spark] = bg[spark]                                            # white and grey: the sparkle, not the chest
    lighter = (im - bg).mean(axis=2)
    d0 = np.abs(im - bg).max(axis=2)
    body = ndi.binary_fill_holes(ndi.binary_closing(d0 > 38, iterations=3))
    lab, n = ndi.label(body)
    sizes = ndi.sum(body, lab, range(1, n + 1))
    body = lab == 1 + int(np.argmax(sizes))
    # the cast shadow on the floor: a little darker than the grey and smooth (no paint strokes); the chest is darker
    # or has detail, so it stays. Only patches at the chest's edge, low down, are taken.
    ratio = im / np.maximum(bg, 1)
    lum = im.mean(axis=2)
    mu = ndi.uniform_filter(lum, 9)
    std = np.sqrt(np.maximum(ndi.uniform_filter(lum * lum, 9) - mu * mu, 0))
    flat = body & (ratio.mean(axis=2) > 0.5) & (ratio.mean(axis=2) < 0.99) & (std < 2.5)
    flat = ndi.binary_opening(flat, iterations=3)
    lab, n = ndi.label(flat)
    edge = ndi.binary_dilation(~body, iterations=4)
    ys = np.nonzero(body.any(axis=1))[0]
    low = ys.min() + 0.6 * (ys.max() - ys.min())                     # on the floor: in the lower part, not the lid
    cy = ndi.center_of_mass(flat, lab, range(1, n + 1)) if n else []
    keep = [i for i in range(1, n + 1) if cy[i - 1][0] > low and (edge & (lab == i)).any() and (lab == i).sum() > 400]
    cast = np.isin(lab, keep)
    body = ndi.binary_opening(body & ~cast, iterations=2)
    lab, n = ndi.label(body)
    body = lab == 1 + int(np.argmax(ndi.sum(body, lab, range(1, n + 1))))
    ys = np.nonzero(body.any(axis=1))[0]                             # the lid's pale metal can match the grey:
    for y in range(ys.min(), ys.min() + int(0.3 * (ys.max() - ys.min()))):   # its top is solid edge to edge
        xs = np.nonzero(body[y])[0]
        if len(xs):
            body[y, xs.min():xs.max() + 1] = True
    d = ndi.gaussian_filter(np.abs(im - bg).max(axis=2), 1.0)
    near = np.clip(1 - ndi.distance_transform_edt(~body) / (w * 0.07), 0, 1)  # light and shadow only close by
    soft = np.clip((d - 14) / 55, 0, 1) * near
    a = np.maximum(ndi.gaussian_filter(body.astype(np.float32), 0.8), soft)
    aa = np.clip(a, 0.08, 1)[..., None]
    col = np.where(a[..., None] > 0.97, im, np.clip((im - bg * (1 - aa)) / aa, 0, 255))
    shade = ~ndi.binary_dilation(body, iterations=2) & (lighter < 6) & (np.abs(im - bg).max(axis=2) > 0)
    dark = np.clip((1 - ratio.mean(axis=2)) * 1.6, 0, 0.75) * near        # a shadow: black, as dark as it is
    col[shade] = 0
    a = np.where(shade, dark, a)
    return np.dstack([col, a * 255]).astype(np.uint8), body


def base(body):
    """The chest's base: (left, right, bottom) of its lowest solid rows."""
    ys = np.nonzero(body.any(axis=1))[0]
    bottom = ys.max()
    band = body[bottom - max(8, (bottom - ys.min()) // 6):bottom - 2]
    xs = np.nonzero(band.any(axis=0))[0]
    return xs.min(), xs.max(), bottom


def place(rgba, body, ref=None):
    """On the shared canvas: the closed chest centred with room above for the lid; the open one matched to it."""
    l, r, b = base(body)
    if ref is None:
        ys, xs = np.nonzero(body)
        w, h = xs.max() - xs.min(), ys.max() - ys.min()
        k = min(SIZE * 0.80 / w, SIZE * 0.56 / h)
        cx, target_b = SIZE / 2, SIZE * 0.86
        ref = (cx - (r - l) * k / 2, cx + (r - l) * k / 2, target_b)
    else:
        k = (ref[1] - ref[0]) / (r - l)
    ox, oy = ref[0] - l * k, ref[2] - b * k
    im = Image.fromarray(rgba, "RGBA")
    big = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE))
    canvas.alpha_composite(big, (round(ox), round(oy))) if ox >= 0 and oy >= 0 else canvas.paste(big, (round(ox), round(oy)), big)
    return canvas, ref


def main(paths):
    if len(paths) != 12:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    for i, tier in enumerate(TIERS):
        shut, shut_body = cut(paths[2 * i])
        opened, open_body = cut(paths[2 * i + 1])
        a, ref = place(shut, shut_body)
        b, _ = place(opened, open_body, ref)
        a.save(os.path.join(OUT, f"{tier}.webp"), quality=90, method=6)
        b.save(os.path.join(OUT, f"{tier}_open.webp"), quality=90, method=6)
        print(tier, "base", [round(v) for v in ref])


if __name__ == "__main__":
    main(sys.argv[1:])
