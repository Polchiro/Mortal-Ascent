"""Prepare Practice's still pictures from SHOAIB's Nov 24 Gemini images (art/practice/; docs/technique.md "Practice").

    python -m scripts.make_practice_art dummy=a.png plaque=b.png ... (every name in GREEN, BLACK, ICONS, plus
        scroll=, portrait=, hall=)

- GREEN (painted on green): the training objects. Green becomes clear (scripts/make_spar_art.from_green), Gemini's
  sparkle is blanked, the picture is trimmed to the object.
- BLACK (painted on black): the effects. Black becomes clear: how bright a pixel is, is how solid it is.
- ICONS: the three drill badges, gold on a charcoal disc. Their backgrounds came out black, white or both, so the
  disc itself is cut out as a circle (its centre and radius measured by hand on the pictures).
- scroll: the result's parchment, on black: the backdrop is the black joined to the picture's edge (so the dark
  rollers and the tassel stay).
- portrait (Senior Sister Xue's face) and hall (the drill's background: a bright wooden training hall, side view):
  the sparkle painted out; saved as JPEG.
- ambience=<video> (the instructor's "watching" video): its quiet room sound (the hall's air, cloth, a bird outside)
  becomes hall.wav, a seamless loop played under the drill's music (raised, softened above 6 kHz).

Needs numpy, Pillow, scipy and opencv (scripts/make_spar_art).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from scripts import make_spar_art as art

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "practice")

GREEN = {                                  # name: largest width kept (px)
    "dummy": 520, "straw": 520, "iron": 520, "stone": 520, "jade": 520, "broken": 640, "post": 360,
    "plaque": 256, "sandbag": 360, "staff": 900, "log": 760,
}
BLACK = {"splinters": 640, "sparks": 640, "bell": 640, "aura": 480, "breath": 512, "flame": 320}
ICONS = {                                  # name: (centre x, centre y, radius) in the 1024 x 1024 pictures
    "icon_strike": (511, 510, 354), "icon_defend": (503, 516, 388), "icon_breath": (508, 507, 410),
}


def icon(path, cx, cy, r, size=256):
    im = Image.open(path).convert("RGB")
    big = 4                                                       # a smooth edge: drawn large, then shrunk
    mask = Image.new("L", (im.width * big, im.height * big), 0)
    ImageDraw.Draw(mask).ellipse(((cx - r) * big, (cy - r) * big, (cx + r) * big, (cy + r) * big), fill=255)
    mask = mask.resize(im.size, Image.LANCZOS)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out.crop((cx - r, cy - r, cx + r, cy + r)).resize((size, size), Image.LANCZOS)


def scroll(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    x0, y0, x1, y1 = art.mark_box(w, h)
    im[y0:y1, x0:x1] = 0
    dark = im.max(axis=2) < 18
    lab, _ = ndi.label(dark)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    back = np.isin(lab, list(edge))
    a = ndi.gaussian_filter((~back).astype(np.float32), 0.8)
    return np.dstack([im, a * 255])


def main(args):
    art.OUT = OUT                                                  # make_spar_art's save() writes here
    os.makedirs(OUT, exist_ok=True)
    got = dict(a.split("=", 1) for a in args)
    for name, width in GREEN.items():
        if name in got:
            rgba = art.from_green(got[name])
            rgb = rgba[..., :3]                                     # no green cast anywhere (nothing here is green)
            rgb[..., 1] = np.minimum(rgb[..., 1], np.maximum(rgb[..., 0], rgb[..., 2]) + 14)
            art.save(art.trim(rgba), name, width)
    for name, width in BLACK.items():
        if name in got:
            art.save(art.trim(art.from_black(got[name], 1.3)), name, width)
    for name, (cx, cy, r) in ICONS.items():
        if name in got:
            icon(got[name], cx, cy, r).save(os.path.join(OUT, name + ".webp"), quality=90)
            print(name)
    if "scroll" in got:
        art.save(art.trim(scroll(got["scroll"])), "scroll", 1100)
    if "portrait" in got:
        Image.fromarray(art.paint_out(got["portrait"])).resize((384, 384), Image.LANCZOS) \
            .save(os.path.join(OUT, "portrait.jpg"), quality=90)
        print("portrait")
    if "hall" in got:
        Image.fromarray(art.paint_out(got["hall"])).save(os.path.join(OUT, "hall.jpg"), quality=90)
        print("hall")
    if "ambience" in got:
        art.ambience(got["ambience"], level=0.07, name="hall.wav", out=OUT, lowpass=6000)


if __name__ == "__main__":
    main(sys.argv[1:])
