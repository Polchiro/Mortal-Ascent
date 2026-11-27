"""Make the beast roar (web/static/fight.js `roar`, docs/web.md) from SHOAIB's roar video, and find where every beast's
head is, so the one roar can burst from any beast's mouth.

    python -m scripts.make_roar_fx path/to/roar.mp4

The video (Gemini, 1280 x 720, 24 fps) is a 4 x 2 grid of eight white shockwaves on a dark background, each starting
at its own moment. Three are used, one per beast tier, each keyed against its own cell's empty frame from before it
starts (so the background and the grid lines drop out exactly), and saved white so the fight can tint it with the
beast's element colour:

    art/fx/roar_ring.webp    a clean ring with a glittering edge    normal beasts and bandits
    art/fx/roar_double.webp  a double ring                          Elite beasts
    art/fx/roar_burst.webp   a spiky burst of rings                 Beast Kings

Each: FRAMES frames of SIZE x SIZE in an 8-wide grid, from a dot to the full wave.

Also writes art/beasts/heads.json: for every beast picture in art/beasts/, its mouth (where the roar starts) and how
tall it stands, as shares of the picture. The mouths were read off each picture by eye (MOUTHS: beasts face left or
front, and a crane's beak or a serpent's raised head isn't where a rule would guess). A beast added later, not yet in
MOUTHS, gets a guess from its outline (`head_of`) by running this again; until then fight.js uses a default.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "art", "fx")
BEASTS = os.path.join(ROOT, "art", "beasts")
CELL_W, CELL_H = 320, 360
SIZE, FRAMES, COLS = 256, 16, 8
# name: (cell column, cell row, the empty frame's time, the wave's start and end times in s)
MOUTHS = {
    "abyss_crocodile": (0.05, 0.33),
    "ancient_flame_lion": (0.05, 0.47),
    "ancient_golden_ape": (0.41, 0.25),
    "armored_boar_chief": (0.08, 0.62),
    "azure_dragon": (0.04, 0.42),
    "bifang_fire_crane": (0.04, 0.12),
    "black_tortoise_xuanwu": (0.03, 0.47),
    "black_water_serpent": (0.04, 0.18),
    "bloodfang_wolf": (0.04, 0.5),
    "bone_vulture": (0.04, 0.33),
    "cloud_leopard": (0.05, 0.45),
    "crimson_fire_hawk": (0.3, 0.23),
    "earth_splitting_rhino": (0.13, 0.6),
    "ember_lizard": (0.02, 0.07),
    "field_viper": (0.04, 0.11),
    "fire_hoof_steed": (0.04, 0.28),
    "flame_maned_lion": (0.03, 0.37),
    "flood_dragon_jiao": (0.03, 0.29),
    "frost_python": (0.03, 0.17),
    "frost_wolf": (0.04, 0.28),
    "ghost_fire_wolf": (0.06, 0.44),
    "golden_eyed_ape_king": (0.07, 0.32),
    "golden_silk_spider": (0.38, 0.55),
    "grey_wolf": (0.05, 0.52),
    "horned_stag": (0.05, 0.345),
    "iron_feather_crow": (0.06, 0.15),
    "iron_hide_boar": (0.08, 0.63),
    "ironbark_bear": (0.03, 0.18),
    "jade_scaled_crocodile": (0.03, 0.52),
    "kun_peng_fish_of_the_northern_sea": (0.02, 0.45),
    "lightning_weasel": (0.03, 0.22),
    "mountain_tiger": (0.04, 0.5),
    "nine_tailed_fox": (0.04, 0.31),
    "old_black_bear": (0.045, 0.56),
    "pixiu": (0.13, 0.3),
    "poison_toad": (0.05, 0.31),
    "primordial_dragon_turtle": (0.03, 0.42),
    "qilin": (0.15, 0.3),
    "qiongqi_the_winged_tiger": (0.06, 0.49),
    "red_fox": (0.03, 0.32),
    "rock_python": (0.022, 0.137),
    "shadow_panther": (0.04, 0.33),
    "shadow_wolf": (0.03, 0.47),
    "shanxiao_mountain_spirit": (0.47, 0.26),
    "silver_monkey": (0.07, 0.3),
    "sky_lynx": (0.06, 0.37),
    "spear_beak_crane": (0.1, 0.12),
    "steel_horn_bull": (0.1, 0.5),
    "stone_shell_tortoise": (0.02, 0.47),
    "storm_eagle": (0.03, 0.13),
    "stray_dog_pack": (0.05, 0.36),
    "taotie_the_devourer": (0.3, 0.2),
    "the_master": (0.45, 0.2),
    "thornback_lizard": (0.02, 0.36),
    "thousand_year_centipede": (0.04, 0.3),
    "thunder_hawk": (0.04, 0.17),
    "thunder_rhino": (0.12, 0.6),
    "tiangou_the_heavenly_hound": (0.18, 0.37),
    "venom_scorpion": (0.32, 0.61),
    "vermilion_bird": (0.17, 0.27),
    "void_serpent": (0.03, 0.2),
    "white_browed_tiger_king": (0.055, 0.35),
    "wind_feather_falcon": (0.03, 0.67),
    "white_tiger": (0.05, 0.37),
    "wild_boar": (0.08, 0.58),
    "wild_ox": (0.07, 0.6),
    "wind_leopard": (0.03, 0.31),
}
VARIANTS = {"roar_ring": (1, 0, 0.3, 0.85, 3.6), "roar_double": (3, 0, 0.3, 1.15, 3.0), "roar_burst": (0, 1, 1.0, 2.3, 4.6)}


# the open mouths of the roar pictures (art/beasts/roar/<slug>.png, on the standing picture's canvas), read by eye;
# saved in heads.json as "<slug>@roar"
ROAR_MOUTHS = {
    "abyss_crocodile": (0.13, 0.39),
    "ancient_flame_lion": (0.08, 0.22),
    "ancient_golden_ape": (0.37, 0.29),
    "armored_boar_chief": (0.125, 0.59),
    "azure_dragon": (0.08, 0.5),
    "bifang_fire_crane": (0.05, 0.31),
    "black_tortoise_xuanwu": (0.07, 0.52),
    "black_water_serpent": (0.09, 0.23),
    "bloodfang_wolf": (0.075, 0.5),
    "bone_vulture": (0.08, 0.38),
    "cloud_leopard": (0.3, 0.24),
    "crimson_fire_hawk": (0.33, 0.15),
    "earth_splitting_rhino": (0.12, 0.47),
    "ember_lizard": (0.07, 0.18),
    "field_viper": (0.31, 0.17),
    "fire_hoof_steed": (0.08, 0.12),
    "flame_maned_lion": (0.1, 0.37),
    "flood_dragon_jiao": (0.08, 0.36),
    "frost_python": (0.07, 0.22),
    "frost_wolf": (0.1, 0.32),
    "ghost_fire_wolf": (0.08, 0.15),
    "golden_eyed_ape_king": (0.1, 0.33),
    "golden_silk_spider": (0.37, 0.58),
    "grey_wolf": (0.06, 0.36),
    "horned_stag": (0.063, 0.377),
    "iron_feather_crow": (0.23, 0.36),
    "iron_hide_boar": (0.11, 0.59),
    "ironbark_bear": (0.07, 0.25),
    "jade_scaled_crocodile": (0.12, 0.42),
    "kun_peng_fish_of_the_northern_sea": (0.27, 0.48),
    "lightning_weasel": (0.09, 0.23),
    "mountain_tiger": (0.1, 0.45),
    "nine_tailed_fox": (0.15, 0.19),
    "old_black_bear": (0.08, 0.44),
    "poison_toad": (0.15, 0.38),
    "primordial_dragon_turtle": (0.07, 0.42),
    "qiongqi_the_winged_tiger": (0.06, 0.25),
    "red_fox": (0.07, 0.33),
    "rock_python": (0.067, 0.266),
    "shadow_panther": (0.08, 0.22),
    "shadow_wolf": (0.07, 0.41),
    "shanxiao_mountain_spirit": (0.46, 0.29),
    "silver_monkey": (0.09, 0.34),
    "sky_lynx": (0.06, 0.34),
    "spear_beak_crane": (0.1, 0.41),
    "steel_horn_bull": (0.12, 0.5),
    "stone_shell_tortoise": (0.06, 0.47),
    "storm_eagle": (0.07, 0.19),
    "stray_dog_pack": (0.06, 0.36),
    "thornback_lizard": (0.05, 0.4),
    "thousand_year_centipede": (0.09, 0.3),
    "thunder_hawk": (0.08, 0.2),
    "thunder_rhino": (0.24, 0.5),
    "venom_scorpion": (0.31, 0.6),
    "vermilion_bird": (0.36, 0.24),
    "void_serpent": (0.08, 0.25),
    "white_browed_tiger_king": (0.12, 0.36),
    "white_tiger": (0.17, 0.25),
    "wild_boar": (0.14, 0.53),
    "wild_ox": (0.07, 0.55),
    "wind_feather_falcon": (0.05, 0.68),
    "wind_leopard": (0.08, 0.4),
}


def grab(video, t, col, row):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "f.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                        "-vf", f"crop={CELL_W}:{CELL_H}:{col * CELL_W}:{row * CELL_H}", out], check=True)
        return np.asarray(Image.open(out).convert("RGB")).astype(np.float32)


def wave(video, col, row, empty, t0, t1):
    bg = grab(video, empty, col, row)
    side = min(CELL_W, CELL_H) - 24                                   # a square inside the cell, off its grid lines
    x0, y0 = (CELL_W - side) // 2, (CELL_H - side) // 2
    cells = []
    for i in range(FRAMES):
        a = grab(video, t0 + (t1 - t0) * i / (FRAMES - 1), col, row)
        lum = np.clip((a - bg).max(-1), 0, 255)                       # only what the wave adds
        alpha = np.clip((lum - 6) / 150, 0, 1)
        img = np.dstack([np.full(lum.shape + (3,), 255.0), alpha * 255]).astype(np.uint8)
        cell = Image.fromarray(img, "RGBA").crop((x0, y0, x0 + side, y0 + side)).resize((SIZE, SIZE), Image.LANCZOS)
        cells.append(cell)
    sheet = Image.new("RGBA", (SIZE * COLS, SIZE * (FRAMES // COLS)), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        sheet.alpha_composite(c, ((i % COLS) * SIZE, (i // COLS) * SIZE))
    return sheet


def head_of(path):
    """The head: the top of the figure in its leftmost fifth (beasts face left), as shares of the picture."""
    a = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    ys, xs = np.where(a > 128)
    if not len(xs):
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    front = xs <= x0 + (x1 - x0) * 0.22
    top = ys[front].min()
    near = front & (ys <= top + (y1 - y0) * 0.12)
    hx, hy = xs[near].mean(), ys[near].mean() + (y1 - y0) * 0.06
    h, w = a.shape
    return [round(float(hx) / w, 3), round(float(hy) / h, 3), round(float(y1 - y0) / h, 3)]


def main(video):
    for name, (col, row, empty, t0, t1) in VARIANTS.items():
        wave(video, col, row, empty, t0, t1).save(os.path.join(FX, name + ".webp"), "WEBP", quality=85, method=6)
        print(name)
    heads = {}
    for f in sorted(os.listdir(BEASTS)):
        if f.endswith(".png"):
            h = head_of(os.path.join(BEASTS, f))
            if h:
                if f[:-4] in MOUTHS:
                    h[:2] = MOUTHS[f[:-4]]
                heads[f[:-4]] = h
    for name, xy in ROAR_MOUTHS.items():
        if os.path.exists(os.path.join(BEASTS, "roar", name + ".png")) and name in heads:
            heads[name + "@roar"] = [*xy, heads[name][2]]
    with open(os.path.join(BEASTS, "heads.json"), "w") as fh:
        json.dump(heads, fh, indent=0, sort_keys=True)
    print(len(heads), "heads")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
