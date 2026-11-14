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
    "abyss_crocodile": (0.07, 0.65),
    "ancient_flame_lion": (0.13, 0.33),
    "ancient_golden_ape": (0.23, 0.3),
    "armored_boar_chief": (0.13, 0.55),
    "azure_dragon": (0.12, 0.28),
    "bifang_fire_crane": (0.08, 0.2),
    "black_tortoise_xuanwu": (0.16, 0.14),
    "black_water_serpent": (0.2, 0.12),
    "bloodfang_wolf": (0.15, 0.38),
    "bone_vulture": (0.05, 0.47),
    "cave_bat_swarm": (0.18, 0.45),
    "cloud_leopard": (0.06, 0.33),
    "crimson_fire_hawk": (0.05, 0.48),
    "earth_splitting_rhino": (0.22, 0.52),
    "ember_lizard": (0.08, 0.33),
    "field_viper": (0.33, 0.13),
    "fire_hoof_steed": (0.06, 0.33),
    "flame_maned_lion": (0.24, 0.42),
    "flood_dragon_jiao": (0.12, 0.33),
    "frost_python": (0.19, 0.3),
    "frost_wolf": (0.08, 0.47),
    "ghost_fire_wolf": (0.11, 0.47),
    "golden_eyed_ape_king": (0.3, 0.22),
    "golden_silk_spider": (0.32, 0.5),
    "grey_wolf": (0.06, 0.42),
    "horned_stag": (0.05, 0.3),
    "iron_feather_crow": (0.07, 0.27),
    "iron_hide_boar": (0.13, 0.52),
    "ironbark_bear": (0.09, 0.37),
    "jade_scaled_crocodile": (0.15, 0.22),
    "kun_peng_fish_of_the_northern_sea": (0.05, 0.3),
    "lightning_weasel": (0.1, 0.37),
    "mountain_tiger": (0.1, 0.5),
    "nine_tailed_fox": (0.1, 0.43),
    "old_black_bear": (0.17, 0.22),
    "pixiu": (0.13, 0.3),
    "poison_toad": (0.12, 0.4),
    "primordial_dragon_turtle": (0.12, 0.42),
    "qilin": (0.15, 0.3),
    "qiongqi_the_winged_tiger": (0.12, 0.65),
    "red_fox": (0.06, 0.33),
    "rock_python": (0.3, 0.17),
    "shadow_panther": (0.08, 0.37),
    "shadow_wolf": (0.08, 0.47),
    "shanxiao_mountain_spirit": (0.26, 0.18),
    "silver_monkey": (0.12, 0.2),
    "sky_lynx": (0.13, 0.48),
    "spear_beak_crane": (0.28, 0.12),
    "steel_horn_bull": (0.15, 0.25),
    "stone_shell_tortoise": (0.06, 0.48),
    "storm_eagle": (0.23, 0.4),
    "stray_dog_pack": (0.1, 0.42),
    "taotie_the_devourer": (0.3, 0.2),
    "the_master": (0.45, 0.2),
    "thornback_lizard": (0.06, 0.48),
    "thousand_year_centipede": (0.18, 0.2),
    "thunder_hawk": (0.1, 0.7),
    "thunder_rhino": (0.25, 0.65),
    "tiangou_the_heavenly_hound": (0.18, 0.37),
    "venom_scorpion": (0.25, 0.55),
    "vermilion_bird": (0.15, 0.25),
    "void_serpent": (0.3, 0.33),
    "white_browed_tiger_king": (0.1, 0.33),
    "white_tiger": (0.13, 0.4),
    "wild_boar": (0.08, 0.6),
    "wild_ox": (0.15, 0.43),
    "wind_leopard": (0.08, 0.38),
}
VARIANTS = {"roar_ring": (1, 0, 0.3, 0.85, 3.6), "roar_double": (3, 0, 0.3, 1.15, 3.0), "roar_burst": (0, 1, 1.0, 2.3, 4.6)}


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
    with open(os.path.join(BEASTS, "heads.json"), "w") as fh:
        json.dump(heads, fh, indent=0, sort_keys=True)
    print(len(heads), "heads")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
