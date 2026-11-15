"""Turn SHOAIB's Gemini designs for the deflection techniques into the effect pictures the fight plays
(web/static/fight.js `deflected`; docs/web.md "Techniques"), cleaned of their painted checkerboard and Gemini's sparkle
like the others.

    python -m scripts.make_deflect_fx streak.png water.png wing.png moon.png hands.png void.png

    streak.png  Parrying Arm: a white streak of light, bright at its middle.
    water.png   Flowing Stream Palm: a ring of two curling water streams.
    wing.png    Crane Wing Deflection: a white crane's wing with loose feathers.
    moon.png    Moon Mirror Palm: a pale moon mirror, open at its middle.
    These four glow brighter than the checker, so they are keyed by brightness and colour (make_fist_fx `key_glow`).
    hands.png   Thousand Hands Deflection: a ring of jade hands joined by threads. Dim and see-through, so the checker
                is rebuilt square by square (make_palm_fx `key_checker`), and the stray bits it leaves are dropped.
    void.png    Void Mirror Stance: a dark violet mirror cracked by lightning, shards flying. No brighter than the
                checker, so it is cut out by rembg with its glow keyed on top (make_fist_fx `key_solid`).

Writes art/fx/tech/<technique id>.webp.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from scripts.make_fist_fx import key_glow, key_solid, save
from scripts.make_palm_fx import key_checker, trim


def main_part(im, share=0.12):
    """Only the design itself: bits much smaller than its largest piece (lines left along the edges) are dropped."""
    a = np.asarray(im).astype(np.float32)
    al = a[..., 3] / 255
    lab, n = ndimage.label(ndimage.binary_dilation(al > 0.1, iterations=4))
    if n > 1:
        sizes = ndimage.sum(al > 0.1, lab, range(1, n + 1))
        al *= np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * share))
    a[..., 3] = al * 255
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def main(paths):
    if len(paths) != 6:
        sys.exit(__doc__)
    streak, water, wing, moon, hands, void = paths
    save(key_glow(Image.open(streak)), "parrying_arm")
    save(key_glow(Image.open(water)), "flowing_stream_palm")
    save(key_glow(Image.open(wing)), "crane_wing_deflection")
    save(key_glow(Image.open(moon)), "moon_mirror_palm")
    save(trim(main_part(key_checker(hands))), "thousand_hands_deflection")
    save(key_solid(Image.open(void)), "void_mirror_stance")


if __name__ == "__main__":
    main(sys.argv[1:])
