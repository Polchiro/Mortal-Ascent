"""Cut SHOAIB's painted UI pieces (Nov 27 2026): the Heavenly Blessing orbs, Lotus Coins and Moon Pearls, the map
screen's frame (hero plate, rings, vials, Break Through tab, dock icons), the realm seals, equipment slots, journey
icons and name plaque (docs/web.md "Painted UI").

    python -m scripts.make_ui_art blessings1=a.png blessings2=b.png currency=c.png hero_plate=d.png frames=e.png \\
        dock=f.png seals1=g.png seals2=h.png slots=i.png journey=j.png plaque=k.png [only=blessings1,currency]

Each source picture is named as in JOBS: the box (x0, y0, x1, y1) of every piece in it (a 1376 x 768 picture; a
3 x 2 or 2 x 2 grid uses its cells), how to cut it and where it goes:

orb    a round thing on grey (a blessing pearl, a realm seal): found as a circle and kept whole, its glow lifted off
       as light (scripts/make_pill_art.cut_pill), set in a clear ICON square at one size, like the pills.
item   one object (a coin, a pouch, a slot): cut as the gear is (scripts/make_item_art.cut: solid inside its
       outline, no halo), fitted into a clear ICON square.
rect   a square slot frame on a dark backdrop it can't be told from by colour: its gold border found, and the
       square inside it kept whole with rounded corners, fitted into a clear ICON square.
frame  a frame whose middle is the same grey as the backdrop (the hero plate, a ring): everything unlike the grey is
       kept, softly at its edge; the grey middle comes out clear so the page's own text and face show through. Kept
       at its own shape, at most WIDE px wide.

Gemini's sparkle is painted out first where it touches a piece (SPARKLE). The sources are only read.
Needs numpy, opencv, Pillow and rembg (isnet-general-use).
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

from scripts import make_env_assets as mea

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art")
ICON = 256
WIDE = 1200
SPARKLE = "@0.906,0.836,0.026"           # Gemini's mark, bottom right of every picture


def cells(cols, rows, w=1376, h=768, inset=3):
    return [((i % cols) * w // cols + inset, (i // cols) * h // rows + inset,
             (i % cols + 1) * w // cols - inset, (i // cols + 1) * h // rows - inset) for i in range(cols * rows)]


C32, C22 = cells(3, 2), cells(2, 2)
REALMS = ["mortal", "martial_apprentice", "martial_warrior", "martial_expert", "martial_master", "grandmaster",
          "martial_lord", "martial_king", "martial_emperor", "martial_ancestor", "martial_saint"]
JOBS = {
    # (box, mode, path under art/) — pieces not listed (Gemini's extras) are left out
    "blessings1": [(C32[0], "orb", "icons/blessings/gentle_breeze"), (C32[1], "orb", "icons/blessings/spring_rain"),
                   (C32[3], "orb", "icons/blessings/bright_moon"), (C32[4], "orb", "icons/blessings/blazing_sun")],
    "blessings2": [(C32[0], "orb", "icons/blessings/rolling_thunder"), (C32[1], "orb", "icons/blessings/starfall"),
                   (C32[3], "orb", "icons/blessings/heavenly_dragon"),
                   (C32[5], "orb", "icons/blessings/eternal_dao")],         # the glowing one of the two
    "currency": [(C22[0], "item", "icons/currency/lotus_coin"), (C22[1], "item", "icons/currency/lotus_coins"),
                 (C22[2], "item", "icons/currency/moon_pearl"), (C22[3], "item", "icons/currency/moon_pearls")],
    "hero_plate": [((40, 190, 1340, 570), "frame", "ui/hero_plate")],
    "frames": [((55, 22, 458, 425), "frame", "ui/ring"), ((480, 15, 915, 440), "frame", "ui/seal_ring"),
               (C32[2], "item_wide", "ui/vial_hp"),
               (C32[3], "item_wide", "ui/vial_qi"), ((495, 470, 900, 725), "frame", "ui/break_tab")],
    "dock": [(C22[0], "item", "ui/dock_bag"), (C22[1], "item", "ui/dock_character"),
             (C22[2], "item", "ui/dock_techniques"), (C22[3], "item", "ui/dock_map")],
    "seals1": [(C32[i], "orb", f"icons/realms/{REALMS[i]}") for i in range(6)],
    "seals2": [((90, 20, 410, 338), "orb", "icons/realms/martial_lord"),
               ((530, 20, 850, 338), "orb", "icons/realms/martial_king"),
               ((975, 20, 1295, 338), "orb", "icons/realms/martial_emperor"),
               ((300, 390, 630, 705), "orb", "icons/realms/martial_ancestor"),   # (the names written under them
               ((720, 350, 1110, 712), "orb", "icons/realms/martial_saint")],     # are left out)
    "slots": [((345, 52, 648, 362), "rect", "ui/slot_weapon"), ((731, 52, 1034, 362), "rect", "ui/slot_armor"),
              ((345, 400, 648, 710), "rect", "ui/slot_artifact"), ((731, 400, 1034, 710), "rect", "ui/slot_empty")],
    "journey": [(C22[0], "item", "icons/journey/beasts"), (C22[1], "item", "icons/journey/herbs"),
                (C22[2], "item", "icons/journey/breakthroughs"), (C22[3], "item", "icons/journey/duels")],
    "plaque": [((40, 190, 1340, 570), "frame", "ui/name_plaque")],
}


def cut_frame(im):
    """A frame off its grey: anything unlike the grey kept (softly at the edge), the grey middle clear."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    bg, _ = mea.backdrop(rgb.astype(int))
    dist = np.sqrt(((rgb - bg) ** 2).sum(2))
    a = np.clip((dist - mea.SAME) / (mea.KEY - mea.SAME), 0, 1)
    k, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8))
    if k > 2:                                              # specks and the sparkle out
        big = st[1:, cv2.CC_STAT_AREA].max()
        keep = [i for i in range(1, k) if st[i, cv2.CC_STAT_AREA] >= big * 0.02]
        near = cv2.dilate(np.isin(lab, keep).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        a = np.where(near, a, 0)
    a3 = a[..., None]
    col = np.where(a3 > 0.02, (rgb - (1 - a3) * bg) / np.maximum(a3, 0.02), 0)
    out = np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8)
    ys, xs = np.nonzero(out[..., 3] > 8)
    return Image.fromarray(out[ys.min():ys.max() + 1, xs.min():xs.max() + 1])


def cut_rect(im):
    """A square slot frame: the gold border's extent, kept whole with rounded corners."""
    rgb = np.asarray(im.convert("RGB")).astype(int)
    gold = (rgb[..., 0] > 120) & (rgb[..., 1] > 95) & (rgb[..., 0] - rgb[..., 2] > 30)
    ys, xs = np.nonzero(gold)
    x0, x1, y0, y1 = np.percentile(xs, 0.5), np.percentile(xs, 99.5), np.percentile(ys, 0.5), np.percentile(ys, 99.5)
    box = (int(x0), int(y0), int(x1) + 1, int(y1) + 1)
    pic = im.convert("RGBA").crop(box)
    big = 4
    m = Image.new("L", (pic.width * big, pic.height * big), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(m).rounded_rectangle((0, 0, pic.width * big - 1, pic.height * big - 1),
                                        radius=round(min(pic.size) * big * 0.07), fill=255)
    pic.putalpha(m.resize(pic.size, Image.LANCZOS))
    return pic


def fit(obj, side=ICON, fill=0.9):
    s = side * fill / max(obj.size)
    obj = obj.resize((max(1, round(obj.width * s)), max(1, round(obj.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.alpha_composite(obj, ((side - obj.width) // 2, (side - obj.height) // 2))
    return out


def wide(obj):
    if obj.width > WIDE:
        obj = obj.resize((WIDE, round(obj.height * WIDE / obj.width)), Image.LANCZOS)
    return obj


def main(args):
    from rembg import new_session

    from scripts import make_item_art as mia
    from scripts import make_pill_art as mpa
    from scripts.make_gather_art import pairs, unsparkle
    only = None
    for a in list(args):
        if a.startswith("only="):
            only = set(a[5:].split(","))
            args.remove(a)
    session = new_session("isnet-general-use")
    for name, (src, spots) in pairs(args).items():
        if name not in JOBS:
            raise SystemExit(f"{name}: not one of {', '.join(JOBS)}")
        if only and name not in only:
            continue
        im = Image.open(src).convert("RGB")
        im = unsparkle(im, spots) if spots else im
        for box, mode, rel in JOBS[name]:
            pic = im.crop(box)
            path = os.path.join(ART, rel + ".webp")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if mode == "orb":
                cell, at = mpa.cut_pill(pic, session)
                out = mpa.square(cell, at)
            elif mode == "item":
                out = fit(mia.cut(pic, session))
            elif mode == "rect":
                out = fit(cut_rect(pic), fill=0.96)
            elif mode == "item_wide":
                out = wide(mia.cut(pic, session))
            else:
                out = wide(cut_frame(pic))
            out.save(path, "WEBP", quality=92, method=6)
            print(f"{rel}: {out.width} x {out.height}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
