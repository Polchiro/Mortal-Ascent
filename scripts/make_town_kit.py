"""Cut the town's buildings and props out of SHOAIB's Gemini pictures (web/town.py BUILDINGS and PROPS, docs/town.md).

Each building picture is one building on its own square stone base, drawn at the town map's isometric angle, on a
plain grey-green backdrop. It is cut out as the townsfolk are (scripts/make_town_npcs.py: rembg plus a colour key,
the Gemini sparkle dropped). A base's stone is often near the backdrop's colour and comes away in rags, so the whole
base diamond is put back from the picture: its left, right and bottom corners as cut, and the top corner they imply.
Then the base's three lower corners are measured: left, right and bottom. The page fits
those corners onto the building's footprint on the ground, so the picture's own size doesn't matter. A building used
mirrored (its door turned from the bottom-right to the bottom-left) is saved mirrored too, as <name>_m.

Props (the well, the training dummies) come from one picture of several props on a shared stone floor: each is cropped
by hand (PROP_BOXES, in that picture's pixels), enlarged, cut out with rembg, and the floor's thin grid lines that
cling to it are opened away.

    python -m scripts.make_town_kit forge=forge.png herbshop=shop.png ... props=props.png

Writes art/maps/town/<name>.webp and art/maps/town/kit.json: for each picture its size and, for buildings, the
corners (left x, right x, bottom x and y). Needs numpy, Pillow and rembg.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from scripts import make_town_npcs as npc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "maps", "town")
PROP_BOXES = {"well": (455, 150, 580, 330), "dummy1": (195, 100, 285, 305), "dummy2": (305, 75, 395, 250)}


def corners(im):
    """The base's left and right corners (x) and its bottom corner (x, y), in the picture's pixels."""
    a = np.asarray(im)[:, :, 3] > 128
    ys, xs = np.nonzero(a)
    return {"l": int(xs.min()), "r": int(xs.max()), "bx": round(float(xs[ys == ys.max()].mean()), 1), "by": int(ys.max())}


def save(name, im, kit, base=True):
    im.save(os.path.join(OUT, f"{name}.webp"), "WEBP", quality=90, method=6)
    kit[name] = {"w": im.width, "h": im.height, **(corners(im) if base else {})}


def building(path, session):
    from PIL import ImageDraw
    old = npc.HOLE
    npc.HOLE = 2500                         # gaps a building shuts in (between its posts) are bigger than a person's
    try:
        im = npc.cut(path, session, crop=False)
    finally:
        npc.HOLE = old
    a = np.asarray(im)[:, :, 3] > 128
    ys, xs = np.nonzero(a)
    left = (xs.min(), ys[xs == xs.min()].mean())
    right = (xs.max(), ys[xs == xs.max()].mean())
    bottom = (xs[ys == ys.max()].mean(), ys.max())
    top = (left[0] + right[0] - bottom[0], left[1] + right[1] - bottom[1])
    base = Image.new("L", im.size, 0)
    ImageDraw.Draw(base).polygon([left, bottom, right, top], fill=255)
    src = Image.open(path).convert("RGBA")
    im = Image.composite(src, im, base)                    # the base diamond as painted, whole
    return im.crop(im.getbbox())


def prop(src, box, session):
    from rembg import remove
    x0, y0, x1, y1 = box
    im = remove(src.crop(box).resize(((x1 - x0) * 3, (y1 - y0) * 3), Image.LANCZOS), session=session).convert("RGBA")
    a = np.asarray(im).copy()
    a[a[:, :, 3] < 60, 3] = 0
    im = Image.fromarray(a)
    alpha = im.getchannel("A")
    opened = alpha.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))   # grid lines under 7 px go
    im.putalpha(Image.composite(alpha, Image.new("L", alpha.size, 0), opened.point(lambda v: 255 if v else 0)))
    return im.crop(im.getbbox())


def main(pairs):
    from rembg import new_session
    from web import town
    session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "kit.json")
    kit = json.load(open(path)) if os.path.exists(path) else {}
    mirrored = {b["img"] for b in town.BUILDINGS if b.get("mirror")}
    for pair in pairs:
        name, _, src = pair.partition("=")
        if name == "props":
            whole = Image.open(src).convert("RGB")
            for key, box in PROP_BOXES.items():
                save(key, prop(whole, box, session), kit, base=False)
            continue
        im = building(src, session)
        save(name, im, kit)
        if name in mirrored:
            save(name + "_m", ImageOps.mirror(im), kit)
    json.dump(kit, open(path, "w"), indent=1, sort_keys=True)
    print(f"wrote {len(kit)} pictures to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
