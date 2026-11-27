"""Make the Mortal to Earth techniques' effect pieces (web/technique_fx.py `parts`, web/static/fight.js `part`,
docs/web.md "Techniques: the pieces") from SHOAIB's Nano Banana pictures (Nov 27): each technique gets its main picture
and one to three extra pieces (an impact, a ground patch, flying rocks, leaves, a single palm the fight repeats...),
so the fight builds a moving effect out of stills instead of sliding one picture.

    python -m scripts.make_tech_fx path/to/folder

The folder holds his pictures named as in PIECES below (1376 x 768, effects on pure black). Each is cleaned (the
Gemini sparkle and "AI" badge painted out, scripts/make_element_fx.marks), keyed off its black background and
cropped, and saved to art/fx/tech/<out>.webp, replacing a technique's main picture where `out` is its id. Two keys:

    glow    light on black: opacity from brightness, so a glow stays soft (make_element_fx.keyed)
    solid   painted things (rock, shell, roots, dust): anything clearly above black is opaque, its colour kept,
            so dark rock is not turned into a ghost; faint haze still fades out

Run it again with new pictures to replace any of them.
"""
import os
import sys

import numpy as np
from PIL import Image

from scripts.make_element_fx import keyed, marks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "fx", "tech")

# his file: (the picture it becomes, key, longest side, black under this (of 255) is clear)
PIECES = {
    # Earth
    "mountain_rocks": ("mountain_shattering_fist", "solid", 900, 18),
    "mountain_cracks": ("mountain_shattering_fist_cracks", "solid", 1000, 18),
    "mountain_chunks": ("mountain_shattering_fist_chunks", "solid", 800, 14),
    "shadow_palm": ("thousand_shadow_palm_hand", "glow", 460, 10),
    "shadow_burst": ("thousand_shadow_palm_burst", "glow", 640, 10),
    "river_water": ("river_splitting_finger_water", "glow", 1000, 10),
    "river_flash": ("river_splitting_finger_flash", "glow", 640, 10),
    "bell": ("golden_bell_cover", "glow", 760, 10),
    "bell_ring": ("golden_bell_cover_ring", "glow", 900, 10),
    "bell_sparks": ("golden_bell_cover_sparks", "glow", 640, 10),
    "turtle_dome": ("ancient_turtle_shell_art", "solid", 800, 16),
    "turtle_motes": ("ancient_turtle_shell_art_motes", "glow", 480, 30),
    "hands_hand": ("thousand_hands_deflection_hand", "glow", 380, 10),
    "hands_push": ("thousand_hands_deflection_push", "glow", 800, 10),
    # Mystic
    "thunder_vortex": ("rolling_thunder_palm", "glow", 760, 10),
    "thunder_burst": ("rolling_thunder_palm_burst", "glow", 640, 10),
    "viper_head": ("viper_fang_finger_head", "glow", 640, 10),
    "viper_bite": ("viper_fang_finger_bite", "glow", 640, 10),
    "autumn_arc": ("autumn_wind_kick", "glow", 900, 10),
    "autumn_leaves": ("autumn_wind_kick_leaves", "glow", 900, 10),
    "moon_mirror": ("moon_mirror_palm", "glow", 640, 10),
    "moon_burst": ("moon_mirror_palm_burst", "glow", 700, 10),
    "mist_figure": ("drifting_mist_steps_figure", "glow", 600, 10),
    "mist_trail": ("drifting_mist_steps_trail", "glow", 900, 10),
    "rooted_roots": ("rooted_mountain_stance_roots", "solid", 900, 22),
    "rooted_mountain": ("rooted_mountain_stance", "glow", 700, 10),
    # Yellow
    "tiger_impact": ("fierce_tiger_claw_hit", "glow", 640, 10),
    "swallow_impact": ("swift_swallow_kick_hit", "glow", 640, 10),
    "bull_impact": ("raging_bull_fist_hit", "glow", 640, 10),
    "ironcloth_figure": ("iron_cloth_body_figure", "glow", 600, 10),
    "ironcloth_sparks": ("iron_cloth_body_hit", "glow", 560, 10),
    "stream_splash": ("flowing_stream_palm_hit", "glow", 640, 10),
    "crane_feathers": ("crane_wing_deflection_feathers", "glow", 760, 10),
    # Mortal
    "ironfist_burst": ("iron_fist_hit", "glow", 560, 10),
    "twinpalm_ring": ("twin_palm_strike_hit", "glow", 560, 10),
    "crescent_dust": ("crescent_sweep_hit", "glow", 700, 72),     # his ground behind the dust: under 72 is clear
    "horse_dust": ("horse_stance_guard_hit", "glow", 760, 12),
    "parry_spark": ("parrying_arm_hit", "glow", 480, 10),
    "calm_spiral": ("calm_breath_stance_breath", "glow", 480, 10),
}


def glow(a, floor):
    rgb = a.astype(np.float32)
    v = np.clip((rgb.max(axis=2) - floor) / (255 - floor), 0, 1)
    alpha = np.power(v, 0.85)
    col = np.where(alpha[..., None] > 0.004, rgb / np.maximum(v[..., None], 0.004), 0)
    return np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8)


def solid(a, floor):
    """Opaque where clearly painted (a ramp over 45 levels above `floor`), the painting's own colour kept; where the
    light key would say more (a bright glow at the edge), that wins, so glows stay glows."""
    rgb = a.astype(np.float32)
    hi = rgb.max(axis=2)
    alpha = np.clip((hi - floor) / 45.0, 0, 1)
    g = glow(a, 10)
    lit = g[..., 3].astype(np.float32) / 255
    use_glow = lit > alpha
    col = np.where(use_glow[..., None], g[..., :3].astype(np.float32), rgb)
    return np.dstack([col, np.maximum(alpha, lit) * 255]).astype(np.uint8)


def tidy(name, a):
    """Each picture's own fixes."""
    h, w = a.shape[:2]
    if name == "thunder_burst":                    # a white strip under the picture
        a[int(h * 0.92):] = 0
    if name == "autumn_leaves":                    # a leaf cut off at the left edge
        a[:, :int(w * 0.05)] = 0
    if name == "moon_mirror":                      # a starry sky behind the mirror: only the mirror and its flames
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot(xx - w * 0.5, yy - h * 0.5) / h
        keep = np.clip((0.47 - r) / 0.06, 0, 1)
        a = (a.astype(np.float32) * keep[..., None]).astype(np.uint8)
    if name == "rooted_roots":                     # the trunk he got above the roots: fades into the ground
        ramp = np.clip((np.arange(h) / h - 0.42) / 0.16, 0, 1)
        a = (a.astype(np.float32) * ramp[:, None, None]).astype(np.uint8)
    return a


def soft_edges(a, share=0.06):
    """Where his picture ran off the frame's edge (a trail, the water), it fades out instead of stopping in a line."""
    h, w = a.shape[:2]
    rx = np.minimum(np.arange(w), np.arange(w)[::-1]) / (w * share)
    ry = np.minimum(np.arange(h), np.arange(h)[::-1]) / (h * share)
    ramp = np.clip(np.minimum(ry[:, None], rx[None, :]), 0, 1)
    a[..., 3] = (a[..., 3] * ramp).astype(np.uint8)
    return a


def make(src, name):
    out, key, side, floor = PIECES[name]
    a = tidy(name, marks(np.array(Image.open(src).convert("RGB"))))
    a = solid(a, floor) if key == "solid" else glow(a, floor)
    a = soft_edges(a)
    ys, xs = np.nonzero(a[..., 3] > 6)
    pad = 10
    a = a[max(0, ys.min() - pad):ys.max() + pad, max(0, xs.min() - pad):xs.max() + pad]
    im = Image.fromarray(a, "RGBA")
    im.thumbnail((side, side), Image.LANCZOS)
    path = os.path.join(OUT, out + ".webp")
    im.save(path, "WEBP", quality=86, method=4)
    return path, im.size


def main(folder):
    missing = []
    for name in PIECES:
        src = os.path.join(folder, name + ".png")
        if not os.path.exists(src):
            missing.append(name)
            continue
        path, size = make(src, name)
        print(f"{name:18s} -> {os.path.relpath(path, ROOT)} {size[0]}x{size[1]}")
    if missing:
        print("not in the folder (kept as they were):", ", ".join(missing))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
