"""The beasts' faces for the round portrait ring on the fight screen's foe banner (web/templates/explore_play.html
`.eface`, docs/web.md "Fights"): a square crop of each beast's painting (art/beasts/<slug>.png) round its head, so the
ring shows the head instead of the whole body shrunk.

The head is found from its mouth, which art/beasts/heads.json already holds for every beast (read off each picture by
eye, scripts/make_roar_fx.py): beasts face left, so the head's middle sits a little behind and above the mouth; a
beast facing front (the apes, the Master) has its mouth under the middle of its face. The square is 42% of how tall
the beast stands (17% of how long it is, for the long low ones). FIX nudges the few where that misses, in shares of
the square: right, down, and how much bigger.

    python3 -m scripts.make_beast_faces          # every beast; writes art/beasts/faces/<slug>.webp
"""
import json
import os

import numpy as np
from PIL import Image

BEASTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "beasts")
OUT = os.path.join(BEASTS, "faces")
SIZE = 256
FIX = {
    "abyss_crocodile": (0.35, 0, 1.6), "armored_boar_chief": (-0.08, 0.05, 1.3), "bifang_fire_crane": (-0.05, 0.05, 0.7),
    "crimson_fire_hawk": (0.12, 0.08, 0.9), "iron_hide_boar": (0, 0.05, 1.4),
    "jade_scaled_crocodile": (0.3, -0.18, 1.7), "kun_peng_fish_of_the_northern_sea": (0.13, 0.25, 1.05),
    "spear_beak_crane": (0.3, 0, 0.7), "taotie_the_devourer": (-0.1, 0.35, 1.2),
    "tiangou_the_heavenly_hound": (-0.15, -0.1, 1.3), "wild_ox": (-0.1, 0, 1.3), "the_master": (0.2, 0.05, 1.0),
}


def face_box(im, mouth, slug=""):
    """The square round the head, in picture pixels: (left, top, right, bottom)."""
    W, H = im.size
    a = np.asarray(im.convert("RGBA"))[..., 3]
    ys, xs = np.where(a > 128)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    fw, fh = x1 - x0, y1 - y0
    mx, my = mouth[0] * W, mouth[1] * H
    s = max(0.42 * fh, 0.17 * fw)
    facing_left = (mx - x0) < 0.3 * fw
    cx, cy = mx + (0.34 * s if facing_left else 0), my - 0.1 * s
    if slug in FIX:
        dx, dy, k = FIX[slug]
        cx, cy, s = cx + dx * s, cy + dy * s, s * k
    return round(cx - s / 2), round(cy - s / 2), round(cx + s / 2), round(cy + s / 2)


def main():
    with open(os.path.join(BEASTS, "heads.json")) as fh:
        heads = json.load(fh)
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(BEASTS)):
        slug = f[:-4]
        if not f.endswith(".png") or slug not in heads:
            continue
        im = Image.open(os.path.join(BEASTS, f)).convert("RGBA")
        face = im.crop(face_box(im, heads[slug], slug)).resize((SIZE, SIZE), Image.LANCZOS)
        face.save(os.path.join(OUT, slug + ".webp"), "WEBP", quality=90, method=6)
        n += 1
    print(n, "faces")


if __name__ == "__main__":
    main()
