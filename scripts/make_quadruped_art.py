"""Turn SHOAIB's redesigned four-legged beasts (Gemini) into their beast art (art/beasts/<slug>.png; art/beasts/README.md):
each beast keeps its own picture, cut out of its plain backdrop, standing on its paws.

    python -m scripts.make_quadruped_art art_dir
    python -m scripts.make_quadruped_art --roar roar_dir

`--roar`: the same beasts' open-mouthed roar pictures (SHOAIB's, Gemini: the same design and side view, mouth wide
open), cut the same way into art/beasts/roar/<slug>.png, on the standing picture's own canvas (`like_standing`) so the
fight shows it at the same size and place. The fight shows one while its beast roars (web/static/fight.js
`roaringMoved`); its mouth goes in heads.json as "<slug>@roar" (scripts/make_roar_fx.py MOUTHS).

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
           "nine_tailed_fox", "thunder_rhino", "fire_hoof_steed", "sky_lynx", "ghost_fire_wolf",
           "qiongqi_the_winged_tiger", "ancient_flame_lion", "white_tiger", "stray_dog_pack")
# the flying beasts (SHOAIB's redesign of the birds), cut the same way
FLYING = ("spear_beak_crane", "thunder_hawk", "bone_vulture", "storm_eagle", "iron_feather_crow", "crimson_fire_hawk",
          "bifang_fire_crane", "vermilion_bird", "kun_peng_fish_of_the_northern_sea", "wind_feather_falcon")
# the serpents (SHOAIB's redesign), cut the same way
SERPENTS = ("field_viper", "rock_python", "frost_python", "black_water_serpent", "void_serpent")
# the amphibians (SHOAIB's redesign)
AMPHIBIANS = ("thornback_lizard", "poison_toad", "ember_lizard")
# the dragons (SHOAIB's redesign)
DRAGONS = ("flood_dragon_jiao", "azure_dragon")
# the primates (SHOAIB's redesign; the Ancient Golden Ape moved here from the four-legged beasts)
PRIMATES = ("silver_monkey", "golden_eyed_ape_king", "ancient_golden_ape", "shanxiao_mountain_spirit")
# the insects and arthropods (SHOAIB's redesign)
INSECTS = ("venom_scorpion", "golden_silk_spider", "thousand_year_centipede")
# the crocodiles (SHOAIB's redesign)
CROCODILES = ("jade_scaled_crocodile", "abyss_crocodile")
# the tortoises (SHOAIB's redesign)
TORTOISES = ("stone_shell_tortoise", "black_tortoise_xuanwu", "primordial_dragon_turtle")
FACES_RIGHT = {"black_tortoise_xuanwu", "jade_scaled_crocodile", "abyss_crocodile", "thousand_year_centipede", "golden_eyed_ape_king", "shanxiao_mountain_spirit", "flood_dragon_jiao", "thornback_lizard", "black_water_serpent", "bifang_fire_crane", "vermilion_bird", "nine_tailed_fox", "thunder_rhino", "fire_hoof_steed", "ancient_golden_ape", "bloodfang_wolf", "steel_horn_bull", "ironbark_bear", "wind_leopard", "flame_maned_lion",
               "earth_splitting_rhino", "shadow_panther", "cloud_leopard"}
# drawn on a slab: the slab's top edge, as a share of the picture's height (read off each design by eye)
SLAB = {"horned_stag": 0.81, 
        "grey_wolf": 0.80, "cloud_leopard": 0.73,
        "nine_tailed_fox": 0.80, "thunder_rhino": 0.80, "fire_hoof_steed": 0.80}
SPARKLE = (70, 60)               # Gemini's mark: its box from the bottom-right corner, px
# stood on grey stone the cut-out keeps (a pedestal, a rock) under coloured talons: below this line (a share of the
# picture's height) the grey stone is dropped and the talons kept
STONE = {"crimson_fire_hawk": 0.83, "thunder_hawk": 0.76}
SOLID = {"old_black_bear", "shanxiao_mountain_spirit", "venom_scorpion", "golden_silk_spider", "thousand_year_centipede"}  # its thin staff and crystal: kept whole against the plain backdrop
ONE_PIECE = {"spear_beak_crane"}  # only the beast itself (its roar picture has the spear tip drawn loose beside it)
WARM = {"crimson_fire_hawk"}     # a flame beast: below the line only its own red-orange is kept (the stone is beige)
HAZE = {"ancient_flame_lion"}    # drawn wreathed in smoke the backdrop's grey shows through: that grey is dropped


def cut(path, name, session):
    from rembg import remove
    im = Image.open(path).convert("RGB")
    a = np.asarray(remove(im, session=session)).copy()
    h, w = a.shape[:2]
    if name in SOLID:                                        # thin parts the cutter fades: whatever isn't the grey backdrop
        px = np.asarray(im).astype(np.float32)
        bg = np.median(np.concatenate([px[:20].reshape(-1, 3), px[:, :20].reshape(-1, 3)]), axis=0)
        keep = np.abs(px - bg).max(axis=2) > 34
        a[..., :3] = np.where(keep[..., None], px, a[..., :3]).astype(np.uint8)      # with its own colours
        a[..., 3] = np.maximum(a[..., 3], keep * 255).astype(np.uint8)
    a[h - SPARKLE[1]:, w - SPARKLE[0]:, 3] = 0
    if name in SLAB:
        a = off_the_slab(a, SLAB[name])
    if name in STONE:
        a = off_the_stone(a, np.asarray(im).astype(np.float32), STONE[name], name in WARM)
    if name in HAZE:
        a = no_haze(a, np.asarray(im).astype(np.float32))
    alpha = a[..., 3] > 24                                   # the beast itself: its largest piece and what touches it
    lab, n = ndimage.label(ndimage.binary_dilation(alpha, iterations=3))
    if n > 1:
        sizes = ndimage.sum(alpha, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * (1.0 if name in ONE_PIECE else 0.03)))
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


def off_the_stone(a, src, top, warm=False):
    """Below `top`, drop the stone (unsaturated grey, and what the cut-out left of it half-transparent) and anything
    no longer joined to the beast above the line: the talons are solid and joined to the legs."""
    h = a.shape[0]
    y = int(h * top)
    sat = src.max(-1) - src.min(-1)
    stone = (sat < 38) & (src[..., 2] - src[..., 0] < 25)                 # grey, not the blue of lightning or flame
    if warm:
        stone |= src[..., 0] - src[..., 1] < 45                           # beige stone: red and green alike
    below = np.zeros(a.shape[:2], bool)
    below[y:] = True
    a[..., 3] = np.where(below & (stone | (a[..., 3] < 200)), 0, a[..., 3])   # the stone, and its half-cut shading
    keep = a[..., 3] > 60
    lab, n = ndimage.label(keep)
    above = set(np.unique(lab[:y][keep[:y]]))                              # pieces that reach above the line: the beast
    a[..., 3] = np.where(np.isin(lab, list(above - {0})), a[..., 3], 0)
    return a


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


# the roar pictures drawn on a slab (its top edge, as SLAB), and drawn facing the other way from the standing design
ROAR_SLAB = {}
ROAR_FLIP = set()


def like_standing(roar, still):
    """The roar picture on the standing picture's own canvas, so the fight draws it at the same size and place: scaled
    to the same amount of body (alpha area), its feet on the same ground line under the same spot (the middle of its
    paws), shrunk if it would not fit."""
    def feet_x(im):
        a = np.asarray(im.getchannel("A")) > 128
        rows = np.flatnonzero(a.any(1))
        low = a[rows.max() - max(2, int(len(rows) * 0.08)):rows.max() + 1]
        return np.flatnonzero(low.any(0)).mean()
    W, H = still.size
    area = lambda im: (np.asarray(im.getchannel("A")) > 128).sum()
    s = (area(still) / max(1, area(roar))) ** 0.5
    fx = feet_x(still)
    for _ in range(40):
        w, h = max(1, round(roar.width * s)), max(1, round(roar.height * s))
        x = round(fx - feet_x(roar) * s)
        if h <= H and w <= W:
            x = min(max(x, 0), W - w)
            break
        s *= 0.97
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(roar.resize((w, h), Image.LANCZOS), (x, H - h))
    return canvas


def main(src, roar=False):
    from rembg import new_session
    session = new_session("isnet-general-use")
    dest = os.path.join(BEASTS, "roar") if roar else BEASTS
    os.makedirs(dest, exist_ok=True)
    for name in DESIGNS + FLYING + SERPENTS + AMPHIBIANS + DRAGONS + PRIMATES + INSECTS + CROCODILES + TORTOISES:                                     # (the Mountain Tiger roars from its own cut-out poses)
        path = os.path.join(src, name + ".png")
        if not os.path.exists(path):
            print("missing", name)
            continue
        if roar:
            SLAB.clear(); SLAB.update(ROAR_SLAB)
            STONE.clear()                                   # the roar pictures are drawn with nothing underfoot
            FACES_RIGHT.symmetric_difference_update(ROAR_FLIP & {name})
        out = cut(path, name, session)
        if roar:
            out = like_standing(out, Image.open(os.path.join(BEASTS, name + ".png")).convert("RGBA"))
        out.save(os.path.join(dest, name + ".png"), optimize=True)
        print(name, out.size)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--roar"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], roar="--roar" in sys.argv)
