"""Cut SHOAIB's Gemini environment pictures into the game's pieces (web/env.py, docs/environment.md).

Each picture is one object (a rock, a log, a plant ...) on a plain flat backdrop (grey-green, or light grey for green
things). For each:

1. The backdrop's colour is read from the picture's edges.
2. The object is cut out: rembg (isnet-general-use) for its outline, plus anything clearly off the backdrop's colour
   (thin stems and petals rembg drops), minus everything of the backdrop's colour joined to the picture's edge, and
   minus a cast shadow (the backdrop's colour, only darker). Gemini's sparkle and other loose bits not joined to the
   object are dropped.
3. Edges are cleaned: where the edge is see-through, the backdrop's colour mixed into it is taken back out, so no
   grey or green fringe is left; the edge is pulled in by a pixel and softened.
4. Per-asset fixes (FIX): `cut_below` drops everything below a line (the fern's bare roots, which would float above
   the ground), `rim` removes the pale blue rim line Gemini paints along some rocks' top edges.
5. It is cropped, made at most MAX px on its long side (about twice the size it is drawn), and saved as
   art/env/<region>/<category>/<name>.webp. Its foot (where it touches the ground) is measured: the middle of its
   lowest part, or for a log (`length` in web/env.ASSETS) the lowest point under the middle of its length. Both go into
   art/env/catalog.json.

    python -m scripts.make_env_assets rock_small_01=rock.png fern_01=fern.png ...

The source pictures are only read, never changed. A name must be in web/env.ASSETS. Prints each result and anything
that looks wrong (the object touching the picture's edge, a backdrop that isn't flat). Needs numpy, Pillow, opencv
and rembg.
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

from web import env

ROOT = env.ROOT
MAX = 640                         # the long side of a saved piece (px): about twice its drawn size
KEY = 34                          # colour distance from the backdrop that is surely the object
SAME = 16                         # ... and that is surely the backdrop, when joined to the picture's edge
FIX = {
    "fern_01": {"cut_below": 0.82},          # its bare roots hang below the fronds: cut at 82% of the picture
    "rock_small_01": {"rim": True},
    "boulder_01": {"rim": True},
}


def backdrop(rgb):
    border = np.concatenate([rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3), rgb[:, :8].reshape(-1, 3),
                             rgb[:, -8:].reshape(-1, 3)])
    bg = np.median(border, 0)
    flat = np.percentile(np.abs(border - bg).max(1), 95)
    return bg, flat


def joined_to_edge(mask):
    """The parts of `mask` that touch the picture's edge."""
    n, lab = cv2.connectedComponents(mask.astype(np.uint8), connectivity=4)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    return np.isin(lab, list(edge))


def biggest(alpha):
    """Keep the object: the largest piece and anything joined to it (drops the sparkle, specks)."""
    m = (alpha > 24).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((9, 9), np.uint8)))
    if n < 2:
        return alpha
    keep = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return np.where(lab == keep, alpha, 0).astype(np.uint8)


def remove_rim(rgb, alpha, width=9):
    """Gemini's pale blue rim line along a rock's edge: pale, bluer than it is red, within `width` px of the edge."""
    inside = (alpha > 128).astype(np.uint8)
    dist = cv2.distanceTransform(inside, cv2.DIST_L2, 3)
    r, g, b = rgb[..., 0].astype(int), rgb[..., 1].astype(int), rgb[..., 2].astype(int)
    rim = (dist < width) & (b > r + 8) & (rgb.min(2) > 120)
    rim = cv2.dilate(rim.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & (dist < width + 1)
    out = alpha.copy()
    out[rim] = 0
    return out


def cut(name, src, session):
    im = Image.open(src).convert("RGB")
    rgb = np.asarray(im).copy()
    bg, flat = backdrop(rgb.astype(int))
    notes = []
    if flat > 10:
        notes.append(f"the backdrop isn't flat (varies by {flat:.0f})")
    from rembg import remove
    ai = np.asarray(remove(im, session=session).convert("RGBA"))[..., 3].astype(np.uint8)
    dist = np.sqrt(((rgb.astype(int) - bg) ** 2).sum(2))
    k = (rgb.astype(int) * bg).sum(2) / (bg * bg).sum()
    shadow = (np.sqrt(((rgb - k[..., None] * bg) ** 2).sum(2)) < 14) & (k < 0.98) & (ai < 40)
    sure_bg = joined_to_edge(dist < SAME)
    alpha = np.maximum(ai, np.where(dist > KEY, 255, 0)).astype(np.uint8)
    alpha[(sure_bg & (ai < 160)) | shadow] = 0                     # rembg sure it's the object: kept (pale stone)
    fix = FIX.get(name, {})
    h, w = alpha.shape
    if fix.get("cut_below"):
        y = int(h * fix["cut_below"])
        ramp = np.clip((y - np.arange(h)) / 6.0, 0, 1)[:, None]          # a soft cut over 6 px
        alpha = (alpha * ramp).astype(np.uint8)
    alpha = biggest(alpha)
    if fix.get("rim"):
        alpha = biggest(remove_rim(rgb, alpha))
    # the edge: pulled in a pixel and softened, then the backdrop's colour taken out of what is see-through
    hard = cv2.erode((alpha > 127).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    alpha = np.minimum(alpha, cv2.GaussianBlur(hard, (3, 3), 0))
    a = alpha.astype(np.float32)[..., None] / 255
    clean = np.where(a > 0.02, (rgb.astype(np.float32) - (1 - a) * bg) / np.maximum(a, 0.02), 0)
    rgb = np.clip(np.where(a > 0.98, rgb, clean), 0, 255).astype(np.uint8)
    ys, xs = np.nonzero(alpha > 8)
    if xs.min() <= 2 or ys.min() <= 2 or xs.max() >= w - 3 or ys.max() >= h - 3:
        notes.append("it touches the picture's edge: part of it may be cut off")
    pad = 3
    x0, y0, x1, y1 = max(0, xs.min() - pad), max(0, ys.min() - pad), min(w, xs.max() + pad + 1), min(h, ys.max() + pad + 1)
    out = Image.fromarray(np.dstack([rgb, alpha])[y0:y1, x0:x1])
    s = min(1.0, MAX / max(out.size))
    if s < 1:
        out = out.resize((round(out.width * s), round(out.height * s)), Image.LANCZOS)
    return out, foot(np.asarray(out)[..., 3], "length" in env.ASSETS[name]), notes


def foot(alpha, long=False):
    """Where it touches the ground (px): the middle of its lowest band, or under a log's middle."""
    h, w = alpha.shape
    solid = alpha > 96
    ys, xs = np.nonzero(solid)
    if long:
        mid = int(round((xs.min() + xs.max()) / 2))
        band = solid[:, max(0, mid - 4):mid + 5].any(1)
        return [float(mid), float(np.nonzero(band)[0].max())]
    low = ys.max()
    sel = ys >= low - max(3, int(h * 0.15))       # the lower band, so a cluster stands on its middle
    return [round(float(xs[sel].mean()), 1), float(low)]


def main(pairs):
    from rembg import new_session
    session = new_session("isnet-general-use")
    cat = env.catalog()
    for pair in pairs:
        name, _, src = pair.partition("=")
        if name not in env.ASSETS:
            raise SystemExit(f"{name}: not in web/env.ASSETS")
        im, ft, notes = cut(name, src, session)
        out = os.path.join(ROOT, env.path(name))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.save(out, "WEBP", quality=90, method=6)
        cat[name] = {"w": im.width, "h": im.height, "foot": ft}
        print(f"{name}: {im.width} x {im.height}, foot {ft}" + (f"  !! {'; '.join(notes)}" if notes else ""))
    os.makedirs(os.path.dirname(env.CATALOG), exist_ok=True)
    with open(env.CATALOG, "w") as f:
        json.dump(dict(sorted(cat.items())), f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
