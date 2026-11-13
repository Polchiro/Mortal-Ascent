"""Build the male cultivator's sword-attack and guard frames for the website fight screen from SHOAIB's videos.

The video (Gemini, 1280 x 720, 24 fps) is a 4 x 2 grid of the same swordsman. The middle-bottom cell
(x 320-640, y 360-720) plays one full attack between 2.5 s and 5 s: raise the sword behind, a spinning
horizontal slash, the sword overhead, a forward diagonal cut, back on guard.

    python scripts/make_hero_attack.py path/to/attack.mp4 [path/to/guard.mp4]

The guard video (1280 x 720, 24 fps) is a storyboard of 8 numbered panels; panel 5 (x 140-385, y 355-680,
inside the numbers) holds a sword block: a flash and gold sparks as a blow lands, a lean back, steady again.
Its swordsman is drawn in greyer robes, so his colours are matched to the attack video's swordsman, and he is
scaled and placed so his feet stand where the attack frames' feet do.

Needs ffmpeg on PATH, numpy, Pillow and rembg (pip install "rembg[cpu]"; the isnet-general-use model).
Writes, into art/portraits/fight/:
  hero_male_attack.webp     the attack, ATTACK_FRAMES frames of 320 x 360 in a COLS-wide grid (fight.js plays them)
  hero_male_{idle,windup,strike}.webp   stills from the same video on the 1024 x 559 fight canvas
  hero_male_guard.webp      the block, GUARD_FRAMES frames in the same 320 x 360 cells (from the guard video)
The video's white motion blur is recoloured into blue Qi, so the spin reads as a Qi slash.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

CELL = (320, 360, 320, 360)          # w, h, x, y of the attacking cell in the video
START, LENGTH = 2.5, 2.5             # seconds: frames 1..60 at 24 fps
FIRST, LAST = 10, 50                 # the attack, frame numbers inside that clip
SWOOSH = range(16, 34)               # frames whose white motion blur becomes blue Qi
STILLS = {"idle": 1, "windup": 15, "strike": 42}
COLS = 8
SCALE = 1.5                          # cell pixels -> fight-canvas pixels (1024 x 559)
OFFSET = (208, 3)                    # where the cell's top-left lands on the fight canvas
GUARD_CELL = (245, 325, 140, 355)   # w, h, x, y of panel 5 in the guard video, inside its number labels
GUARD_FIRST, GUARD_LAST = 95, 131    # one block, frame numbers from the start of the guard video
GUARD_SCALE, GUARD_AT = 1.10, (56, -2)   # his size and place inside a 320 x 360 attack cell (feet matched)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "portraits", "fight")


def frames(video, tmp, cell=CELL, start=START, length=LENGTH, numbers=range(1, 61)):
    w, h, x, y = cell
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(length), "-i", video,
                    "-vf", f"crop={w}:{h}:{x}:{y}", os.path.join(tmp, "%03d.png")], check=True)
    return [Image.open(os.path.join(tmp, "%03d.png" % i)).convert("RGB") for i in numbers]


def cut(images):
    from rembg import new_session, remove
    s = new_session("isnet-general-use")
    out = []
    for im in images:
        big = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)          # the model sees more detail
        m = remove(big, session=s, only_mask=True).resize(im.size, Image.LANCZOS)
        rgba = im.convert("RGBA")
        rgba.putalpha(m)
        out.append(rgba)
    return out


def qi_swoosh(im):
    """The white, half-transparent motion blur turns into glowing blue Qi; the body is left alone."""
    a = np.asarray(im).astype(np.float32) / 255
    rgb, al = a[..., :3], a[..., 3]
    lum = rgb.mean(-1)
    sat = rgb.max(-1) - rgb.min(-1)
    w = np.clip((lum - 0.45) / 0.25, 0, 1) * np.clip((0.28 - sat) / 0.12, 0, 1) * np.clip((0.97 - al) / 0.25, 0, 1)
    pale = np.array([0.72, 0.95, 1.0]); deep = np.array([0.20, 0.72, 1.0])
    tint = deep + (pale - deep) * np.clip((lum[..., None] - 0.5) / 0.4, 0, 1)
    rgb = rgb * (1 - w[..., None]) + tint * w[..., None]
    al = np.clip(al + w * al * 0.6, 0, 1)
    glow = Image.fromarray((w * al * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    g = np.asarray(glow).astype(np.float32) / 255 * 0.85
    halo = np.array([0.25, 0.75, 1.0])
    out_a = al + g * (1 - al)
    out_rgb = (rgb * al[..., None] + halo * (g * (1 - al))[..., None]) / np.maximum(out_a, 1e-4)[..., None]
    return Image.fromarray((np.dstack([out_rgb, out_a]) * 255).clip(0, 255).astype(np.uint8), "RGBA")


def feather(im, px=10):
    """Fade the cell's edges so a blade or swoosh cut by the video's grid line ends softly."""
    w, h = im.size
    x = np.minimum(np.arange(w), np.arange(w)[::-1]) / px
    y = np.minimum(np.arange(h), np.arange(h)[::-1]) / px
    edge = np.clip(np.minimum(x[None, :], y[:, None]), 0, 1)
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * edge).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def keep_thin_parts(cutout, frame, above=250):
    """The cut-out model drops the thin blade and the flying sparks on some frames: above the knees (the ground
    shadow lies below), anything that is clearly not the video's near-white backdrop is kept as well."""
    rgb = np.asarray(frame).astype(np.float32)
    edge = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    far = np.abs(rgb - np.median(edge, 0)).max(-1)
    key = np.clip((far - 14) / 34, 0, 1) * 255
    key[above:] = 0
    key[:8] = 0; key[:, :6] = 0; key[:, 224:] = 0                    # the storyboard's highlight box runs along the edges
    a = np.asarray(cutout).copy()
    a[..., 3] = np.maximum(a[..., 3], key.astype(np.uint8))
    return Image.fromarray(a, "RGBA")


def match_colours(images, ref):
    """Recolour the guard swordsman so his robes match the attack swordsman (mean and spread of each channel);
    the warm sparks and flash keep their own colours."""
    def body(im):
        a = np.asarray(im).astype(np.float32)
        return a[..., :3][a[..., 3] > 200]
    r, g = body(ref), body(images[0])
    mu_r, sd_r, mu_g, sd_g = r.mean(0), r.std(0), g.mean(0), g.std(0)
    out = []
    for im in images:
        a = np.asarray(im).astype(np.float32)
        rgb = a[..., :3]
        warm = np.clip((rgb[..., 0] - rgb[..., 2]) / 60, 0, 1) * np.clip((rgb.max(-1) - rgb.min(-1)) / 255 / 0.3, 0, 1)
        new = (rgb - mu_g) / sd_g * sd_r + mu_r
        a[..., :3] = (rgb * warm[..., None] + new * (1 - warm[..., None])).clip(0, 255)
        out.append(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return out


def in_cell(im, size):
    big = im.resize((round(im.width * GUARD_SCALE), round(im.height * GUARD_SCALE)), Image.LANCZOS)
    cell = Image.new("RGBA", size, (0, 0, 0, 0))
    x, y = GUARD_AT
    cell.alpha_composite(big, (x, max(0, y)), (0, max(0, -y)))       # alpha_composite takes no negative place
    return cell


def grid(images, name):
    w, h = images[0].size
    rows = -(-len(images) // COLS)
    sheet = Image.new("RGBA", (w * COLS, h * rows), (0, 0, 0, 0))
    for i, im in enumerate(images):
        sheet.alpha_composite(im, ((i % COLS) * w, (i // COLS) * h))
    sheet.save(os.path.join(OUT, name), quality=82, method=6)
    return rows


def on_canvas(im):
    big = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 559), (0, 0, 0, 0))
    canvas.alpha_composite(big, OFFSET)
    return canvas


def main(video, guard_video=None):
    with tempfile.TemporaryDirectory() as tmp:
        clip = cut(frames(video, tmp))
    clip = [feather(qi_swoosh(im) if i + 1 in SWOOSH else im) for i, im in enumerate(clip)]
    attack = clip[FIRST - 1:LAST]
    rows = grid(attack, "hero_male_attack.webp")
    for pose, n in STILLS.items():
        on_canvas(clip[n - 1]).save(os.path.join(OUT, f"hero_male_{pose}.webp"), quality=88, method=6)
    print(f"attack: {len(attack)} frames, {COLS} x {rows} grid")
    if guard_video:
        with tempfile.TemporaryDirectory() as tmp:
            n = GUARD_LAST - GUARD_FIRST + 1
            raw = frames(guard_video, tmp, GUARD_CELL, (GUARD_FIRST - 1) / 24, n / 24 + 0.01, range(1, n + 1))
            block = [keep_thin_parts(c, f) for c, f in zip(cut(raw), raw)]
        block = [feather(in_cell(im, attack[0].size)) for im in match_colours(block, clip[0])]
        rows = grid(block, "hero_male_guard.webp")
        print(f"guard: {len(block)} frames, {COLS} x {rows} grid")


if __name__ == "__main__":
    main(*sys.argv[1:3])
