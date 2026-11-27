"""Cut SHOAIB's painted UI pieces (Nov 27 2026): the Heavenly Blessing orbs, Lotus Coins and Moon Pearls, the map
screen's frame (hero plate, rings, vials, Break Through tab, dock icons), the realm seals, equipment slots, journey
icons and name plaque, the fight screens' banners, omen scroll and foe rings, and their move buttons, side buttons, info panel and move
pictures (docs/web.md "Painted UI").

    python -m scripts.make_ui_art blessings1=a.png blessings2=b.png currency=c.png hero_plate=d.png frames=e.png \\
        dock=f.png seals1=g.png seals2=h.png slots=i.png journey=j.png plaque=k.png \\
        fight_banners=l.png fight_frames=m.png fight_rings=n.png \\
        move_frames=o.png side_frames=p.png move_icons=q.png [only=blessings1,currency]

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
shape  a plate lying on another frame (the info panel's tab): cut by its outline in SHAPES, the frame under it dropped.
disc   a round move picture (x, y, radius): cut off the grey with what spills past the disc, in a square
       DISC_REACH times the radius each way, so every disc sits the same size in its square.
panel  a frame cut the same way, with the clear spots it closes in (grooves, ring, middle) filled with dark lacquer
       so text set in them reads on any scene (the fight screens' banners, omen scroll, plaque and pill).

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
    # the fight screens' top corners (beast fight, spar, duel): your banner and the foe's, the omen scroll, the
    # middle-of-the-screen plaque, the Battle History pill and the foe's portrait ring by danger
    "fight_banners": [((44, 50, 1319, 367), "panel", "ui/fight_me"), ((51, 382, 1328, 718), "panel", "ui/fight_foe")],
    "fight_frames": [((54, 36, 1323, 425), "panel", "ui/fight_omen"), ((84, 508, 671, 677), "panel", "ui/fight_toast"),
                     ((784, 511, 1300, 671), "panel", "ui/fight_pill")],
    "fight_rings": [((63, 188, 453, 578), "frame", "ui/foe_ring_normal"), ((480, 182, 901, 581), "frame", "ui/foe_ring_elite"),
                    ((903, 145, 1344, 594), "frame", "ui/foe_ring_boss")],
    # the fight screens' bottom: the four move buttons (the top four of six; the last two are spares), the pill and
    # flee buttons, the "Your turn" panel and its gold tab, and the five move pictures
    "move_frames": [((23, 24, 677, 253), "panel", "ui/move_strike"), ((705, 26, 1365, 255), "panel", "ui/move_techniques"),
                    ((24, 256, 678, 487), "panel", "ui/move_guard"), ((707, 257, 1360, 488), "panel", "ui/move_break")],
    "side_frames": [((30, 295, 462, 424), "panel", "ui/fight_side_pill"), ((497, 280, 916, 438), "panel", "ui/fight_side_flee"),
                    ((940, 86, 1355, 665), "panel", "ui/fight_info"), ((954, 80, 1110, 142), "shape", "ui/fight_info_tab")],
    "move_icons": [((151, 379, 127), "disc", "icons/actions/strike"), ((419, 379, 126), "disc", "icons/actions/techniques"),
                   ((688, 379, 127), "disc", "icons/actions/guard"), ((956, 377, 126), "disc", "icons/actions/break"),
                   ((1223, 379, 127), "disc", "icons/actions/flee")],
}


# Pieces patched from their own mirror image (flipped left to right about column `about`) before they are cut: the
# info panel loses its gold tab (cut on its own, so the panel can stretch) and Gemini's sparkle on its bottom edge.
MIRROR_X = {"ui/fight_info": [((940, 80, 1148, 147), 1147.5), ((1200, 598, 1292, 686), 1147.5)]}
# Colour fixes: the Break button's right-hand ornament came out teal like Techniques'; turned to ember red.
RETINT = {"ui/move_break": 0.72}
DISC_REACH = 1.32                   # a move picture's square reaches this far past its disc, for the sword, flames, sparks


def mirror_x(im, fixes):
    out = im.copy()
    for (x0, y0, x1, y1), about in fixes:
        src = (round(2 * about - x1), y0, round(2 * about - x0), y1)
        out.paste(im.crop(src).transpose(Image.FLIP_LEFT_RIGHT), (x0, y0))
    return out


def retint(pic, from_x):
    """Teal to ember red, right of `from_x` (a fraction of the width)."""
    a = np.asarray(pic).copy()
    hsv = cv2.cvtColor(a[..., :3], cv2.COLOR_RGB2HSV)
    h, sat = hsv[..., 0].astype(int), hsv[..., 1]
    x = np.arange(a.shape[1])[None, :] >= from_x * a.shape[1]
    teal = x & (h >= 70) & (h <= 110) & (sat > 30) & (hsv[..., 2] > 60)        # not the dark lacquer inside
    hsv[..., 0] = np.where(teal, 4, hsv[..., 0])
    hsv[..., 1] = np.where(teal, np.clip(sat.astype(int) * 1.25, 0, 255), sat).astype(np.uint8)
    a[..., :3] = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return Image.fromarray(a)


def cut_disc(im, cx, cy, r, others):
    """A round move picture off the grey with what spills past its disc (sword tip, flames, sparks), in a clear
    square DISC_REACH times its radius each way, so every disc is the same size in its square. Anything nearer one
    of the other discs is theirs."""
    R = round(r * DISC_REACH)
    grey = tuple(int(v) for v in np.median(np.asarray(im.convert("RGB")).reshape(-1, 3), 0))
    padded = Image.new("RGB", (im.width + 2 * R, im.height + 2 * R), grey)       # a square past the edge is grey too
    padded.paste(im.convert("RGB"), (R, R))
    pic = cut_frame_soft(padded.crop((cx, cy, cx + 2 * R, cy + 2 * R)))
    a = np.asarray(pic).copy()
    yy, xx = np.mgrid[cy - R:cy + R, cx - R:cx + R]
    mine = np.hypot(xx - cx, yy - cy) - r
    for ox, oy, orr in others:
        a[..., 3] = np.where(np.hypot(xx - ox, yy - oy) - orr < mine, 0, a[..., 3])
    inside = np.hypot(xx - cx, yy - cy) <= r - 1.5
    a[..., 3] = np.where(inside, 255, a[..., 3])
    return Image.fromarray(a)


# A gold plate lying on another frame is cut by its outline (the frame's own gold lines touch it, so colour can't
# tell them apart): the info panel's tab, a plate with a point at the bottom middle. Picture coordinates.
SHAPES = {"ui/fight_info_tab": [(961, 86), (1103, 86), (1103, 131), (1045, 131), (1032, 140), (1019, 131), (961, 131)]}


def cut_shape(im, box, outline):
    """The piece inside `outline` (drawn 4x and shrunk, for a soft edge), the rest clear."""
    from PIL import ImageDraw
    big = 4
    m = Image.new("L", (im.width * big, im.height * big), 0)
    ImageDraw.Draw(m).polygon([((x - box[0]) * big, (y - box[1]) * big) for x, y in outline], fill=255)
    pic = im.convert("RGBA")
    pic.putalpha(m.resize(im.size, Image.LANCZOS))
    a = np.asarray(pic)[..., 3]
    ys, xs = np.nonzero(a > 8)
    return pic.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def cut_frame_soft(im):
    """cut_frame without trimming or speck removal: the same box back, the grey made clear."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    bg, _ = mea.backdrop(rgb.astype(int))
    dist = np.sqrt(((rgb - bg) ** 2).sum(2))
    a = np.clip((dist - mea.SAME) / (mea.KEY - mea.SAME), 0, 1)
    a3 = a[..., None]
    col = np.where(a3 > 0.02, (rgb - (1 - a3) * bg) / np.maximum(a3, 0.02), 0)
    return Image.fromarray(np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8))


# Where Gemini's sparkle sits on a piece, painting it over the grey would bite a hole in it; instead the spot is
# mended from the piece's own mirror image (flipped top to bottom about the row given: the foe's ring, the pill).
MEND = {"fight_banners": 549, "fight_frames": 584}


def mend(im, about, at=(0.906, 0.836), r=0.03):
    """Cover the sparkle at `at` with the same spot flipped top to bottom about row `about`."""
    w, h = im.size
    cx, cy, rr = round(at[0] * w), round(at[1] * h), round(r * w)
    box = (cx - rr, cy - rr, cx + rr, cy + rr)
    src = (box[0], 2 * about - box[3], box[2], 2 * about - box[1])
    out = im.copy()
    out.paste(im.crop(src).transpose(Image.FLIP_TOP_BOTTOM), box[:2])
    return out


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


def fill_holes(pic, rgba=(9, 15, 19, 215)):
    """A panel: the clear spots closed in by the frame (its grooves, ring and middle) filled with dark lacquer under
    the paint, so text and bars set in them read on any scene; outside the frame stays clear."""
    a = np.asarray(pic)[..., 3]
    k, lab = cv2.connectedComponents((a < 250).astype(np.uint8))
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    inside = np.isin(lab, [i for i in range(1, k) if i not in edge])
    under = np.zeros(a.shape + (4,), np.uint8)
    under[inside] = rgba
    base = Image.fromarray(under)
    base.alpha_composite(pic)
    return base


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
        if name in MEND:
            im = mend(im, MEND[name])
        else:
            im = unsparkle(im, spots) if spots else im
        for box, mode, rel in JOBS[name]:
            if mode == "disc":
                others = [b for b, m, _ in JOBS[name] if m == "disc" and b != box]
                out = cut_disc(im, *box, others)
                path = os.path.join(ART, rel + ".webp")
                out.save(path, "WEBP", quality=92, method=6)
                print(f"{rel}: {out.width} x {out.height}", flush=True)
                continue
            pic = (mirror_x(im, MIRROR_X[rel]) if rel in MIRROR_X else im).crop(box)
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
            elif mode == "shape":
                out = cut_shape(pic, box, SHAPES[rel])
            elif mode == "panel":
                out = wide(fill_holes(cut_frame(pic)))
                out = retint(out, RETINT[rel]) if rel in RETINT else out
            else:
                out = wide(cut_frame(pic))
            out.save(path, "WEBP", quality=92, method=6)
            print(f"{rel}: {out.width} x {out.height}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
