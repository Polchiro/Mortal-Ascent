"""Cut the World Map scroll out of SHOAIB's Gemini picture (web/world.py, docs/world.md).

The picture is a painted silk scroll on a plain grey backdrop. The scroll is cut out with GrabCut (the backdrop's
soft light gradient defeats a simple colour key), its edge feathered a little, and Gemini's sparkle (a pale four-pointed star near the bottom-right) is painted over from the
parchment around it. What is left is the scroll alone, see-through round it, so it sits on the page's dark ground.

    python -m scripts.make_world_map map.png [sparkle=x,y,r]

`sparkle` is where the star is (its middle and radius, in the picture's pixels); without it, it is looked for in the
bottom-right quarter. Writes art/maps/world.webp. Needs numpy, Pillow and opencv.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "maps", "world.webp")


def scroll_mask(rgb):
    """The scroll (1) against the grey backdrop (0): GrabCut started from a guess (grey pixels: probably backdrop; the picture's side
    edges: backdrop), then the one largest piece kept, its holes filled and its edge smoothed (closing nibbles in the paper)."""
    h, w = rgb.shape[:2]
    q = rgb.astype(int)
    grey = (q.max(2) - q.min(2) < 16) & (q.min(2) > 80) & (q.max(2) < 150)
    mask = np.where(grey, cv2.GC_PR_BGD, cv2.GC_PR_FGD).astype(np.uint8)
    mask[:, :2] = mask[:, -2:] = cv2.GC_BGD                       # the picture's left and right edges: backdrop
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(rgb, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
    fg = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    P = 48                                                         # padded, so closing doesn't reach the edges
    fg = np.pad(fg, P)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    for k in ((41, 1), (1, 41)):                                   # the paper's straight edges: no nibbles
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones(k[::-1], np.uint8))
    fg = np.ascontiguousarray(fg[P:-P, P:-P])
    fg = cv2.erode(fg, np.ones((3, 3), np.uint8))                 # no grey rim
    n, lab, st, _ = cv2.connectedComponentsWithStats(1 - fg)
    for i in range(1, n):                                          # holes: not touching the picture's edge
        x, y, ww, hh, _a = st[i]
        if x > 0 and y > 0 and x + ww < w and y + hh < h:
            fg[lab == i] = 1
    return fg


def find_sparkle(rgb):
    """The sparkle's middle and radius: the largest flat grey blob in the corner where Gemini puts it (just inside the
    parchment's bottom-right corner: X, Y, shares of the picture)."""
    h, w = rgb.shape[:2]
    x0, x1, y0, y1 = int(w * .82), int(w * .96), int(h * .74), int(h * .93)
    q = cv2.GaussianBlur(rgb[y0:y1, x0:x1], (5, 5), 0).astype(int)
    pale = (q.min(2) > 100) & (q.max(2) - q.min(2) < 24)
    pale = cv2.morphologyEx(pale.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, cents = cv2.connectedComponentsWithStats(pale)
    if n < 2:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[i, cv2.CC_STAT_AREA] < 80:
        return None
    cx, cy = cents[i]
    r = max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]) / 2 + 4
    return round(cx + x0, 1), round(cy + y0, 1), r


def make(src, sparkle=None):
    rgb = np.asarray(Image.open(src).convert("RGB")).copy()
    sp = sparkle or find_sparkle(rgb)
    if sp:
        x, y, r = sp
        hole = np.zeros(rgb.shape[:2], np.uint8)
        cv2.circle(hole, (round(x), round(y)), round(r), 255, -1)
        rgb = cv2.inpaint(rgb, hole, 7, cv2.INPAINT_TELEA)
    alpha = scroll_mask(rgb) * 255
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)                   # a soft, not jagged, edge
    ys, xs = np.where(alpha > 8)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    out = Image.fromarray(np.dstack([rgb, alpha])).crop(box)
    out.save(OUT, "WEBP", quality=92, method=6)
    return out.size, sp


if __name__ == "__main__":
    args = sys.argv[1:]
    sp = next((tuple(float(v) for v in a.split("=", 1)[1].split(",")) for a in args if a.startswith("sparkle=")), None)
    size, where = make(args[0], sp)
    print(f"{OUT}: {size[0]} x {size[1]}, sparkle at {where}")
