"""Cut SHOAIB's gathering and mining art (Nov 25 2026) into the game's files (docs/world.md "Gathering art").

    python -m scripts.make_gather_art herbs  mortal=grid.png yellow=grid.png mystic=grid.png earth=grid.png \
                                             heaven_lotus=one.png immortal_peach=one.png star_dew=one.png chaos_root=one.png
    python -m scripts.make_gather_art hero   female_kneel=v.mp4 male_kneel=v.mp4 female_swing=v.mp4 male_swing=v.mp4
    python -m scripts.make_gather_art sounds female_kneel=v.mp4 ... pillar=v.mp4
    python -m scripts.make_gather_art still  pick=pick.png keeper=keeper.png

herbs   The painted herbs: a grade's picture holds its four plants in a 2 x 2 grid (qi, healing / purity,
        breakthrough: alchemy.HERBS' order); the Heaven herbs are one picture each. Each plant is cut off its flat
        grey backdrop as the environment pieces are (scripts/make_env_assets.py: rembg plus a colour key, Gemini's
        sparkle and loose specks dropped, the backdrop's colour taken out of the edges), made at most 384 px, and
        written to art/herbs/<herb>.webp. art/herbs/catalog.json keeps each one's size and foot (where it meets the
        ground), as art/env/catalog.json does.
hero    The kneel and pick-swing animations, from Veo videos of each hero on a flat backdrop. Frames are taken at FPS,
        the hero cut out (rembg), and every frame set in a cell with the point between the feet at the same spot and
        the hero as tall as on the walking sheets (about 205 px standing). Written as a sheet (COLS cells a row) to
        art/gather/hero_<gender>_<move>.webp, with art/gather/sheets.json: cell, feet, cols, frames, fps and the
        marks (the frames where each part of the move starts; CLIPS below).
sounds  Short sounds cut from the same videos' own sound (CUTS below: where each one is), to art/gather/sounds/.
still   One object or person on a flat backdrop, cut the same way, to art/gather/<name>.webp.

The source files are only read. Needs ffmpeg, numpy, opencv, Pillow and rembg (isnet-general-use).
"""
import json
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

import alchemy
from scripts import make_env_assets as mea

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERBS = os.path.join(ROOT, "art", "herbs")
OUT = os.path.join(ROOT, "art", "gather")
MAX = 384
TALL = 205                                # a standing hero's height on the walking sheets (px)
COLS = 12
TYPES = ["qi", "healing", "purity", "breakthrough"]      # a grid's plants: top left, top right, bottom left, bottom right

# The part of each video that is used (seconds), how many pictures a second are kept, and the marks (seconds into the
# video) where each part of the move begins. kneel: down (to the knees), search (hands at the ground: held, played back
# and forth while the round is open), lift (the hands close and rise), rise (back to standing).
# swing: one blow, from the pick raised to just after it lands; `hit` is the frame it lands on.
CLIPS = {
    "female_kneel": {"span": (0.0, 7.6), "fps": 12, "marks": {"down": 0.0, "search": 2.0, "lift": 3.5, "rise": 5.6}},
    "male_kneel":   {"span": (0.0, 7.6), "fps": 12, "marks": {"down": 0.0, "search": 2.1, "lift": 3.5, "rise": 6.0}},
    "female_swing": {"span": (3.6, 5.4), "fps": 24, "marks": {"raise": 3.6, "hit": 4.9}},
    "male_swing":   {"span": (2.25, 3.34), "fps": 24, "marks": {"raise": 2.25, "hit": 3.15}},
}
# sounds: name → (video key, start s, length s)
CUTS = {
    "pick_1": ("female_swing", 1.26, 0.42), "pick_2": ("female_swing", 2.86, 0.42), "pick_3": ("female_swing", 4.84, 0.5),
    "pick_4": ("male_swing", 3.06, 0.5), "pick_5": ("male_swing", 2.02, 0.42),
    "kneel_1": ("female_kneel", 0.24, 0.5), "kneel_2": ("male_kneel", 0.44, 0.5),
    "rustle_1": ("female_kneel", 2.0, 1.6), "rustle_2": ("male_kneel", 2.56, 1.0),
    "rise_1": ("female_kneel", 6.44, 0.6), "rise_2": ("male_kneel", 6.44, 0.8),
    "pillar": ("pillar", 0.4, 7.2),
}


def slug(name):
    return name.lower().replace("'", "_").replace(" ", "_")


def cut(im, session, shadows=True):
    """One object off its flat backdrop: (RGBA picture, foot). As scripts/make_env_assets.cut, without the per-asset
    fixes. `shadows` False keeps dark patches the colour of a darker backdrop: a plant's soil is one, and the herb
    pictures have no cast shadows to remove."""
    from rembg import remove
    im = im.convert("RGB")
    rgb = np.asarray(im).copy()
    bg, _ = mea.backdrop(rgb.astype(int))
    ai = np.asarray(remove(im, session=session).convert("RGBA"))[..., 3].astype(np.uint8)
    dist = np.sqrt(((rgb.astype(int) - bg) ** 2).sum(2))
    k = (rgb.astype(int) * bg).sum(2) / (bg * bg).sum()
    shadow = (np.sqrt(((rgb - k[..., None] * bg) ** 2).sum(2)) < 14) & (k < 0.98) & (ai < 40)
    sure_bg = mea.joined_to_edge(dist < mea.SAME)
    alpha = np.maximum(ai, np.where(dist > mea.KEY, 255, 0)).astype(np.uint8)
    alpha[(sure_bg & (ai < 160)) | (shadow & shadows)] = 0
    alpha = mea.biggest(alpha)
    hard = cv2.erode((alpha > 127).astype(np.uint8) * 255, np.ones((3, 3), np.uint8))
    alpha = np.minimum(alpha, cv2.GaussianBlur(hard, (3, 3), 0))
    a = alpha.astype(np.float32)[..., None] / 255
    clean = np.where(a > 0.02, (rgb.astype(np.float32) - (1 - a) * bg) / np.maximum(a, 0.02), 0)
    rgb = np.clip(np.where(a > 0.98, rgb, clean), 0, 255).astype(np.uint8)
    ys, xs = np.nonzero(alpha > 8)
    x0, y0, x1, y1 = max(0, xs.min() - 3), max(0, ys.min() - 3), xs.max() + 4, ys.max() + 4
    out = Image.fromarray(np.dstack([rgb, alpha])[y0:y1, x0:x1])
    s = min(1.0, MAX / max(out.size))
    if s < 1:
        out = out.resize((round(out.width * s), round(out.height * s)), Image.LANCZOS)
    return out, mea.foot(np.asarray(out)[..., 3])


def unsparkle(im, spots):
    """Paint Gemini's sparkle out where it lies on the object itself: `spots` = [(x, y, radius)] in shares of the picture."""
    a = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)
    m = np.zeros(a.shape[:2], np.uint8)
    for x, y, r in spots:
        cv2.circle(m, (round(x * a.shape[1]), round(y * a.shape[0])), round(r * a.shape[1]), 255, -1)
    return Image.fromarray(cv2.cvtColor(cv2.inpaint(a, m, 7, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB))


def pairs(args):
    out = {}
    for a in args:
        k, _, v = a.partition("=")
        v, _, spots = v.partition("@")                     # picture.png@x,y,r;x,y,r : sparkles to paint out first
        out[k] = (v, [tuple(float(n) for n in s.split(",")) for s in spots.split(";") if s])
    return out


def herbs(args):
    from rembg import new_session
    session = new_session("isnet-general-use")
    os.makedirs(HERBS, exist_ok=True)
    cat_path = os.path.join(HERBS, "catalog.json")
    cat = json.load(open(cat_path)) if os.path.exists(cat_path) else {}
    singles = {slug(n): n for g in alchemy.HERBS.values() for n, _ in g.values()}
    for key, (src, spots) in pairs(args).items():
        im = Image.open(src).convert("RGB")
        if spots:
            im = unsparkle(im, spots)
        if key in singles:
            jobs = [(key, im)]
        else:
            grade = key.capitalize()
            w, h = im.size
            jobs = [(slug(alchemy.HERBS[grade][t][0]), im.crop(((i % 2) * w // 2, (i // 2) * h // 2,
                                                                (i % 2 + 1) * w // 2, (i // 2 + 1) * h // 2)))
                    for i, t in enumerate(TYPES)]
        for name, pic in jobs:
            out, ft = cut(pic, session, shadows=False)
            out.save(os.path.join(HERBS, name + ".webp"), "WEBP", quality=90, method=6)
            cat[name] = {"w": out.width, "h": out.height, "foot": ft}
            print(f"{name}: {out.width} x {out.height}, foot {ft}", flush=True)
    json.dump(dict(sorted(cat.items())), open(cat_path, "w"), indent=1)


def still(args):
    from rembg import new_session
    session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    for key, (src, spots) in pairs(args).items():
        im = Image.open(src).convert("RGB")
        out, _ = cut(unsparkle(im, spots) if spots else im, session)
        out.save(os.path.join(OUT, key + ".webp"), "WEBP", quality=90, method=6)
        print(f"{key}: {out.width} x {out.height}", flush=True)


def frames(video, t0, t1, fps):
    w, h = 960, 540                                   # half size: the hero is still ~470 px tall, over twice a cell
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t0}", "-to", f"{t1}", "-i", video, "-vf",
                          f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    return [Image.fromarray(f) for f in a]


def hero(args):
    from rembg import new_session, remove
    session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    meta_path = os.path.join(OUT, "sheets.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    for key, (video, _) in pairs(args).items():
        clip = CLIPS[key]
        t0, t1 = clip["span"]
        cut_frames = []
        # the height and the feet come from the video's first frame, where the hero stands as on the start picture
        first = np.asarray(remove(frames(video, 0, 0.05, 24)[0], session=session))
        ys, xs = np.nonzero(first[..., 3] > 96)
        scale = TALL / (ys.max() - ys.min())
        low = ys >= ys.max() - 6
        fx, fy = xs[low].mean(), ys.max()
        for f in frames(video, t0, t1, clip["fps"]):
            a = np.asarray(remove(f, session=session)).copy()
            a[380:, 700:, 3] = 0                                  # Veo's mark and the sparkle, bottom right
            al = mea.biggest(a[..., 3])
            a[..., 3] = np.minimum(al, cv2.GaussianBlur(cv2.erode((al > 127).astype(np.uint8) * 255, np.ones((3, 3), np.uint8)), (3, 3), 0))
            cut_frames.append(a)
        box = [min(np.nonzero(a[..., 3] > 16)[1].min() for a in cut_frames), min(np.nonzero(a[..., 3] > 16)[0].min() for a in cut_frames),
               max(np.nonzero(a[..., 3] > 16)[1].max() for a in cut_frames), max(np.nonzero(a[..., 3] > 16)[0].max() for a in cut_frames)]
        half = max(fx - box[0], box[2] - fx) * scale + 6
        cw = int(np.ceil(half * 2 / 16) * 16)
        up = (fy - box[1]) * scale + 8
        down = max(0, box[3] - fy) * scale + 8
        ch = int(np.ceil((up + down) / 16) * 16)
        feet = [cw // 2, ch - int(round(down))]
        n = len(cut_frames)
        rows = (n + COLS - 1) // COLS
        sheet = Image.new("RGBA", (cw * COLS, ch * rows))
        for i, a in enumerate(cut_frames):
            im = Image.fromarray(a)
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
            sheet.alpha_composite(im, ((i % COLS) * cw + feet[0] - round(fx * scale), (i // COLS) * ch + feet[1] - round(fy * scale)))
        gender, move = key.split("_")
        name = f"hero_{gender}_{move}.webp"
        sheet.save(os.path.join(OUT, name), "WEBP", quality=84, method=6)
        meta[key] = {"src": f"/art/gather/{name}", "cell": [cw, ch], "feet": feet, "cols": COLS, "frames": n, "fps": clip["fps"],
                     "marks": {m: min(n - 1, round((t - t0) * clip["fps"])) for m, t in clip["marks"].items()}}
        print(key, meta[key], flush=True)
    json.dump(dict(sorted(meta.items())), open(meta_path, "w"), indent=1)


def sounds(args):
    vids = {k: v for k, (v, _) in pairs(args).items()}
    os.makedirs(os.path.join(OUT, "sounds"), exist_ok=True)
    for name, (key, t0, length) in CUTS.items():
        if key not in vids:
            continue
        out = os.path.join(OUT, "sounds", name + ".mp3")
        fade = min(0.12, length / 4)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t0}", "-t", f"{length}", "-i", vids[key], "-vn", "-ac", "1",
                        "-af", f"afade=t=in:d=0.01,afade=t=out:st={length - fade}:d={fade},loudnorm=I=-18:TP=-2",
                        "-ar", "44100", "-b:a", "64k", out], check=True)
        print(name, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    {"herbs": herbs, "hero": hero, "sounds": sounds, "still": still}[sys.argv[1]](sys.argv[2:])
