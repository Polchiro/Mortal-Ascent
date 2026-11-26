"""Make the element effects of the beast roars and blows (web/static/fight.js `blast`, `crack`, `impact`, docs/web.md "The beast
roar") from SHOAIB's Nano Banana pictures: each element's own blast, burst and ground patch, so a frost roar throws
ice and a fire roar throws flame instead of one white wave tinted.

    python -m scripts.make_element_fx path/to/folder

The folder holds his pictures, named after what they are (effects on pure black, 1376 x 768 or 1024 x 1024):

    <element>_stream.png   the blast from the beast's mouth across to you, bright end on the RIGHT (8)
    <element>_burst.png    the burst where it hits you, a ring of pieces round an empty middle (8)
    <element>_ground.png   the patch it leaves on the ground at your feet (8)
    ground_crack.png       the crack a toad's or lizard's roar sends along the ground to you (1)
    <mark>.png             a beast's hit mark, painted white so the fight colours it by element (MARKS: bite,
                           fang, gore, tusk, beak, talon, sting, sting_alt, smash, lash), saved to art/fx/marks/

for the eight elements (ELEMENTS). Each is cleaned (the Gemini sparkle and "AI" badge in the bottom-right corner
painted out), keyed off its black background (light becomes opacity, so the glow stays soft), cropped to what is
drawn, and saved to art/fx/elem/<name>.webp. Run it again with new pictures to replace any of them.
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "fx", "elem")
ELEMENTS = ("blood", "frost", "flame", "shadow", "thunder", "venom", "earth", "jade")
NAMES = ([e + "_stream" for e in ELEMENTS] + [e + "_burst" for e in ELEMENTS] + [e + "_ground" for e in ELEMENTS]
         + ["ground_crack"])
MARKS = ("bite", "fang", "gore", "tusk", "beak", "talon", "sting", "sting_alt", "smash", "lash")
MARKS_OUT = os.path.join(ROOT, "art", "fx", "marks")
MAX_SIDE = {"stream": 1100, "burst": 640, "ground": 900, "crack": 1100, "mark": 640}
# SHOAIB: the flame patch came out thinner than the others; it stands a little taller so it reads at your feet
STRETCH_Y = {"flame_ground": 1.5}
FLOOR = 10            # background noise under this (of 255) is pure black


def marks(a):
    """Paint out the Gemini sparkle and the "AI" badge (bottom-right corner): grey, unsaturated, on the black."""
    h, w = a.shape[:2]
    if w > h:                                                  # 1376 x 768
        boxes = [(0.87, 0.78, 0.94, 0.89, False), (0.93, 0.89, 0.99, 0.98, True)]
    else:                                                      # 1024 x 1024
        boxes = [(0.78, 0.78, 0.88, 0.88, False), (0.9, 0.9, 0.98, 0.98, True)]
    for x0, y0, x1, y1, whole in boxes:
        X0, Y0, X1, Y1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
        cell = a[Y0:Y1, X0:X1].astype(int)
        hi, lo = cell.max(axis=2), cell.min(axis=2)
        grey = (hi - lo < 22) & (hi > 30) & (hi < 215)         # the sparkle: flat grey (an effect's light is brighter or coloured)
        if whole:
            grey = (hi - lo < 30)                              # the badge: a grey pill with white letters, alone in its corner
        cell[grey] = 0
        a[Y0:Y1, X0:X1] = cell.astype(np.uint8)
    return a


def keyed(a):
    """Light on black to colour + opacity: opacity from the brightest channel, colour un-darkened by it."""
    rgb = a.astype(np.float32)
    v = np.clip((rgb.max(axis=2) - FLOOR) / (255 - FLOOR), 0, 1)
    alpha = np.power(v, 0.85)
    col = np.where(alpha[..., None] > 0.004, rgb / np.maximum(v[..., None], 0.004), 0)
    col = np.clip(col, 0, 255)
    return np.dstack([col, alpha * 255]).astype(np.uint8)


def fade_ends(a, share=0.1):
    """The crack's two ends melt into the ground instead of stopping at a hard edge."""
    w = a.shape[1]
    ramp = np.ones(w, np.float32)
    n = int(w * share)
    ramp[:n] = np.linspace(0, 1, n)
    ramp[-n:] = np.linspace(1, 0, n)
    a[..., 3] = (a[..., 3] * ramp[None, :]).astype(np.uint8)
    return a


def make(src, name):
    im = Image.open(src).convert("RGB")
    a = keyed(marks(np.array(im)))
    ys, xs = np.nonzero(a[..., 3] > 6)
    pad = 12
    a = a[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]
    if name == "ground_crack":
        a = fade_ends(a)
    out = Image.fromarray(a, "RGBA")
    if name in STRETCH_Y:
        out = out.resize((out.width, round(out.height * STRETCH_Y[name])), Image.LANCZOS)
    kind = "mark" if name in MARKS else "crack" if name == "ground_crack" else name.split("_")[1]
    out.thumbnail((MAX_SIDE[kind], MAX_SIDE[kind]), Image.LANCZOS)
    folder = MARKS_OUT if kind == "mark" else OUT
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".webp")
    out.save(path, "WEBP", quality=86, method=4)
    return path, out.size


def main(folder):
    names = NAMES + list(MARKS)
    missing = [n for n in names if not os.path.exists(os.path.join(folder, n + ".png"))]
    for n in names:
        src = os.path.join(folder, n + ".png")
        if os.path.exists(src):
            path, size = make(src, n)
            print(f"{n:16s} -> {os.path.relpath(path, ROOT)} {size[0]}x{size[1]}")
    if missing:
        print("not in the folder (kept as they were):", ", ".join(missing))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
