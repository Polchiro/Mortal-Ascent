"""Cut the townsfolk out of SHOAIB's Gemini pictures for the town hub (web/town.py NPCS "src", docs/town.md).

Each picture is one person standing on a plain grey-green backdrop. rembg (isnet-general-use) takes the backdrop away;
because it drops thin things (a spear's shaft), and small gaps it shuts in are filled, anything clearly off the backdrop's colour is kept as well. Anything
that isn't joined to the person (Gemini's sparkle in the corner) and the faint cast shadow are dropped, so the page's
own shadow sits under their feet. The result is cropped tight: feet at the bottom middle.

    python -m scripts.make_town_npcs gate=warden.png blacksmith=smith.png ...

Writes art/portraits/town/<key>.webp for each, and prints its size and whether it faces left or right (the page
expects right; a picture that faces left gets "flip": True in town.NPCS).
Needs numpy, Pillow and rembg.
"""
import os
import sys

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "portraits", "town")
HOLE = 400                       # see-through gaps smaller than this (px), shut in by the person, are filled
SOLID = 40                       # alpha below this is shadow or haze: gone
KEY = 38                         # colour distance from the backdrop that is surely the person


def components(mask):
    """Label 4-connected regions (no scipy): (labels, sizes)."""
    lab = np.zeros(mask.shape, np.int32)
    sizes = [0]
    h, w = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n = len(sizes)
        stack, lab[y0, x0], size = [(y0, x0)], n, 0
        while stack:
            y, x = stack.pop()
            size += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v, u = y + dy, x + dx
                if 0 <= v < h and 0 <= u < w and mask[v, u] and not lab[v, u]:
                    lab[v, u] = n
                    stack.append((v, u))
        sizes.append(size)
    return lab, sizes


def cut(path, session):
    from rembg import remove
    src = Image.open(path).convert("RGB")
    im = remove(src, session=session).convert("RGBA")
    a = np.asarray(im).copy()
    rgb = np.asarray(src).astype(np.int16)
    border = np.concatenate([rgb[:6].reshape(-1, 3), rgb[-6:].reshape(-1, 3), rgb[:, :6].reshape(-1, 3)])
    bg = np.median(border, 0)
    off = np.sqrt(((rgb - bg) ** 2).sum(2)) > KEY
    k = (rgb * bg).sum(2) / (bg * bg).sum()                       # how much of the backdrop's colour, and ...
    same_hue = np.sqrt(((rgb - k[..., None] * bg) ** 2).sum(2)) < 14
    off &= ~(same_hue & (k < 0.98) & (a[:, :, 3] < SOLID))         # ... a darker backdrop is its shadow: not her
    a[off, :3] = rgb[off]
    a[off, 3] = np.maximum(a[off, 3], 255)
    a[a[:, :, 3] < SOLID, 3] = 0
    lab, sizes = components(a[:, :, 3] > 0)
    main = int(np.argmax(sizes))
    keep = np.isin(lab, [i for i, s in enumerate(sizes) if i and (i == main or s > sizes[main] * 0.02)])
    a[~keep, 3] = 0
    gaps, gap_sizes = components(a[:, :, 3] == 0)                   # small shut-in gaps: a spearhead's pale middle
    edge = set(gaps[0]) | set(gaps[-1]) | set(gaps[:, 0]) | set(gaps[:, -1])
    fill = np.isin(gaps, [i for i, s in enumerate(gap_sizes) if i and i not in edge and s < HOLE])
    a[fill, :3], a[fill, 3] = rgb[fill], 255
    out = Image.fromarray(a)
    return out.crop(out.getbbox())


def facing(im):
    """'right' or 'left': which way the body leans, by where its weight sits (a rough guide, check by eye)."""
    a = np.asarray(im)[:, :, 3] > 0
    top = a[: a.shape[0] // 3]
    xs = np.nonzero(top)[1]
    return "right" if xs.mean() > a.shape[1] / 2 else "left"


def main(pairs):
    from rembg import new_session
    session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    for pair in pairs:
        key, _, path = pair.partition("=")
        im = cut(path, session)
        im.save(os.path.join(OUT, f"{key}.webp"), "WEBP", quality=90, method=6)
        print(f"{key}: {im.width} x {im.height}, leans {facing(im)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
