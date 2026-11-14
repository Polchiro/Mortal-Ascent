"""Turn SHOAIB's Gemini designs for the brace techniques into the effect pictures the fight plays (web/static/fight.js,
`braced`; docs/web.md "Techniques"), cleaned of their painted checkerboard and Gemini's sparkle like the others.

    python -m scripts.make_brace_fx dust.png mist.png iron.png roots.png bell.png shell.png lotus.png

    dust.png    Horse Stance Guard: a ring of dust at the feet. See-through and no brighter than the checker, so the
                checker is rebuilt square by square (scripts/make_palm_fx.py `key_checker`).
    mist.png    Calm Breath Stance: a slow spiral of breath mist.
    iron.png    Iron Cloth Body: a woven iron sheen over a man's outline. Only the weave of its chest is kept, as a
                texture (iron_cloth_body.webp); the fight lays it over the fighter's own frame, so it takes the shape
                of whoever is fighting.
    roots.png   Rooted Mountain Stance: stone roots and a see-through mountain.
    bell.png    Golden Bell Cover: a golden bell, dim and see-through inside.
    shell.png   Ancient Turtle Shell Art: a dome of hexagonal shell plates. A small man is painted standing inside
                it; he is erased, so the fighter is the one inside.
    The roots, the bell and the shell are see-through or dark in places, so like the dust their checker is rebuilt
    square by square.
    lotus.png   Immortal Lotus Body: a blooming lotus.

Writes art/fx/tech/<technique id>.webp.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from scripts.make_fist_fx import key_glow, save
from scripts.make_palm_fx import key_checker, trim

IRON_WEAVE = (468, 120, 568, 250)          # the chest of the woven outline, x0 y0 x1 y1 on the 1024 x 559 picture
SHELL_MAN = (468, 250, 556, 400)           # the man painted inside the dome


def solid(keyed, path, t, floor):
    """Fill a design's enclosed inside (no brighter than the checker, so the rebuild let it go) back in with its own
    colours at no less than `floor`, and drop stray bits away from it."""
    a = np.asarray(keyed).astype(np.float32)
    al = a[..., 3] / 255
    inside = ndimage.binary_fill_holes(ndimage.binary_closing(al > t, iterations=3))
    raise_ = inside & (al < floor)
    src = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    src = ndimage.uniform_filter(src, (17, 17, 1))               # over one checker period, so the checker evens out
    a[raise_, :3] = src[raise_]
    al = np.where(raise_, floor, al)
    lab, n = ndimage.label(al > 0.1)
    if n:
        sizes = ndimage.sum(al > 0.1, lab, range(1, n + 1))
        al *= np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * 0.12))
    a[..., 3] = al * 255
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def tidy(im, iterations=3, fade=0.0):
    """Drop thin stray lines left at a design's edges, and fade its bottom `fade` share (a ragged cut edge)."""
    a = np.asarray(im).astype(np.float32)
    al = a[..., 3] / 255
    keep = ndimage.binary_dilation(ndimage.binary_opening(al > 0.15, iterations=iterations), iterations=iterations + 1)
    al = al * keep
    if fade:
        ys = np.where(al.max(1) > 0.1)[0]
        y0, y1 = ys.min(), ys.max()
        ramp = np.clip((y1 - np.arange(len(al))) / max(1, (y1 - y0) * fade), 0, 1)
        al = al * ramp[:, None]
    a[..., 3] = al * 255
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def iron(path):
    """The weave of its chest: on a light checker, so the checker is rebuilt square by square to lift it."""
    return key_checker(path).crop(IRON_WEAVE)


def main(paths):
    if len(paths) != 7:
        sys.exit(__doc__)
    dust, mist, iron_png, roots, bell, shell_png, lotus = paths
    save(trim(tidy(key_checker(dust))), "horse_stance_guard")
    save(key_glow(Image.open(mist)), "calm_breath_stance")
    save(iron(iron_png), "iron_cloth_body")
    save(trim(solid(key_checker(roots), roots, 0.3, 0.75)), "rooted_mountain_stance")
    save(trim(solid(key_checker(bell), bell, 0.3, 0.45)), "golden_bell_cover")
    dome = solid(key_checker(shell_png), shell_png, 0.25, 0.92)
    a = np.asarray(dome).copy()
    x0, y0, x1, y1 = SHELL_MAN                 # the painted man, gone: the fighter stands inside instead
    a = a.astype(np.float32)                    # filled from the dome around him, as if he was never there
    hole = np.zeros(a.shape[:2], bool)
    hole[y0:y1, x0:x1] = True
    for _ in range(300):
        smooth = ndimage.uniform_filter(a, (3, 3, 1))
        a[hole] = smooth[hole]
    a = a.clip(0, 255).astype(np.uint8)
    save(trim(tidy(Image.fromarray(a, "RGBA"), 4, 0.08)), "ancient_turtle_shell_art")
    save(key_glow(Image.open(lotus)), "immortal_lotus_body")


if __name__ == "__main__":
    main(sys.argv[1:])
