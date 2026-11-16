"""Cut the town's buildings and props out of SHOAIB's Gemini pictures (web/town.py BUILDINGS and PROPS, docs/town.md).

Each building picture is one building on its own square stone base, drawn at the town map's isometric angle, on a
plain grey-green backdrop. It is cut out as the townsfolk are (scripts/make_town_npcs.py: rembg plus a colour key,
the Gemini sparkle dropped). A base's stone is often near the backdrop's colour and comes away in rags, so the whole
base diamond is put back from the picture: its left, right and bottom corners as cut, and the top corner they imply.
Then the base's three lower corners are measured: left, right and bottom. The page fits
those corners onto the building's footprint on the ground, so the picture's own size doesn't matter. A building used
is saved both ways round: as drawn, and mirrored (<name>_m: its door turned from the bottom-right to the bottom-left).

Nature and small props (FLUSH: the pond, trees, boulders, the bush, the racks and barrels) were drawn on little
slabs of ground. Their slab sides are trimmed away, so they sit flush on the ground, their top surface's edge
feathered into it; their base is measured on the lowest part of the picture only (BAND: a canopy is wider than its roots).

The wall picture is one corner of wall: a long arm and a short return. The arm is straightened (its footing and
roof run at WALL["slope"] in the picture; sheared to the map's exact 0.5), and two one-tile slices are cut from it:
plain (wall_s) and with a lantern (wall_l), their footing's start at their bottom-left. Laid one per tile they make
a straight, unbroken wall of any length (web/town.py wall_line); their face looks to the bottom-right, mirrored
(_m) to the bottom-left.

The well comes from one picture of several props on a shared stone floor: each is cropped
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
PROP_BOXES = {"well": (455, 150, 580, 330)}
FLUSH = {"pond", "pine", "blossom", "boulders", "bush", "rack", "barrels", "herbrack"}
BAND = {"pine": 0.3, "blossom": 0.3}      # where the base is looked for: the lowest share of the picture (trees: low)
# a base whose stone is so close to the backdrop that the cut-out loses most of it: its corners in the picture
# (left, right, bottom), measured by hand, so the floor is put back whole and where it really is
BASES = {"stalls": ((150, 336), (868, 334.5), (507.5, 534))}
SLOPE = 0.58                        # Gemini draws its tiles a little steeper than 2:1
WALL = {"slope": 0.478, "foot": 647.5, "plain": 520, "lantern": 650, "tile": 64, "overlap": 3}   # px, measured


def corners(im):
    """The base's left and right corners (x) and its bottom corner (x, y), in the picture's pixels."""
    a = np.asarray(im)[:, :, 3] > 128
    ys, xs = np.nonzero(a)
    return {"l": int(xs.min()), "r": int(xs.max()), "bx": round(float(xs[ys == ys.max()].mean()), 1), "by": int(ys.max())}


def save(name, im, kit, base=True):
    im.save(os.path.join(OUT, f"{name}.webp"), "WEBP", quality=90, method=6)
    kit[name] = {"w": im.width, "h": im.height, **(corners(im) if base else {})}


def building(path, session, corners_at=None):
    from PIL import ImageDraw
    old = npc.HOLE
    npc.HOLE = 2500                         # gaps a building shuts in (between its posts) are bigger than a person's
    try:
        im = npc.cut(path, session, crop=False)
    finally:
        npc.HOLE = old
    if corners_at:
        left, right, bottom = corners_at
    else:
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
    if corners_at:                                         # nothing outside the base's own outline below its top
        a = np.asarray(im).copy()
        yy, xx = np.mgrid[0:im.height, 0:im.width]
        a[(yy > min(left[1], right[1])) & ((xx < left[0]) | (xx > right[0]) | (np.asarray(base) == 0)), 3] = 0
        im = Image.fromarray(a)
    return im.crop(im.getbbox())


def flush(path, session, band=0.65):
    """A piece drawn on a slab of ground: the slab's sides trimmed away below its top face, the edge feathered."""
    from PIL import ImageDraw
    im = npc.cut(path, session, crop=False)       # small gaps only: a rack's open frame stays open
    a = np.asarray(im)[:, :, 3] > 128
    ys, xs = np.nonzero(a)
    low = a.copy()
    low[: ys.max() - int((ys.max() - ys.min()) * band)] = False         # the base: the picture's lowest part
    ly, lx = np.nonzero(low)
    left, right = lx.min(), lx.max()
    # the top face's side corners: the highest point near each side (Gemini draws a slab a little wider at its foot,
    # so the outermost pixel is the foot's corner, not the top's)
    near = int((right - left) * 0.03)
    L = (left, ly[lx <= left + near].min())
    R = (right, ly[lx >= right - near].min())
    # the top face's bottom corner: below the middle of L and R by half their distance times Gemini's tile slope
    # (about 0.58, measured on the ground tiles), and never below the picture's lowest point
    B = (float(lx[ly == ly.max()].mean()), min(ly.max(), (L[1] + R[1]) / 2 + (R[0] - L[0]) / 2 * SLOPE))
    keep = Image.new("L", im.size, 0)
    ImageDraw.Draw(keep).polygon([(0, 0), (im.width, 0), (im.width, R[1]), R, B, L, (0, L[1])], fill=255)
    keep = keep.filter(ImageFilter.GaussianBlur(3))
    alpha = Image.fromarray(np.minimum(np.asarray(im.getchannel("A")), np.asarray(keep)).astype(np.uint8))
    im.putalpha(alpha)
    box = im.getbbox()
    im = im.crop(box)
    return im, {"l": int(L[0] - box[0]), "r": int(R[0] - box[0]), "bx": round(B[0] - box[0], 1), "by": int(B[1] - box[1])}


def wall_slices(path, session):
    """The wall's one-tile slices (name, picture, corners as a 0.6 x 1 tile footprint's)."""
    im = npc.cut(path, session, crop=False)
    k = 0.5 - WALL["slope"]
    im = im.transform(im.size, Image.AFFINE, (1, 0, 0, k, 1, 0), Image.BICUBIC)   # footing now: foot - 0.5 x
    out = []
    for name, x in (("wall_s", WALL["plain"]), ("wall_l", WALL["lantern"])):
        t = WALL["tile"]
        strip = im.crop((x, 0, x + t + WALL["overlap"], im.height))
        box = strip.getbbox()
        strip = strip.crop((0, box[1], strip.width, box[3]))
        by = WALL["foot"] - 0.5 * x - box[1]
        out.append((name, strip, {"l": round(-0.6 * t, 1), "r": t, "bx": 0, "by": round(by, 1)}))
    return out


def mirrored(im, c):
    w = im.width
    return ImageOps.mirror(im), {"l": w - 1 - c["r"], "r": w - 1 - c["l"], "bx": round(w - 1 - c["bx"], 1), "by": c["by"]}


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
    session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "kit.json")
    kit = json.load(open(path)) if os.path.exists(path) else {}
    for pair in pairs:
        name, _, src = pair.partition("=")
        if name == "props":
            whole = Image.open(src).convert("RGB")
            for key, box in PROP_BOXES.items():
                save(key, prop(whole, box, session), kit, base=False)
            continue
        if name in FLUSH or name == "wall":
            pieces = wall_slices(src, session) if name == "wall" else [(name, *flush(src, session, BAND.get(name, 0.65)))]
            for base, im, c in pieces:
                for n, (pic, cc) in ((base, (im, c)), (base + "_m", mirrored(im, c))):   # both ways round
                    pic.save(os.path.join(OUT, f"{n}.webp"), "WEBP", quality=90, method=6)
                    kit[n] = {"w": pic.width, "h": pic.height, **cc}
            continue
        im = building(src, session, BASES.get(name))
        save(name, im, kit)
        save(name + "_m", ImageOps.mirror(im), kit)
    json.dump(kit, open(path, "w"), indent=1, sort_keys=True)
    print(f"wrote {len(kit)} pictures to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
