"""Build the female cultivator's walk for the hunting-ground map (looks.WALK_SHEETS, web/static/huntmap.js) from
SHOAIB's five walk videos (docs/hunting.md "The map").

Each video (Gemini, 24 fps, 10 s, 1280 x 720 or 720 x 1280) is her walking in place facing ONE way, camera fixed,
on a plain grey-green backdrop: front (S), front-right (SE), right (E), back-right (NE) and back (N). She never
faces left, so SW, W and NW are her SE, E and NE mirrored. In each video the script finds the stride (two steps)
whose last frame best meets its first, takes 8 frames from it, cuts her out, and lines every frame up on the same
spot between her feet.

    python -m scripts.make_heroine_walk front.mp4 front_right.mp4 right.mp4 back_right.mp4 back.mp4

Writes art/portraits/map/hero_female_walk.webp: the spec sheet, 8 rows (S SW W NW N NE E SE) x 8 frames, cells
256 x 256, the point between the feet at (128, 232), about 200 px tall, and prints each row's standing frame
(feet closest together) for looks.WALK_SHEETS["female"]["stand"].
Needs ffmpeg, numpy, scipy, Pillow and rembg (the isnet-general-use model).
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

from scripts.make_hero_walk import CELL, FEET, HEIGHT, MIRROR, ORDER, check, feet_spread

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "portraits", "map",
                   "hero_female_walk.webp")
VIEWS = ["S", "SE", "E", "NE", "N"]     # the order the videos are given in
SKIP = {"NE": 84}                       # her back-right video turns round for its first 3.5 s
STRIDE = (36, 64)                       # frames in one stride, at most and least


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", video], capture_output=True, text=True, check=True).stdout
    w, h = (int(v) for v in out.strip().split(","))
    return w, h


def raw(video, w, h, vf=None):
    args = ["ffmpeg", "-v", "error", "-i", video]
    if vf:
        args += ["-vf", vf]
    data = subprocess.run(args + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(data, np.uint8).reshape(-1, h, w, 3)


def stride(video, skip, span=STRIDE):
    """(first frame, frames) of the stride (or breath) that loops best, `span` frames long at least and most."""
    small = raw(video, 90, 160, "scale=90:160").astype(float).mean(3)
    best = None
    for a in range(skip, len(small) - span[0]):
        for n in range(span[0], min(span[1], len(small) - a)):
            d = np.abs(small[a] - small[a + n]).mean()
            if best is None or d < best[0]:
                best = (d, a, n)
    return best[1], best[2]


def cut(frames, session):
    """Her, cut out: the biggest piece rembg keeps (the Gemini mark in the corner goes)."""
    from rembg import remove
    out = []
    for f in frames:
        im = remove(Image.fromarray(f), session=session).convert("RGBA")
        a = np.asarray(im).copy()
        lab, n = ndimage.label(a[:, :, 3] > 40)
        if n > 1:
            keep = 1 + int(np.argmax(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))))
            a[lab != keep, 3] = 0
        out.append(Image.fromarray(a))
    return out


def row(cuts):
    """8 cells, every frame scaled alike so she is HEIGHT tall, her feet on FEET."""
    boxes = [np.nonzero(np.asarray(c)[:, :, 3] > 100) for c in cuts]
    top = np.median([ys.min() for ys, _ in boxes])
    bottom = np.median([ys.max() for ys, _ in boxes])
    mid = np.median([(xs.min() + xs.max()) / 2 for _, xs in boxes])
    scale = HEIGHT / (bottom - top)
    cells = []
    for c in cuts:
        im = c.resize((round(c.width * scale), round(c.height * scale)), Image.LANCZOS)
        cell = Image.new("RGBA", (CELL, CELL))
        cell.alpha_composite(im, (round(FEET[0] - mid * scale), round(FEET[1] - bottom * scale)))
        cells.append(cell)
    return cells


def main(videos):
    if len(videos) != len(VIEWS):
        sys.exit(f"give the five videos in this order: {', '.join(VIEWS)}")
    from rembg import new_session
    session = new_session("isnet-general-use")
    rows, stand = {}, {}
    for view, video in zip(VIEWS, videos):
        w, h = probe(video)
        a, n = stride(video, SKIP.get(view, 0))
        frames = raw(video, w, h)
        picked = [frames[a + round(j * n / 8)] for j in range(8)]
        cuts = cut(picked, session)
        rows[view] = row(cuts)
        stand[view] = min(range(8), key=lambda j: feet_spread(rows[view][j]))
        print(f"{view}: frames {a}-{a + n}")
    out = Image.new("RGBA", (CELL * 8, CELL * 8))
    for r, d in enumerate(ORDER):
        for j, cell in enumerate(rows[MIRROR.get(d, d)]):
            out.alpha_composite(ImageOps.mirror(cell) if d in MIRROR else cell, (j * CELL, r * CELL))
    bad = check(out)
    if bad:
        sys.exit("The sheet does not meet the spec:\n  " + "\n  ".join(bad))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, "WEBP", quality=88, method=6)
    print(f"wrote {OUT}; stand frames per row ({' '.join(ORDER)}): {[stand[MIRROR.get(d, d)] for d in ORDER]}")


if __name__ == "__main__":
    main(sys.argv[1:])
