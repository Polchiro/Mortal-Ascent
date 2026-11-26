"""Cut a beast's four animation videos (SHOAIB's, Gemini) into the frame sheets the fight plays
(art/beasts/sheets/<slug>/: idle, attack, hit, death + sheets.json; web/explore_play.beast_sheets, web/static/fight.js
`BeastSheets`; docs/web.md "Animated beasts").

    python -m scripts.make_beast_sheets grey_wolf idle.mp4 attack.mp4 hit.mp4 death.mp4 [--cache DIR]

Each video is 1280 x 720 at 24 fps (Flow's 1920 x 1080 is scaled down; one video may be given for two moves, its
seconds in CLIPS): one beast, side on, facing left (toward the cultivator), on a plain backdrop, the
camera still. What is taken from each (CLIPS):
- idle: the stretch (3-6 s) whose last frame best meets its first (scripts/make_heroine_walk.stride), looped;
- attack, hit, death: the part where the beast acts, from its first frame (standing as in idle) to the end of the move.
Every frame is cut out (rembg, as the beast art is), Gemini's sparkle mark and the floor shadow dropped, and a
painted slab under the paws cut away (`slab`: its top edge and how deep the paws sink into it). Then each video is placed on
the beast's own picture (art/beasts/<slug>.png), so the fight's beast never changes size or place between them: its
first frame scaled to the same size of outline and stood on the same ground under the same spot, and every frame of that video moved the same way. `match`: a video whose beast drifts in
colour (the grey wolf's death: lighter and greyer once it lies down) has each frame's colours brought to the named
video's first frame.

All frames share one cell, the box that holds every frame of all four (the attack lunges further left, the death lies
further right than the picture), at SCALE of the picture's pixels. sheets.json says where the picture sits in that
cell (`still`, cell px), so the page lays the frames exactly over it; and per sheet its frames (COLS wide, rows filled
exactly so the idle can be stepped in CSS), its length (`ms`), and for the attack the frame it bites on (`bite`) and
how far its jaws then reach ahead of the picture's nose (`reach`, a share of the picture's width) and where they are
(`bite_x`, a share of the cell's width); for the idle where its front is (`nose_x`); for the death the frame it lands
on (`impact`). The page uses `bite_x` and `nose_x` to keep the beast and the cultivator from running into each other.
Needs ffmpeg, numpy, Pillow, scipy and rembg. --cache keeps the cut frames, so a second run only places them.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from scripts.make_heroine_walk import stride

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24
STEP = 2                        # every 2nd video frame: 12 frames a second, as the cultivator's moves
COLS = 8
SCALE = 0.6                     # sheet pixels per pixel of the beast's picture
KINDS = ("idle", "attack", "hit", "death")
# per beast: the seconds taken from each video, a slab to cut (its top edge, a share of the frame's height), the
# videos to recolour (to whose colours), how long the attack plays in the fight (ms)
CLIPS = {
    "grey_wolf": {"attack": (0.0, 3.0), "hit": (0.0, 1.5), "death": (0.0, 2.5), "idle_span": (72, 144),
                  "slab": {"idle": (0.80, 0.12)}, "match": {"death": "hit"}, "attack_ms": 2200},
    "wild_boar": {"attack": (3.6, 6.1), "hit": (0.6, 1.45), "death": (4.42, 6.5), "idle_span": (84, 144),
                  "attack_ms": 2000, "bite": 16, "white": ("hit",)},
    "field_viper": {"attack": (2.5, 5.9), "hit": (1.6, 3.0), "death": (3.0, 5.6), "idle_span": (30, 50),
                    "idle_until": 2.1, "attack_ms": 2400, "fade": {"attack": 90}},
    "stray_dog_pack": {"attack": (2.6, 3.8), "hit": (1.4, 2.9), "death": (4.0, 6.2), "idle_span": (36, 60),
                       "idle_until": 2.5, "attack_ms": 1800, "pingpong": ("attack",)},
    "wild_ox": {"attack": (2.0, 5.6), "hit": (1.7, 3.4), "death": (4.4, 6.4), "idle_span": (30, 44),
                "idle_from": 5.95, "attack_ms": 2400, "bite": 33, "white": ("hit", "death")},
    "old_black_bear": {"attack": (2.3, 5.1), "hit": (2.05, 3.45), "death": (3.9, 6.4), "idle_span": (30, 46),
                       "idle_from": 5.8, "attack_ms": 2600, "bite": 27, "impact": 10, "white": ("death",)},
                       # its attack from the remade video with headroom (Nov 26): the first one's head left the video
    "iron_hide_boar": {"attack": (2.6, 4.45), "hit": (2.15, 3.3), "death": (4.2, 6.2), "idle_span": (20, 27),
                       "idle_from": 6.7, "attack_ms": 2000, "white": ("hit", "death"), "pingpong": ("attack",)},
    # the fox leapt out of the video's left edge mid-pounce: its stalk, its spring and its landing snap, joined
    "red_fox": {"attack": ((0.8, 1.75), (3.2, 3.8), (4.62, 5.6)), "hit": (0.3, 2.6), "death": (4.0, 6.1),
                "idle_span": (30, 44), "idle_from": 5.9, "attack_ms": 2400,
                "mark": ((1130, 565, 1195, 632), (1140, 338, 1202, 428)),
                "drop": {"hit": ((0.45, 0.78),), "death": ((4.52, 4.78),)}},
    # the first bird: one wingbeat as its idle (it flew higher and lost its wing tips off the top later in the video)
    "wind_feather_falcon": {"attack": (3.0, 6.85), "hit": (0.4, 1.9), "death": (4.2, 6.6), "idle_span": (40, 51),
                            "idle_until": 2.15, "attack_ms": 2600, "bite": 27, "fade": {"attack": ("top", 40)},
                            "place_as": {"death": "hit"}, "floor": ("attack", "hit", "death")},
    "shadow_wolf": {"attack": (4.2, 7.9), "hit": (1.0, 2.8), "death": (3.3, 5.8), "idle_span": (36, 60),
                    "idle_until": 4.1, "attack_ms": 2600},
    "horned_stag": {"attack": (4.1, 7.6), "hit": (1.0, 3.2), "death": (5.45, 7.6), "idle_span": (36, 60),
                    "idle_until": 4.1, "attack_ms": 2600},
}
MARK = (1100, 540, 1230, 660)   # Gemini's sparkle sits in here (x0, y0, x1, y1 of the 1280 x 720 frame)
# (a beast's own `mark`: tighter boxes where its pale tail tip passes near the sparkle (the fox's), or a second sparkle
# the video drew; a pale blob with the beast all round it is its own fur, not the sparkle, and is kept)


def video_frames(video, numbers):
    """The video's frames with these numbers (0-based), as RGB pictures."""
    w, h = 1280, 720
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-"],                # Flow's 1920 x 1080 brought to 1280 x 720
                          capture_output=True, check=True).stdout
    all_ = np.frombuffer(data, np.uint8).reshape(-1, h, w, 3)
    return [Image.fromarray(all_[n]) for n in numbers]


def off_slab(a, top, depth):
    """Cut a painted slab away: below its top edge (a share of the height) keep only the paws, which sink `depth`
    into it: what the cut-out kept under the legs' own columns, joined to the legs."""
    h = a.shape[0]
    y = int(h * top)
    legs = (a[y - 6:y, :, 3] > 128).any(0)
    cols = ndimage.binary_dilation(legs, iterations=14)
    keep = np.zeros(a.shape[:2], bool)
    keep[:y] = True
    keep[y:y + int(h * depth)] = cols[None, :]
    a[..., 3] = np.where(keep, a[..., 3], 0)
    lab, n = ndimage.label(a[..., 3] > 60)                   # what is left of the stone, no longer joined: dropped
    above = set(np.unique(lab[:y][a[:y, :, 3] > 60])) - {0}
    a[..., 3] = np.where(np.isin(lab, list(above)) | (a[..., 3] <= 60) & keep, a[..., 3], 0)
    return a


def cut_one(im, session, slab=None, white=False, fade=0, mark=MARK):
    """The beast alone: cut out, no mark, no slab, no shadow or loose bits. `white`: a white slash streak the video drew
    over it (the unseen blow) dropped too: near-white, colourless pixels."""
    from rembg import remove
    a = np.asarray(remove(im, session=session)).copy()
    if white:
        px = np.asarray(im).astype(np.int16)
        streak = (px.min(-1) > 175) & ((px.max(-1) - px.min(-1)) < 30)
        a[..., 3] = np.where(ndimage.binary_dilation(streak, iterations=2), 0, a[..., 3])
    px = np.asarray(im).astype(np.float32)
    bg = np.median(np.concatenate([px[:20].reshape(-1, 3), px[:, :20].reshape(-1, 3)]), 0).mean()
    for x0, y0, x1, y1 in (mark if isinstance(mark[0], (tuple, list)) else [mark]):   # one box, or several
        box = px[y0:y1, x0:x1]                               # the sparkle: the biggest pale, colourless blob there
        pale = (box.mean(-1) > np.median(box.mean(-1)) + 8) & ((box.max(-1) - box.min(-1)) < 25)
        lab, n = ndimage.label(pale)
        if n:
            sizes = ndimage.sum(pale, lab, range(1, n + 1))
            star = ndimage.binary_dilation(lab == 1 + int(np.argmax(sizes)), iterations=3)
            ring = ndimage.binary_dilation(star, iterations=4) & ~star
            backdrop = ((box.max(-1) - box.min(-1)) < 18) & (np.abs(box.mean(-1) - bg) < 25)
            if not ring.any() or backdrop[ring].mean() > 0.4:   # set on the backdrop: the sparkle, not a pale
                a[y0:y1, x0:x1, 3] = np.where(star, 0, a[y0:y1, x0:x1, 3])   # tail tip lying over it (the fox's)
        grey = ((box.max(-1) - box.min(-1)) < 18) & (box.mean(-1) > bg - 35)     # the backdrop the cutter kept by
        lab, n = ndimage.label(grey)                                             # the mark: big patches, not the
        if n:                                                                    # paw's own pale specks
            sizes = ndimage.sum(grey, lab, range(1, n + 1))
            grey = np.isin(lab, 1 + np.flatnonzero(sizes >= 150))
            a[y0:y1, x0:x1, 3] = np.where(grey, 0, a[y0:y1, x0:x1, 3])
    if slab:
        a = off_slab(a, *slab)
    if fade:                                                 # the body ran off the video's edge: fade it out
        edge, px = fade if isinstance(fade, tuple) else ("right", fade)     # instead of a hard straight cut
        if edge == "right":
            ramp = np.clip(np.arange(a.shape[1])[::-1] / px, 0, 1)
            a[..., 3] = (a[..., 3] * ramp[None, :]).astype(np.uint8)
        else:                                                               # "top": a head reared out of the video
            ramp = np.clip(np.arange(a.shape[0]) / px, 0, 1)
            a[..., 3] = (a[..., 3] * ramp[:, None]).astype(np.uint8)
    alpha = a[..., 3] > 24
    lab, n = ndimage.label(ndimage.binary_dilation(alpha, iterations=3))
    if n > 1:                                                # the beast: its largest piece and what touches it
        sizes = ndimage.sum(alpha, lab, range(1, n + 1))
        a[..., 3] = np.where(lab == 1 + int(np.argmax(sizes)), a[..., 3], 0)
    a[..., 3] = np.where(a[..., 3] < 24, 0, a[..., 3])
    solid = np.flatnonzero((a[..., 3] > 128).any(1))
    if len(solid):
        a[solid.max() + 1:, :, 3] = 0                        # nothing below its lowest solid part: the floor shadow
    return Image.fromarray(a, "RGBA")


def cut_clip(kind, video, numbers, cfg, cache, session):
    out, raw = [], None
    for n in numbers:
        path = os.path.join(cache, kind, f"{n:03d}.png") if cache else None
        if path and os.path.exists(path):
            out.append(Image.open(path).convert("RGBA"))
            continue
        if session is None:
            from rembg import new_session
            session = new_session("isnet-general-use")
        if raw is None:
            raw = dict(zip(numbers, video_frames(video, numbers)))
        im = cut_one(raw[n], session, cfg.get("slab", {}).get(kind), kind in cfg.get("white", ()),
                     cfg.get("fade", {}).get(kind, 0), cfg.get("mark", MARK))
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            im.save(path)
        out.append(im)
        print(f"  {kind} {n}", flush=True)
    return out, session


def spans(clip):
    """A move's seconds: one (start, end), or several joined ((start, end), ...)."""
    return list(clip) if isinstance(clip[0], (tuple, list)) else [clip]


def solid(im):
    return np.asarray(im.getchannel("A")) > 128


def feet_x(a):
    rows = np.flatnonzero(a.any(1))
    low = a[rows.max() - max(2, int(len(rows) * 0.08)):rows.max() + 1]
    return float(np.flatnonzero(low.any(0)).mean()), int(rows.max())


def placing(first, still):
    """(scale, dx, dy): this video's first frame onto the picture: the same size of outline (its width and height
    together; Gemini redrew the beast a little in each video, so its body fills its outline differently), the same
    ground line, its paws under the same spot."""
    a, b = solid(first), solid(still)
    def size(m):
        ys, xs = np.where(m)
        return xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    (wa, ha), (wb, hb) = size(a), size(b)
    s = (wb / wa * hb / ha) ** 0.5
    fa, ga = feet_x(a)
    fb, gb = feet_x(b)
    return s, fb - fa * s, (gb + 1) - (ga + 1) * s


def match(images, ref):
    """Each frame's body colours brought to the reference's (mean and spread per channel)."""
    def body(im):
        a = np.asarray(im).astype(np.float32)
        return a[..., :3][a[..., 3] > 200]
    r = body(ref)
    mu_r, sd_r = r.mean(0), r.std(0)
    out = []
    for im in images:
        a = np.asarray(im).astype(np.float32)
        g = body(im)
        a[..., :3] = ((a[..., :3] - g.mean(0)) / np.maximum(g.std(0), 1) * sd_r + mu_r).clip(0, 255)
        out.append(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return out


def main(slug, videos, cache=None):
    cfg = CLIPS[slug]
    still = Image.open(os.path.join(ROOT, "art", "beasts", f"{slug}.png")).convert("RGBA")
    picks = {}
    idle_src = videos["idle"]
    if cfg.get("idle_until") or cfg.get("idle_from"):         # its breath only from a calm stretch of the video
        idle_src = os.path.join(cache or "/tmp", f"{slug}_idle_part.mp4")
        os.makedirs(os.path.dirname(idle_src), exist_ok=True)
        part = ["-ss", str(cfg.get("idle_from", 0))] + (["-to", str(cfg["idle_until"])] if cfg.get("idle_until") else [])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", videos["idle"]] + part + ["-an", idle_src], check=True)
    a, n = stride(idle_src, 0, cfg["idle_span"])
    count = COLS * max(1, round(n / STEP / COLS))
    a += round(cfg.get("idle_from", 0) * FPS)                 # back to the whole video's frame numbers
    picks["idle"] = [a + round(j * n / count) for j in range(count)]          # its own end (a + n) is the next start
    idle_ms = round(n / FPS * 1000)
    for kind in KINDS[1:]:
        picks[kind] = []
        for s0, s1 in spans(cfg[kind]):                       # one stretch of the video, or several joined
            picks[kind] += list(range(round(s0 * FPS), round(s1 * FPS), STEP))
        for d0, d1 in cfg.get("drop", {}).get(kind, ()):      # frames an effect covered the beast in: left out
            picks[kind] = [n for n in picks[kind] if not d0 * FPS <= n < d1 * FPS]
    clips, session = {}, None
    for kind in KINDS:
        clips[kind], session = cut_clip(kind, videos[kind], picks[kind], cfg, cache, session)
    for kind in cfg.get("pingpong", ()):                      # it ran off the video mid-move: there and back again
        clips[kind] = clips[kind] + clips[kind][-2:0:-1]
    for kind, ref in cfg.get("match", {}).items():
        clips[kind] = match(clips[kind], clips[ref][0])

    # every frame on the picture's ground, in the picture's pixels; then the box that holds them all
    placed, places = {}, {}
    for kind in KINDS:
        places[kind] = placing(clips[kind][0], still)
    for kind, like in cfg.get("place_as", {}).items():        # the same video, the camera still: placed as that move
        places[kind] = places[like]                           # (the falcon flew further off before it died)
    for kind in KINDS:
        s, dx, dy = places[kind]
        placed[kind] = []
        for im in clips[kind]:
            big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            y = round(dy)
            if kind in cfg.get("floor", ()):                  # never below the ground the picture stands on: a bird
                y -= max(0, y + big.getbbox()[3] - still.height)    # drawn with its talons on it lands on it, dying
            placed[kind].append((big, round(dx), y))
    boxes = []
    for kind in KINDS:
        for big, x, y in placed[kind]:
            l, t, r, b = big.getbbox()
            boxes.append((l + x, t + y, r + x, b + y))
    X0, Y0 = min(b[0] for b in boxes) - 4, min(b[1] for b in boxes) - 4
    X1, Y1 = max(b[2] for b in boxes) + 4, max(b[3] for b in boxes) + 2
    cw, ch = round((X1 - X0) * SCALE), round((Y1 - Y0) * SCALE)

    def cell(big, x, y):
        return big.crop((X0 - x, Y0 - y, X1 - x, Y1 - y)).resize((cw, ch), Image.LANCZOS)   # outside it: transparent

    out_dir = os.path.join(ROOT, "art", "beasts", "sheets", slug)
    os.makedirs(out_dir, exist_ok=True)
    data = {"cell": [cw, ch], "still": [round(-X0 * SCALE, 2), round(-Y0 * SCALE, 2),
                                        round(still.width * SCALE, 2), round(still.height * SCALE, 2)],
            "sheets": {}}
    for kind in KINDS:
        frames = [cell(*p) for p in placed[kind]]
        rows = -(-len(frames) // COLS)
        sheet = Image.new("RGBA", (cw * COLS, ch * rows), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.alpha_composite(f, ((i % COLS) * cw, (i // COLS) * ch))
        sheet.save(os.path.join(out_dir, f"{kind}.webp"), quality=84, method=6)
        info = {"src": f"/art/beasts/sheets/{slug}/{kind}.webp", "frames": len(frames), "cols": COLS, "rows": rows}
        if kind == "idle":
            info["ms"] = idle_ms
            info["nose_x"] = round(frames[0].getbbox()[0] / cw, 4)              # its front, standing
        elif kind == "attack":
            info["ms"] = cfg["attack_ms"]
            lefts = [f.getbbox()[0] for f in frames]
            lo, hi = len(frames) // 4, len(frames) * 3 // 4
            bite = cfg.get("bite", lo + int(np.argmin(lefts[lo:hi])))         # the jaws furthest forward (or set by eye)
            info["bite"] = bite
            info["reach"] = round(max(0, lefts[0] - lefts[bite]) / (still.width * SCALE), 4)
            info["bite_x"] = round(lefts[bite] / cw, 4)                         # its jaws, at the bite
        else:
            if len(spans(cfg[kind])) > 1 or kind in cfg.get("drop", {}):
                info["ms"] = round(len(frames) * STEP / FPS * 1000)            # the frames it really plays
            else:
                s0, s1 = cfg[kind]
                info["ms"] = round((s1 - s0) * 1000)
            if kind == "death":
                tops = [f.getbbox()[1] for f in frames]
                info["impact"] = cfg.get("impact", next(i for i, t in enumerate(tops) if t >= tops[-1] - 0.04 * ch))   # down
        data["sheets"][kind] = info
        print(f"{kind}: {len(frames)} frames, {COLS} x {rows}, {info}")
    with open(os.path.join(out_dir, "sheets.json"), "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"cell {cw} x {ch}, the picture at {data['still']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = None
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 5:
        sys.exit(__doc__)
    main(args[0], dict(zip(KINDS, args[1:])), cache)
