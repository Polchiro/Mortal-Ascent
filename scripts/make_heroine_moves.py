"""Give the female cultivator the punch, the palm push, the finger jab and the brace the male plays (looks.MOTION_SHEETS), made from his frames:
the same movement and timing, so every Fist and Palm technique lines up the same for her (docs/web.md "Techniques").

For each of his frames: his robes take her colours (her idle picture's mean and spread, scripts/make_hero_attack.py
`match_colours`), he is scaled to her height with his feet on her ground line, and his head is replaced by hers,
cut from her idle picture and placed on his face (found frame by frame from the skin of his face), so she keeps
her face and hair.

    python -m scripts.make_heroine_moves

Writes art/portraits/fight/hero_female_{palm,finger,brace}.webp in the same 320 x 360 cells as his, and prints where her
hand is at the release, for looks.MOTION_SHEETS.
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

from scripts.make_hero_attack import COLS, OUT, match_colours

CELL = (320, 360)
WIDE = 120                                       # extra room while building, so nothing is cut before she is placed
CANVAS_OFFSET, CANVAS_SCALE = (208, 3), 1.5      # where a cell sits on the 1024 x 559 fight canvas (make_hero_attack)
HEAD = (181, 63, 229, 125)                      # her head and hair on her idle picture, in cell pixels: x0 y0 x1 y1


def in_cells(path):
    """Her idle picture, cut to the cell the frames are drawn in."""
    im = Image.open(path).convert("RGBA")
    x, y = CANVAS_OFFSET
    return im.crop((x, y, x + round(CELL[0] * CANVAS_SCALE), y + round(CELL[1] * CANVAS_SCALE))).resize(CELL, Image.LANCZOS)


def frames(path, n):
    sheet = Image.open(path).convert("RGBA")
    return [sheet.crop(((i % COLS) * CELL[0], (i // COLS) * CELL[1], (i % COLS + 1) * CELL[0], (i // COLS + 1) * CELL[1]))
            for i in range(n)]


def face_of(im, reach=0.2):
    """The middle of the face: the skin-coloured patch just under the top of the head (the bun), not a raised fist."""
    a = np.asarray(im).astype(np.float32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    ys = np.where(al.max(1) > 128)[0]
    y0, y1 = ys.min(), ys.max()
    top_x = float(np.where(al[y0:y0 + 6].max(0) > 128)[0].mean())         # the top of the head
    skin = (al > 200) & (r > 150) & (r > g + 12) & (g > b) & (r - b > 30)
    skin[int(y0 + (y1 - y0) * reach):] = False
    xx_all = np.arange(a.shape[1])[None, :].repeat(a.shape[0], 0)
    skin &= np.abs(xx_all - top_x) < 34
    if skin.sum() < 15:
        return None
    lab, n = ndimage.label(skin)
    big = 1 + int(np.argmax(ndimage.sum(skin, lab, range(1, n + 1))))
    yy, xx = np.where(lab == big)
    return float(xx.mean()), float(yy.mean())


def top_of(im):
    """The top of the head: where the figure starts, and the middle of it there."""
    al = np.asarray(im.getchannel("A"))
    y0 = int(np.where(al.max(1) > 128)[0].min())
    return float(np.where(al[y0:y0 + 6].max(0) > 128)[0].mean()), float(y0)


def scaled(im, s, feet_y, cx_from, cx_to):
    """Scale about the feet so the figure stands on feet_y, its middle moved from cx_from to cx_to."""
    big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    box = im.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
    dx = round(cx_to - cx_from * s)
    dy = round(feet_y - box[3] * s)
    out = Image.new("RGBA", (CELL[0] + WIDE, CELL[1]), (0, 0, 0, 0))    # room to the right for the lunge
    out.alpha_composite(big.crop((max(0, -dx), max(0, -dy), big.width, big.height)), (max(0, dx), max(0, dy)))
    return out


def head_patch(her):
    """Her head and hair, faded out at the neck so it sits on his collar."""
    x0, y0, x1, y1 = HEAD
    patch = her.crop(HEAD)
    a = np.asarray(patch).astype(np.float32)
    h = a.shape[0]
    fade = np.clip((h - np.arange(h)) / 12, 0, 1)[:, None]
    a[..., 3] *= fade
    return Image.fromarray(a.astype(np.uint8), "RGBA"), face_of(her)


def build(motion, n, her, patch, her_face, hbox, s):
    his = frames(os.path.join(OUT, f"hero_male_{motion}.webp"), n)
    ref_cx = (hbox[0] + hbox[2]) / 2
    mbox = his[0].getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
    his = [scaled(im, s, hbox[3], (mbox[0] + mbox[2]) / 2, ref_cx) for im in his]
    # where the face sits under the top of his head, from the frames where his face shows (before his colours
    # change, which can hide his skin); then every frame places her face there, so a turned face still gets her head
    seen = [(face_of(im), top_of(im)) for im in his]
    found = [(f[0] - t[0], f[1] - t[1]) for f, t in seen if f]
    off = np.median(found, axis=0)
    his = match_colours(his, her)
    out = []
    for im, (f, t) in zip(his, seen):
        fx, fy = f if f else (t[0] + off[0], t[1] + off[1])
        hx, hy = her_face
        px, py = round(fx - (hx - HEAD[0])), round(fy - (hy - HEAD[1]))
        a = np.asarray(im).astype(np.float32)                   # his head and top-knot cleared above his collar
        neck = round(fy + 0.62 * (HEAD[3] - her_face[1]))
        a[:neck, max(0, round(fx) - 30):round(fx) + 30, 3] = 0
        im = Image.fromarray(a.astype(np.uint8), "RGBA")
        im.alpha_composite(patch, (px, py))
        out.append(im)
    # then, as for his frames, she is moved left inside her cells just enough that her lunge isn't cut off
    reach = max(im.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()[2] for im in out)
    shift = max(0, reach - (CELL[0] - 8))
    return [im.crop((shift, 0, shift + CELL[0], CELL[1])) for im in out], shift


def main():
    her = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    patch, her_face = head_patch(her)
    hbox = her.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
    male = in_cells(os.path.join(OUT, "hero_male_idle.webp"))
    mbox = male.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
    s = (hbox[3] - hbox[1]) / (mbox[3] - mbox[1])                    # her height against his
    for motion, n in (("palm", 48), ("finger", 48), ("brace", 33)):   # her punch is her own: make_heroine_fist.py
        images, shift = build(motion, n, her, patch, her_face, hbox, s)
        rows = -(-len(images) // COLS)
        sheet = Image.new("RGBA", (CELL[0] * COLS, CELL[1] * rows), (0, 0, 0, 0))
        for i, im in enumerate(images):
            sheet.alpha_composite(im, ((i % COLS) * CELL[0], (i // COLS) * CELL[1]))
        sheet.save(os.path.join(OUT, f"hero_female_{motion}.webp"), quality=82, method=6)
        print(f"hero_female_{motion}.webp: {len(images)} frames, scale {s:.2f}, moved left {shift} px")


if __name__ == "__main__":
    main()
