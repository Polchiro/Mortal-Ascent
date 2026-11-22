"""SHOAIB's forge pictures (Gemini, on green, 1024 x 1024; the workshop 1024 x 572) into the forge page's art
(art/forge/; web/templates/forge_play.html, docs/web.md "Live forge").

- props and blanks: the green keyed out (how much greener than red and blue a pixel is), the green spill taken out
  of the edges, Gemini's sparkle (about 905, 905) erased, cut to the picture, WebP with transparency;
- the workshop: Gemini's sparkle (about 935, 483) painted over from around it (OpenCV inpaint).

    python -m scripts.make_forge_art DIR      (DIR holds workshop.png, anvil.png, trough.png, cauldron_oil.png,
                                               blank_sword.png, blank_chest.png, blank_disc.png)
Needs numpy, Pillow and opencv-python.
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "forge")
PROPS = {"anvil": False, "trough": False, "cauldron_oil": False, "blank_sword": False, "blank_chest": False,
         "blank_disc": False}           # name: mirror it (the anvil's horn points the way the videos' does)
MARK, MARK_R = (905, 905), 34
KEY_SOLID, KEY_CLEAR = 40, 110          # green excess (g - max(r, b)) at or below: opaque; at or above: clear


def key(path, mirror=False):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    excess = g - np.maximum(r, b)
    alpha = np.clip((KEY_CLEAR - excess) / (KEY_CLEAR - KEY_SOLID), 0, 1)
    yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]
    alpha[(xx - MARK[0]) ** 2 + (yy - MARK[1]) ** 2 <= MARK_R ** 2] = 0
    g2 = np.minimum(g, np.maximum(r, b) + 6)            # take the green spill out of the edges
    out = np.dstack([r, g2, b, alpha * 255]).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(out, "RGBA")
    im = im.crop(im.getbbox())
    return im.transpose(Image.FLIP_LEFT_RIGHT) if mirror else im


def workshop(path):
    import cv2
    a = cv2.imread(path)
    mask = np.zeros(a.shape[:2], np.uint8)
    cv2.circle(mask, (935, 483), 20, 255, -1)
    return Image.fromarray(cv2.cvtColor(cv2.inpaint(a, mask, 9, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB))


def main(src):
    os.makedirs(OUT, exist_ok=True)
    for name, mirror in PROPS.items():
        im = key(os.path.join(src, name + ".png"), mirror)
        im.save(os.path.join(OUT, name + ".webp"), quality=90, method=6)
        print(name, im.size)
    workshop(os.path.join(src, "workshop.png")).save(os.path.join(OUT, "workshop.jpg"), quality=88)


if __name__ == "__main__":
    main(sys.argv[1])


# The spark burst for a good hammer strike (on black, laid on with `screen`), cut from SHOAIB's hammer_sparkles video:
#   ffmpeg -ss 0.7 -t 3.5 -i hammer_sparkles__blacksmith.mp4 -an -vf "crop=800:600:240:120,scale=480:360,fps=24"
#          -c:v libx264 -crf 26 -pix_fmt yuv420p -movflags +faststart art/forge/sparks.mp4
# The rune's glow for Inscribe and the reveal (on black, laid on with `screen`), from SHOAIB's Rune_glow video:
#   ffmpeg -ss 0 -t 7.5 -i Rune_glow_inscribe_blacksmith.mp4 -an -vf "crop=720:720:280:0,scale=480:480,fps=24"
#          -c:v libx264 -crf 24 -pix_fmt yuv420p -movflags +faststart art/forge/rune.mp4
