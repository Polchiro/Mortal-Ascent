"""Turn SHOAIB's redesigned four-legged beasts (Gemini) into their beast art (art/beasts/<slug>.png; art/beasts/README.md):
each beast keeps its own picture, cut out of its plain backdrop, standing on its paws.

    python -m scripts.make_quadruped_art art_dir

`art_dir` holds the designs named by beast (`<slug>.png`, e.g. `iron_hide_boar.png`), any of DESIGNS. Each is
1024 x 559 on a pale backdrop. Several stand on a painted slab of stone or rock (`SLAB`): the cut-out model drops most
of it, and what is left below the paws is cut away so the beast stands on the fight's own ground. Gemini's sparkle mark
(bottom right) is dropped. Beasts face left on the fight screen (toward the cultivator), so the designs drawn facing
right are mirrored (`FACES_RIGHT`). Then each is trimmed to its outline and saved no larger than 900 px, as the others.

After this, run scripts/make_roar_fx.py's `heads` step (or `python -m scripts.make_quadruped_art --heads`) to record
each new beast's mouth for the roar.
Needs numpy, Pillow, scipy and rembg.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEASTS = os.path.join(ROOT, "art", "beasts")
MAX = 900

DESIGNS = ("iron_hide_boar", "red_fox", "shadow_wolf", "horned_stag", "wild_boar", "grey_wolf", "wild_ox",
           "old_black_bear", "bloodfang_wolf", "armored_boar_chief", "white_browed_tiger_king", "steel_horn_bull",
           "ironbark_bear", "frost_wolf", "wind_leopard", "flame_maned_lion", "earth_splitting_rhino", "shadow_panther",
           "cloud_leopard",
           "nine_tailed_fox", "thunder_rhino", "fire_hoof_steed", "sky_lynx", "ancient_golden_ape", "ghost_fire_wolf",
           "qiongqi_the_winged_tiger", "ancient_flame_lion", "white_tiger")
FACES_RIGHT = {"nine_tailed_fox", "thunder_rhino", "fire_hoof_steed", "ancient_golden_ape", "bloodfang_wolf", "steel_horn_bull", "ironbark_bear", "wind_leopard", "flame_maned_lion",
               "earth_splitting_rhino", "shadow_panther", "cloud_leopard"}
# drawn on a slab: the slab's top edge, as a share of the picture's height (read off each design by eye)
SLAB = {"iron_hide_boar": 0.81, "red_fox": 0.80, "shadow_wolf": 0.80, "horned_stag": 0.81, "wild_boar": 0.81,
        "grey_wolf": 0.80, "wild_ox": 0.81, "old_black_bear": 0.80, "cloud_leopard": 0.73,
        "nine_tailed_fox": 0.80, "thunder_rhino": 0.80, "fire_hoof_steed": 0.80, "ancient_golden_ape": 0.80}
SPARKLE = (70, 60)               # Gemini's mark: its box from the bottom-right corner, px
HAZE = {"ancient_flame_lion"}    # drawn wreathed in smoke the backdrop's grey shows through: that grey is dropped


def cut(path, name, session):
    from rembg import remove
    im = Image.open(path).convert("RGB")
    a = np.asarray(remove(im, session=session)).copy()
    h, w = a.shape[:2]
    a[h - SPARKLE[1]:, w - SPARKLE[0]:, 3] = 0
    if name in SLAB:
        a = off_the_slab(a, SLAB[name])
    if name in HAZE:
        a = no_haze(a, np.asarray(im).astype(np.float32))
    alpha = a[..., 3] > 24                                   # the beast itself: its largest piece and what touches it
    lab, n = ndimage.label(ndimage.binary_dilation(alpha, iterations=3))
    if n > 1:
        sizes = ndimage.sum(alpha, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * 0.03))
        a[..., 3] = np.where(keep, a[..., 3], 0)
    out = Image.fromarray(a, "RGBA")
    a = np.asarray(out).copy()
    a[..., 3] = np.where(a[..., 3] < 24, 0, a[..., 3])          # faint haze left of the backdrop: not the beast
    out = Image.fromarray(a, "RGBA")
    if name in FACES_RIGHT:
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    out = out.crop(out.getbbox())
    solid = np.flatnonzero(np.asarray(out.getchannel("A")).max(1) > 128)
    out = out.crop((0, 0, out.width, int(solid.max()) + 1))     # paws on the bottom edge, not a faint shadow below them
    out.thumbnail((MAX, MAX), Image.LANCZOS)
    return out


def no_haze(a, src):
    """Drop the backdrop's pale grey where it shows through smoke: unsaturated and no brighter than the backdrop.
    Flame (saturated, or white-hot above the backdrop) and the beast's own darker colours are kept."""
    sat, v = src.max(-1) - src.min(-1), src.max(-1)
    grey = np.clip((28 - sat) / 14, 0, 1) * np.clip((v - 150) / 30, 0, 1) * np.clip((238 - v) / 8, 0, 1)
    a[..., 3] = (a[..., 3] * (1 - grey)).astype(np.uint8)
    return a


def off_the_slab(a, top):
    """Cut the slab away: below its top edge keep only the paws, columns where the beast comes down to the slab."""
    h = a.shape[0]
    y = int(h * top)
    al = a[..., 3].astype(np.float32)
    rgb = a[..., :3].astype(np.float32)
    below = np.zeros_like(al, dtype=bool)
    below[y:] = True
    # the slab is a greyish-green stone band; paws are darker or the beast's own colour, joined to the legs above
    legs = al[y - 6:y] > 128
    cols = ndimage.binary_dilation(legs.any(0), iterations=6)
    keep = np.zeros_like(below)
    feet = int(h * 0.04)                                     # how far the paws reach below the slab's top edge
    keep[y:y + feet, :] = cols[None, :]
    a[..., 3] = np.where(below & ~keep, 0, a[..., 3])
    return a


def main(src):
    from rembg import new_session
    session = new_session("isnet-general-use")
    for name in DESIGNS:
        path = os.path.join(src, name + ".png")
        if not os.path.exists(path):
            print("missing", name)
            continue
        out = cut(path, name, session)
        out.save(os.path.join(BEASTS, name + ".png"), optimize=True)
        print(name, out.size)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
