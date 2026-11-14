"""Turn SHOAIB's Gemini designs for the punch techniques into the effect images the fight plays (web/static/fight.js,
`technique`; the plan is in docs/web.md "Techniques").

Gemini drew each design on a *fake* transparency checkerboard painted into the pixels (grey squares of 8-9 px, at a
different brightness in each picture) and put its sparkle mark in the bottom-right corner. The glowing designs are
keyed on how much brighter or more coloured each pixel is than the light checker squares; the mountain, whose rock is
darker than the checker, is cut out with rembg and its golden glow added back. The sparkle is cleared.

    python -m scripts.make_fist_fx iron.png tiger.png bull.png thunder.png mountain.png dragons.png

in the order of DESIGNS. Writes art/fx/tech/<technique id>.webp, plus three single dragons cut from the nine for
Nine Dragons Ascending Fist (nine_dragons_head_{1,2,3}.webp), each flying out of a punch.
Needs numpy, Pillow and rembg (pip install "rembg[cpu]"; the isnet-general-use model).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "fx", "tech")
DESIGNS = ("iron_fist", "fierce_tiger_claw", "raging_bull_fist", "rolling_thunder_palm", "mountain_shattering_fist",
           "nine_dragons_ascending_fist")
SOLID = ("iron_fist", "mountain_shattering_fist")   # designs no brighter than the checker: cut out with rembg
PERIOD = 17                               # the painted checker repeats every 17 px (two squares)
SPARKLE = (890, 425, 985, 515)            # Gemini's mark, x0 y0 x1 y1 on the 1024 x 559 pictures
DRAGON_HEADS = (                          # boxes on the nine-dragon picture around one dragon's head and neck
    ((520, 108, 712, 238), False),        # right side, upper: already faces right (towards the beast)
    ((548, 240, 718, 350), False),        # right side, lower
    ((410, 22, 610, 145), True),          # the top one faces left: mirrored
)


def checker_level(a):
    """How bright the light checker squares are: the bright end of the grey pixels along the picture's border."""
    border = np.concatenate([a[:40].reshape(-1, 3), a[-40:].reshape(-1, 3), a[:, :40].reshape(-1, 3), a[:, -40:].reshape(-1, 3)])
    grey = border[(border.max(1) - border.min(1)) < 10]
    return float(np.percentile(grey.max(1), 92))


def key_glow(im, trim=True):
    """Alpha from brightness above the checker and from colour (the checker is grey); colours un-mixed from it.
    In the soft glow the checker still shows through as a faint pattern, so there the picture is averaged over one
    checker period (PERIOD x PERIOD), which evens it out; the bright core keeps its full detail (a tinted checker is
    as coloured as the glow over it, so the core is told apart by brightness alone)."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    level = checker_level(a)
    smooth = np.asarray(im.convert("RGB").filter(ImageFilter.BoxBlur(PERIOD // 2))).astype(np.float32)
    def alpha_of(x):
        v, sat = x.max(-1), x.max(-1) - x.min(-1)
        return np.maximum(np.clip((v - level - 12) / 90, 0, 1), np.clip((sat - 22) / 80, 0, 1))
    sharp, soft = alpha_of(a), alpha_of(smooth)
    core = np.clip((a.max(-1) - level - 95) / 60, 0, 1)[..., None]           # only the truly bright core stays sharp
    a = a * core + smooth * (1 - core)
    alpha = sharp * core[..., 0] + soft * (1 - core[..., 0])
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0
    bg = level * 0.55                                                     # the checker's average grey behind a glow
    rgb = (a - (1 - alpha[..., None]) * bg) / np.maximum(alpha[..., None], 0.05)
    return finish(rgb, alpha, trim)


def key_solid(im, bright=False):
    """For designs no brighter than the checker: the mountain's rock, and the iron fist's grey crystals. Cut out by
    rembg (its soft rim hardened, as it lets checker through), with the glow and sparks keyed by colour (and, for the
    iron fist's white light, brightness) on top, from the checker-averaged picture."""
    from rembg import new_session, remove
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    big = im.convert("RGB").resize((im.width * 2, im.height * 2), Image.LANCZOS)
    mask = np.asarray(remove(big, session=new_session("isnet-general-use"), only_mask=True).resize(im.size, Image.LANCZOS)) / 255.0
    if bright:                                     # the iron fist's crystals: a hard rim, a pixel in
        mask = np.clip((mask - 0.6) / 0.25, 0, 1)
        mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))) / 255.0
    else:                                          # the mountain's rock, which the model is less sure of
        mask = np.clip((mask - 0.45) / 0.3, 0, 1)
        mask = np.maximum(mask, dark_rock(im, mask))
    smooth = np.asarray(im.convert("RGB").filter(ImageFilter.BoxBlur(PERIOD // 2))).astype(np.float32)
    sat = smooth.max(-1) - smooth.min(-1)
    glow = np.clip((sat - 34) / 70, 0, 1)
    if bright:
        glow = np.maximum(glow, np.clip((smooth.max(-1) - checker_level(rgb) - 40) / 80, 0, 1))
    glow *= 1 - mask
    sure = np.clip((mask - 0.9) / 0.1, 0, 1)[..., None]           # the sharp picture only where it is surely rock
    out = rgb * sure + smooth * (1 - sure)
    return finish(out, np.maximum(mask, glow))


def dark_rock(im, model):
    """Rock darker than the checker, found where the model hesitates. Averaged over one checker period the checker
    is a flat mid-grey, while rock stays dark; at the rock's rim (where the average still mixes in checker) a pale
    grey pixel the model did not keep is a light checker square, not rock, and is left out."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    level = checker_level(rgb)
    smooth = np.asarray(im.convert("RGB").filter(ImageFilter.BoxBlur(PERIOD // 2))).astype(np.float32).max(-1)
    rock = np.clip((level * 0.62 - smooth) / (level * 0.15), 0, 1)
    rock = np.asarray(Image.fromarray((rock * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))) / 255.0
    v, sat = rgb.max(-1), rgb.max(-1) - rgb.min(-1)
    pale_square = (v > level * 0.8) & (sat < 14) & (model < 0.5)
    rock[pale_square] = 0
    near = Image.fromarray(((model > 0.2) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(31))   # only beside
    return rock * (np.asarray(near) / 255.0)                     # what the model found, not dark patches elsewhere


def finish(rgb, alpha, trim=True):
    x0, y0, x1, y1 = SPARKLE
    alpha = np.where(alpha < 0.12, 0, alpha)        # faint specks of checker left far from the design
    alpha[y0:y1, x0:x1] = 0
    out = Image.fromarray(np.dstack([rgb.clip(0, 255), alpha * 255]).astype(np.uint8), "RGBA")
    if not trim:
        return out
    box = out.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    pad = 18
    return out.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(out.width, box[2] + pad), min(out.height, box[3] + pad)))


def lone_dragon(im):
    """One dragon lifted from the nine: an oval fade instead of the box's straight edges, and the white swirl that
    winds through the nine (grey, unlike the gold dragons) dropped."""
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    r = np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2))
    sat = a[..., :3].max(-1) - a[..., :3].min(-1)
    a[..., 3] *= np.clip((1 - r) / 0.35, 0, 1) * np.clip((sat - 40) / 60, 0, 1)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def save(im, name):
    im.save(os.path.join(OUT, name + ".webp"), "WEBP", quality=88, method=6)
    print(name, im.size)


def main(paths):
    if len(paths) != len(DESIGNS):
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    for tid, path in zip(DESIGNS, paths):
        src = Image.open(path)
        save(key_solid(src, bright=tid == "iron_fist") if tid in SOLID else key_glow(src), tid)
        if tid == "nine_dragons_ascending_fist":
            keyed = key_glow(src, trim=False)               # DRAGON_HEADS are in the picture's own coordinates
            for i, (box, mirror) in enumerate(DRAGON_HEADS, 1):
                head = lone_dragon(keyed.crop(box))
                save(head.transpose(Image.FLIP_LEFT_RIGHT) if mirror else head, f"nine_dragons_head_{i}")


if __name__ == "__main__":
    main(sys.argv[1:])
