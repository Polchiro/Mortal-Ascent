"""Cut SHOAIB's painted gear, artifacts, manuals and technique icons (Nov 26 2026) into the game's icons
(docs/equipment.md "Pictures").

    python -m scripts.make_item_art items  swords=grid.png ... hunter=grid.png attack=grid.png defense=grid.png \
                                           "Sea-Calming Pillar=one.png" ...
    python -m scripts.make_item_art skills mortal=grid.png yellow=grid.png mystic=grid.png earth=grid.png heaven=grid.png \
                                           iron_fist=one.png

items   A grid holds five things (a gear kind's or an artifact family's five tiers, or five manual grades), read left
        to right, top row first. Gemini doesn't always keep to its cells (items across the lines, pairs, grid
        lines drawn in), so: a tidy grid (CELLS) is cut one thing to a cell; an untidy one has a box per thing
        placed by hand (BOXES, in a 1376 x 768 picture; BLANK greys out a neighbour's bits in it); any other is
        searched whole: rembg marks what isn't backdrop (the empty sixth cell, with Gemini's mark, greyed out
        first), pieces close together are joined (a pendant and its chain, a pair), and the five largest are
        put in reading order, each with the others greyed out. A single picture named
        after one item (its game name) replaces it.
        Each is cut off the grey as the herbs are (rembg plus a colour key, the backdrop's colour taken out of the
        edges; all its pieces kept, so a pair stays a pair), fitted into a clear ICON x ICON square and written to
        art/icons/gear/<slug of its name>.webp (weapons, armor, artifacts: cards/art_icons.gear) or
        art/icons/manuals/<attack|defense>_<grade>.webp (manuals: art_icons.resolve "emblem:manual:...").
skills  A grade's six techniques as painted panels on grey: three attacks on top, three defences below, in
        technique.TECHNIQUES' order. Each panel is cropped square from its middle, made a round medallion with a
        thin gold rim, and written to art/icons/tech/<key>.webp: the skill icon on the Techniques page, the
        cards' round badges and the fight buttons (bot/emojis.py uploads the new pictures by itself). A single
        picture named by a technique's key replaces that one icon.

A source may end in @x,y,r;... to paint Gemini's sparkle out first (shares of the picture, as make_gather_art).
The source files are only read. Needs numpy, opencv, Pillow and rembg (isnet-general-use).
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

import equipments as eq
import technique
from scripts import make_env_assets as mea

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "art", "icons")
ICON = 256
FILL = 0.9                    # an item's longest side, as a share of the square
GRADES = ("Mortal", "Yellow", "Mystic", "Earth", "Heaven")

GEAR = {"swords": ("weapon", "sword"), "sabers": ("weapon", "saber"), "spears": ("weapon", "spear"),
        "staffs": ("weapon", "staff"), "gauntlets": ("weapon", "gauntlets"), "robes": ("armor", "robe"),
        "plate": ("armor", "plate"), "hides": ("armor", "hide"), "vests": ("armor", "vest")}
FAMILIES = {"fangs": "fang", "bells": "bell", "mirrors": "mirror", "thunder": "thunder", "lotus": "lotus",
            "feathers": "feather", "focus": "focus", "qi": "qi", "purity": "purity", "furnace": "furnace",
            "gourds": "gourd", "insight": "insight", "compasses": "compass", "fortune": "fortune", "hunter": "hunter"}


# where Gemini didn't keep to the grid: each thing's box (x0, y0, x1, y1), and grey painted over a neighbour's bits
CELLS = {"swords", "sabers", "staffs", "robes", "vests", "attack", "defense", "thunder", "lotus", "furnace",
         "gourds"}    # tidy: one to a cell
BOXES = {                                                                          # untidy: placed by hand
    "gauntlets": [(40, 0, 440, 384), (450, 0, 915, 384), (920, 0, 1376, 384),       # three singles,
                  (40, 384, 690, 768), (690, 384, 1205, 768)],                       # then two pairs across the cells
    "bells": [(0, 0, 458, 384), (540, 0, 800, 480), (917, 0, 1376, 384), (0, 384, 458, 768), (480, 392, 960, 768)],
    "spears": [(0, 0, 458, 384), (461, 0, 914, 384), (917, 0, 1376, 384), (0, 384, 458, 768),
               (461, 388, 914, 768)],                          # (its starburst was drawn cut off at the grid lines)
    "mirrors": [(110, 0, 440, 340), (540, 0, 900, 340), (980, 0, 1310, 340), (330, 350, 640, 720),
                (650, 320, 1080, 768)],
    "purity": [(110, 0, 440, 340), (560, 0, 880, 340), (990, 0, 1300, 340), (300, 360, 600, 720),
               (660, 350, 1040, 720)],
    "feathers": [(100, 0, 460, 380), (520, 0, 900, 380), (950, 0, 1330, 380), (20, 370, 510, 768),
                 (510, 370, 940, 768)],
    "qi": [(100, 0, 460, 380), (540, 0, 900, 380), (960, 0, 1290, 380), (100, 340, 560, 720), (560, 340, 960, 720)],
    "compasses": [(100, 10, 430, 340), (520, 0, 910, 340), (980, 10, 1310, 340), (80, 360, 460, 740),
                  (590, 360, 1220, 750)],
    "focus": [(100, 0, 460, 380), (540, 0, 900, 380), (980, 0, 1330, 380), (60, 370, 500, 720), (580, 340, 940, 740)],
}
BLANK = {("bells", 1): [(662, 386, 800, 480)],      # the copper bell's box: the chaos bell's flames below it
         ("bells", 4): [(578, 392, 660, 482)],      # the chaos bell's box: the copper bell's tassel above it
         ("feathers", 0): [(300, 300, 460, 380)]}   # the sparrow feather's box: the ribbon's glow below it  


def slug(name):
    from cards.art_icons import slug as s
    return s(name)


def grid_items(grid):
    """The five (name, file) a grid holds, in reading order."""
    if grid in ("attack", "defense"):
        return [(f"{grid} {g}", os.path.join(ICONS, "manuals", f"{grid}_{g.lower()}.webp")) for g in GRADES]
    if grid in GEAR:
        part, kind = GEAR[grid]
        names = [(eq.WEAPON_NAMES if part == "weapon" else eq.ARMOR_NAMES)[t][kind] for t in eq.TIERS]
    elif grid in FAMILIES:
        names = [eq.artifact_name(FAMILIES[grid], t) for t in eq.TIERS]
    else:
        raise SystemExit(f"{grid}: not a grid")
    return [(n, os.path.join(ICONS, "gear", slug(n) + ".webp")) for n in names]


def single(name):
    """(name, file) for one item named as in the game, or None."""
    for grid in list(GEAR) + list(FAMILIES) + ["attack", "defense"]:
        for n, path in grid_items(grid):
            if n.lower() == name.lower():
                return n, path
    return None


def no_lines(far):
    """Grid lines Gemini drew: rows and columns mostly unlike the backdrop, taken out."""
    far = far.copy()
    rows = far.mean(1) > 0.5
    cols = far.mean(0) > 0.5
    for r in np.nonzero(rows)[0]:
        far[max(0, r - 2):r + 3] = False
    for c in np.nonzero(cols)[0]:
        far[:, max(0, c - 2):c + 3] = False
    return far


def found(im, session, join=31):
    """The five things on a grid picture, in reading order: (box (x0, y0, x1, y1), where it lies (a mask))."""
    from rembg import remove
    a = np.asarray(remove(im, session=session).convert("RGBA"))[..., 3]
    m = cv2.dilate((a > 60).astype(np.uint8), np.ones((join, join), np.uint8))
    k, lab, st, _ = cv2.connectedComponentsWithStats(m)
    order = sorted(range(1, k), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:5]
    things = [((st[i, 0], st[i, 1], st[i, 0] + st[i, 2], st[i, 1] + st[i, 3]), lab == i) for i in order]
    h = a.shape[0]
    return sorted(things, key=lambda t: (((t[0][1] + t[0][3]) / 2) > h / 2, (t[0][0] + t[0][2]) / 2))


def unline(im):
    """Grid lines Gemini drew, painted out of the whole picture (filled from around them)."""
    rgb = np.asarray(im.convert("RGB"))
    bg, _ = mea.backdrop(rgb.astype(int))
    far = np.sqrt(((rgb.astype(int) - bg) ** 2).sum(2)) > mea.KEY
    m = np.zeros(far.shape, np.uint8)

    def thin(frac):                                        # a line: mostly unlike the backdrop, with plain either side
        n = len(frac)
        return [i for i in np.nonzero(frac > 0.5)[0]
                if frac[max(0, i - 7)] < frac[i] - 0.3 and frac[min(n - 1, i + 7)] < frac[i] - 0.3]
    for r in thin(far.mean(1)):
        m[max(0, r - 2):r + 3] = 255
    for c in thin(far.mean(0)):
        m[:, max(0, c - 2):c + 3] = 255
    if not m.any():
        return im
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return Image.fromarray(cv2.cvtColor(cv2.inpaint(bgr, m, 5, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB))


def cut(im, session):
    """One item off its grey: RGBA cropped to it. As scripts/make_gather_art.cut, but every sizeable piece is kept
    (a pair of gauntlets, a fan's loose feather) and nothing is resized."""
    from rembg import remove
    rgb = np.asarray(im.convert("RGB")).copy()
    bg, _ = mea.backdrop(rgb.astype(int))
    ai = np.asarray(remove(im.convert("RGB"), session=session).convert("RGBA"))[..., 3].astype(np.uint8)
    dist = np.sqrt(((rgb.astype(int) - bg) ** 2).sum(2))
    sure_bg = mea.joined_to_edge(dist < mea.SAME)
    alpha = np.maximum(ai, np.where(no_lines(dist > mea.KEY), 255, 0)).astype(np.uint8)
    alpha[sure_bg & (ai < 160)] = 0
    k, lab, st, _ = cv2.connectedComponentsWithStats((alpha > 24).astype(np.uint8))
    if k > 2:                                              # drop specks and the sparkle, keep every real piece
        big = st[1:, cv2.CC_STAT_AREA].max()
        keep = [i for i in range(1, k) if st[i, cv2.CC_STAT_AREA] >= big * 0.04]
        alpha[~np.isin(lab, keep)] = 0
    hard = cv2.erode((alpha > 127).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    alpha = np.minimum(alpha, cv2.GaussianBlur(hard, (3, 3), 0))
    h, w = alpha.shape                                     # a glow cut off at the box's edge fades out instead
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    alpha = (alpha * np.clip(edge / 14.0, 0, 1)).astype(np.uint8)
    a = alpha.astype(np.float32)[..., None] / 255
    clean = np.where(a > 0.02, (rgb.astype(np.float32) - (1 - a) * bg) / np.maximum(a, 0.02), 0)
    rgb = np.clip(np.where(a > 0.98, rgb, clean), 0, 255).astype(np.uint8)
    ys, xs = np.nonzero(alpha > 8)
    return Image.fromarray(np.dstack([rgb, alpha])[ys.min():ys.max() + 1, xs.min():xs.max() + 1])


def square(obj):
    s = ICON * FILL / max(obj.size)
    obj = obj.resize((max(1, round(obj.width * s)), max(1, round(obj.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    out.alpha_composite(obj, ((ICON - obj.width) // 2, (ICON - obj.height) // 2))
    return out


def items(args):
    from rembg import new_session

    from scripts.make_gather_art import pairs, unsparkle
    session = new_session("isnet-general-use")
    for name, (src, spots) in pairs(args).items():
        im = Image.open(src).convert("RGB")
        if spots:
            im = unsparkle(im, spots)
        im = unline(im)
        one = single(name)
        if one:
            jobs = [(one, im)]
        else:
            want = grid_items(name)
            w, h = im.size
            bg = tuple(int(v) for v in np.median(np.asarray(im)[:8].reshape(-1, 3), 0))
            if name in BOXES:                               # placed by hand
                things = [(box, None) for box in BOXES[name]]
            elif name in CELLS:                             # one to a cell
                things = [(((i % 3) * w // 3 + 3, (i // 3) * h // 2 + 3, (i % 3 + 1) * w // 3 - 3,
                            (i // 3 + 1) * h // 2 - 3), None) for i in range(5)]
            else:
                ImageDraw.Draw(im).rectangle((w * 2 // 3 + 2, h // 2 + 2, w, h), fill=bg)   # the empty sixth cell
                things = found(im, session)
            if len(things) != 5:
                raise SystemExit(f"{name}: found {len(things)} things, not 5")
            pad = 22
            jobs = []
            for i, (item, (box, mask)) in enumerate(zip(want, things)):
                arr = np.asarray(im).copy()
                for j, (_, other) in enumerate(things):     # the other things greyed out, so no bit of them is kept
                    if j != i and other is not None:
                        arr[other] = bg
                pic = Image.fromarray(arr)
                for rect in BLANK.get((name, i), []):
                    ImageDraw.Draw(pic).rectangle(rect, fill=bg)
                x0, y0, x1, y1 = box
                pad = 22 if mask is not None else 0
                jobs.append((item, pic.crop((max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)))))
        for (n, path), pic in jobs:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            obj = cut(pic, session)
            square(obj).save(path, "WEBP", quality=90, method=6)
            print(f"{n}: {obj.width} x {obj.height}", flush=True)


def panels(im):
    """The six painted panels of a skills grid, as boxes in reading order."""
    rgb = np.asarray(im.convert("RGB")).astype(int)
    bg, _ = mea.backdrop(rgb)
    far = (np.sqrt(((rgb - bg) ** 2).sum(2)) > 18).astype(np.uint8)
    far = cv2.morphologyEx(far, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    k, lab, st, _ = cv2.connectedComponentsWithStats(far)
    order = sorted(range(1, k), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:6]
    found = [(st[i, 0], st[i, 1], st[i, 0] + st[i, 2], st[i, 1] + st[i, 3]) for i in order]
    h = rgb.shape[0]
    return sorted(found, key=lambda b: (((b[1] + b[3]) / 2) > h / 2, (b[0] + b[2]) / 2))


RIM = (214, 178, 106)          # the thin gold rim round a technique medallion


def medallion(pic):
    """A square panel as a round medallion: the painting in a circle with a thin gold rim and clear corners (the
    cards show technique icons in round badges, cards/theme.seal)."""
    big = ICON * 4
    pic = pic.resize((big, big), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", (big, big), 0)
    inset = round(big * 0.02)
    ImageDraw.Draw(m).ellipse((inset, inset, big - 1 - inset, big - 1 - inset), fill=255)
    pic.putalpha(m)
    w = round(big * 0.025)
    ImageDraw.Draw(pic).ellipse((inset, inset, big - 1 - inset, big - 1 - inset), outline=RIM + (255,), width=w)
    return pic.resize((ICON, ICON), Image.LANCZOS)


def skills(args):
    from scripts.make_gather_art import pairs, unsparkle
    out = os.path.join(ICONS, "tech")
    for grade, (src, spots) in pairs(args).items():
        if grade in technique.TECHNIQUES:                   # a redo of one technique: one painting, maybe with an
            rgba = Image.open(src).convert("RGBA")          # empty strip; its painted part, cropped square
            a = np.asarray(rgba)
            painted = (a[..., 3] > 0) & (a[..., :3].max(2) > 8)
            ys, xs = np.nonzero(painted)
            im = rgba.convert("RGB")
            if spots:
                im = unsparkle(im, spots)
            x0, y0, x1, y1 = xs.min() + 4, ys.min() + 4, xs.max() - 4, ys.max() - 4
            side = min(x1 - x0, y1 - y0)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            sq = im.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side))
            medallion(sq).save(os.path.join(out, grade + ".webp"), "WEBP", quality=90, method=6)
            print(f"{grade}: {side} px painting", flush=True)
            continue
        g = grade.capitalize()
        keys = [k for k, v in technique.TECHNIQUES.items() if v["grade"] == g]
        keys = [k for k in keys if technique.TECHNIQUES[k]["type"] == "attack"] + \
               [k for k in keys if technique.TECHNIQUES[k]["type"] == "defense"]
        im = Image.open(src).convert("RGB")
        if spots:
            im = unsparkle(im, spots)
        found = panels(im)
        if len(found) != 6 or len(keys) != 6:
            raise SystemExit(f"{grade}: {len(found)} panels, {len(keys)} techniques")
        for key, (x0, y0, x1, y1) in zip(keys, found):
            x0, y0, x1, y1 = x0 + 4, y0 + 4, x1 - 4, y1 - 4          # inside the panel's edge
            side = min(x1 - x0, y1 - y0)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            sq = im.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side))
            medallion(sq).save(os.path.join(out, key + ".webp"), "WEBP", quality=90, method=6)
            print(f"{key}: {side} px panel", flush=True)


if __name__ == "__main__":
    {"items": items, "skills": skills}[sys.argv[1]](sys.argv[2:])
