"""Cut SHOAIB's painted pills (Nov 26 2026) into the game's pill icons (docs/alchemy.md "Pill pictures").

    python -m scripts.make_pill_art qi=grid.png burst=grid.png mending=grid.png cleansing=grid.png \
                                    breakthrough=grid.png [qi_heaven=one.png ...]

Each grid is 3 x 2 cells read left to right, top row first: the kind's five grades, Mortal to Heaven; the Qi grid
holds the Heaven-Defying Pill in its sixth cell (the others leave it empty). A single picture (`<kind>_<grade>` or
`heaven_defying`) replaces one pill. A source may end in @x,y,r;... to paint Gemini's sparkle out where it touches a
pill (shares of the picture, as scripts/make_gather_art).

Every pill is cut off its flat grey backdrop in two parts (`cut_pill`): the round pill itself, found as a circle,
kept whole with a clean edge; and around it whatever is lighter than the backdrop (its glow, mist and sparks) lifted
off as light, so no grey is left round a glowing pill. A rough Mortal pill's lumps outside the circle are kept as
rembg finds them. It is fitted into a transparent ICON x ICON square with no ring, and written to art/icons/pills/<kind>_<grade>.webp, where
cards/art_icons.resolve finds it for "emblem:pill:<kind>:<grade>": the Discord cards and the website show it from
there. The pattern dots (纹) are still drawn under it by the cards (cards/theme.painted).

The source files are only read. Needs numpy, opencv, Pillow and rembg (isnet-general-use).
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "icons", "pills")
ICON = 256                   # the square's side (px)
PILL = 0.78                  # the pill's width, as a share of the square (glow and mist round it)
GRADES = ("mortal", "yellow", "mystic", "earth", "heaven")
KINDS = ("qi", "burst", "mending", "cleansing", "breakthrough")
GRIDS = {k: [f"{k}_{g}" for g in GRADES] + (["heaven_defying"] if k == "qi" else []) for k in KINDS}
SINGLES = {n for names in GRIDS.values() for n in names}


def square(cell, at):
    """The pill centred in a transparent ICON x ICON square, every pill the same size (its circle PILL of the
    square's side) so the grades line up; glow and mist reach out round it and fade before the square's edge."""
    x, y, r = at
    k = ICON * PILL / (2 * r)
    big = cell.resize((round(cell.width * k), round(cell.height * k)), Image.LANCZOS)
    out = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    out.alpha_composite(big, (round(ICON / 2 - x * k), round(ICON / 2 - y * k)))
    a = np.asarray(out).astype(np.float32)
    yy, xx = np.mgrid[0:ICON, 0:ICON]
    d = np.sqrt((xx - ICON / 2 + 0.5) ** 2 + (yy - ICON / 2 + 0.5) ** 2) / (ICON / 2)
    a[..., 3] *= np.clip((1.0 - d) / 0.12, 0, 1)        # mist fades out before the edge
    return Image.fromarray(a.astype(np.uint8))


def circle(rgb):
    """(x, y, r) of the pill in a cell, or None."""
    g = cv2.medianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), 5)
    h, w = g.shape
    c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=w, param1=60, param2=30,
                         minRadius=int(h * 0.25), maxRadius=int(h * 0.42))
    if c is None:
        return None
    x, y, r = c[0][0]
    return float(x), float(y), float(r)


def cut_pill(im, session):
    """One pill off its flat backdrop (see the module notes): (the cell as RGBA, the pill's circle (x, y, r))."""
    from rembg import remove

    from scripts import make_env_assets as mea
    rgb = np.asarray(im.convert("RGB"))
    f = rgb.astype(np.float32)
    bg, _ = mea.backdrop(f)
    ai = np.asarray(remove(im, session=session).convert("RGBA"))[..., 3].astype(np.float32) / 255
    h, w = ai.shape
    yy, xx = np.mgrid[0:h, 0:w]
    found = circle(rgb)
    if found is None:                                   # no clean circle: as rembg finds it, sized by its extent
        ys, xs = np.nonzero(ai > 0.5)
        x, y, r = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2, max(np.ptp(xs), np.ptp(ys)) / 2
        inside = ai
    else:
        x, y, r = found
        d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
        inside = np.clip(r + 0.5 - d, 0, 1)             # the pill: whole, its edge smoothed over one pixel ...
        solid = np.maximum(np.clip(ai * 1.5, 0, 1), (np.sqrt(((f - bg) ** 2).sum(2)) > mea.KEY).astype(np.float32))
        inside = inside * np.where(d > r * 0.9, solid, 1)     # ... but a rough pill's dents show the backdrop
    # light round it (glow, mist, sparks): how far above the backdrop it rises, as light laid over grey
    over = np.clip((f - bg) / np.maximum(255 - bg, 1), 0, 1).max(2)
    glow = np.clip((over - 0.06) / 0.94, 0, 1)        # (the backdrop itself varies a little)
    # a rough pill's lumps outside the circle: rembg's, where the colour is clearly not the backdrop
    far = np.sqrt(((f - bg) ** 2).sum(2)) > mea.KEY
    lumps = np.where(far & (over < 0.06), ai, 0)
    near = np.sqrt((xx - x) ** 2 + (yy - y) ** 2) < r * 1.45
    a = np.maximum(inside, np.where(near, np.maximum(glow, lumps), 0))
    col = np.where(a[..., None] > 0.02, (f - (1 - a[..., None]) * bg) / np.maximum(a[..., None], 0.02), 0)
    col = np.where(inside[..., None] > 0.99, f, col)
    out = np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8)
    return Image.fromarray(out), (x, y, r)


def main(args):
    from rembg import new_session

    from scripts.make_gather_art import pairs, unsparkle
    session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    for name, (src, spots) in pairs(args).items():
        im = Image.open(src).convert("RGB")
        if spots:
            im = unsparkle(im, spots)
        if name in GRIDS:
            w, h = im.size
            cells = [(n, im.crop(((i % 3) * w // 3, (i // 3) * h // 2, (i % 3 + 1) * w // 3, (i // 3 + 1) * h // 2)))
                     for i, n in enumerate(GRIDS[name])]
        elif name in SINGLES:
            cells = [(name, im)]
        else:
            raise SystemExit(f"{name}: not a grid ({', '.join(GRIDS)}) or a pill ({', '.join(sorted(SINGLES))})")
        for n, pic in cells:
            cell, at = cut_pill(pic, session)
            square(cell, at).save(os.path.join(OUT, n + ".webp"), "WEBP", quality=90, method=6)
            print(f"{n}: pill radius {at[2]:.0f} px", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
