"""Build the male cultivator's deflection from SHOAIB's video of him (looks.MOTION_SHEETS "deflect", web/static/fight.js
`deflected`; docs/web.md "Techniques"): the movement every deflection technique shares, as hers does.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six panels, 3 x 2, each about 424 x 356, on pale grey. The
bottom-left panel (x 0-424, y 362-718) sweeps a blue Qi arc round again and again; from 7.0 s it plays one clean
round: on guard, he reaches back, sweeps the arc up over and round in front of him to turn the blow (furthest out at
about 8.0 s), carries it down and across (about 8.4 s), and settles on guard again by about 9.4 s.

The painted blue arc and its sparks are kept (`qi`): the cut-out model drops them, so saturated, bright blue is keyed
back in by colour. His robes are a lighter blue-grey than his sword frames, so they are matched to those (as
make_hero_fist does), leaving the Qi as it is.

    python -m scripts.make_hero_deflect path/to/his_deflect.mp4

Writes art/portraits/fight/hero_male_deflect.webp: 32 frames of 320 x 360 in an 8-wide grid, and prints his box on
guard and how far he reaches each frame, for looks.MOTION_SHEETS.
Needs ffmpeg, numpy, Pillow, scipy and rembg, as make_hero_attack does.
"""
import os
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid
from scripts.make_hero_fist import bbox, place
from scripts.make_heroine_deflect import only_her
from scripts.make_heroine_guard import edge_clean

CELL = (424, 356, 0, 362)          # w, h, x, y: the bottom-left panel
START, LENGTH, STEP = 7.0, 2.65, 2  # one round, on guard to on guard: 32 frames


def qi(frame):
    """The painted Qi: saturated, bright blue the backdrop and robes never are (robes are greyer and darker)."""
    a = np.asarray(frame.convert("RGB")).astype(np.float32)
    sat, v = a.max(-1) - a.min(-1), a.max(-1)
    blue = np.clip((a[..., 2] - a[..., 0] - 40) / 50, 0, 1)
    k = np.clip((sat - 70) / 50, 0, 1) * np.clip((v - 150) / 50, 0, 1) * blue
    return np.asarray(Image.fromarray((k * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255


def with_qi(cutouts, clip):
    out = []
    for c, f in zip(cutouts, clip):
        a = np.asarray(only_her(c)).copy()
        a[..., 3] = np.maximum(a[..., 3], (qi(f) * 255).astype(np.uint8))
        out.append(Image.fromarray(a, "RGBA"))
    return out


def his_colours(images, ref):
    """Robes matched to his sword frames (mean and spread of each channel, make_hero_attack `match_colours`), the
    painted Qi and the skin left as they are."""
    def body(im):
        a = np.asarray(im).astype(np.float32)
        rgb = a[..., :3]
        sat = rgb.max(-1) - rgb.min(-1)
        return rgb[(a[..., 3] > 200) & (sat < 70)]
    r, g = body(ref), np.concatenate([body(im) for im in images])
    mu_r, sd_r, mu_g, sd_g = r.mean(0), r.std(0), g.mean(0), g.std(0)
    out = []
    for im in images:
        a = np.asarray(im).astype(np.float32)
        rgb = a[..., :3]
        sat, v = rgb.max(-1) - rgb.min(-1), rgb.max(-1)
        keep = np.clip((sat - 60) / 40, 0, 1) * np.clip((rgb[..., 2] - rgb[..., 0] - 30) / 40, 0, 1)   # the Qi
        skin = np.clip((rgb[..., 0] - rgb[..., 2] - 10) / 30, 0, 1)                                     # face, hands
        keep = np.maximum(keep, skin)
        new = (rgb - mu_g) / sd_g * sd_r + mu_r
        a[..., :3] = (rgb * keep[..., None] + new * (1 - keep[..., None])).clip(0, 255)
        out.append(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return out


def his_ref():
    return Image.open(os.path.join(OUT, "hero_male_attack.webp")).convert("RGBA").crop((0, 0, 320, 360))


def build(clip, name):
    ref = his_ref()
    images = his_colours(with_qi(cut(clip), clip), ref)
    images, scale, shift = place(images, ref)
    images = [edge_clean(im) for im in images]
    rows = grid(images, name)
    return images, scale, shift, rows


def report(images, name, scale, shift, rows):
    a = np.asarray(images[0].getchannel("A"))
    ys, xs = np.where(a > 128)
    print(f"{name}: {len(images)} frames, {COLS} x {rows}, scale {scale:.2f}, moved left {shift} px, "
          f"on guard x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}\n  boxes {[bbox(im) for im in images]}")


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, int(LENGTH * 24) + 1, STEP))
    images, scale, shift, rows = build(clip, "hero_male_deflect.webp")
    report(images, "hero_male_deflect.webp", scale, shift, rows)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
