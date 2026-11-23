"""Build the female cultivator's own Strike and Break from SHOAIB's two videos of her (looks.ATTACK_SHEETS["female"],
web/static/fight.js `sweep`; docs/web.md "Her Strike and Break"): frame by frame, each starting and ending in her
fighting stance (scripts/make_heroine_stance.py), so she goes stance, attack, stance without a jump.

The videos (Gemini, 1280 x 720, 24 fps, 10 s; their first frame was her stance) are one figure on a pale grey backdrop:
- slash: she moves at 1.0 s, raises the sword (to 2.25 s), cuts in one diagonal arc with a blue Qi trail (2.5 s, the
  hit), holds while the trail fades (to 4.5 s), steps back into her stance (by 6.5 s);
- break: Qi gathers round her (1.25-3.25 s), she leaps with the sword overhead and drives it into the ground (4.5 s,
  the hit), a blue and orange explosion and its sparks fill the frame (to 8 s), she rises into her stance (by 8.5 s).
The slow parts are thinned and the fast ones kept whole (PICKS); the Break's explosion is left out (its frames are the
whole picture and can't be cut out): the fight's own Break effects burst there (fight.js `slam`), and she holds the
landing frame through them. Every frame is cut out (rembg), with the Break's blue Qi swirl kept where it touches her
(the slash's arc is left out: the fight draws its own sword trail), Gemini's mark and stray sparks dropped. Her leap
across the Break video is taken out (`in_place`): the fight's own dash carries her to the beast and back.

Each video is placed on her stance (its first frame on the stance sheet's first: as tall, feet on the same line and
over the same spot), so a sheet's frame 0 is her stance. Both sheets are drawn at the stance's own scale (1 cell px =
1.5 fight-canvas px) in a cell of their own that holds the arc and the overhead sword (`box`: where it sits on the
1024 x 559 fight canvas, as shares). Each ends on the spot it started from (`home`: the steps back drift onto it).
`keys` play it ([ms, frame]); `tip`: how far right the blade reaches at the hit,
as a share of the canvas (the dash stops it at the beast). The numbers to copy into looks.py are printed.

    python -m scripts.make_heroine_attacks slash.mp4 break.mp4 [--cache DIR]

Needs ffmpeg, numpy, Pillow, scipy and rembg.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "portraits", "fight")
FPS, COLS = 24, 8
CANVAS = (1024, 559)
CELL_SCALE = 1.5                         # fight-canvas px per sheet px, as every cultivator sheet
STANCE_AT = (208, 3)                     # where a 320 x 360 cultivator cell sits on the canvas (make_hero_attack OFFSET)


def span(a, b, step):
    return list(range(round(a * FPS), round(b * FPS), step))


# the video frames taken (0-based), in order, and the moment of the hit among them (`hit`: its index)
PICKS = {
    "strike": {"frames": span(1.0, 2.25, 3) + span(2.25, 3.0, 2) + span(3.0, 4.5, 6) + span(4.5, 6.6, 3), "hit_at": 2.5,
               "crop": (40, 0, 1040, 720), "qi": False, "in_place": False, "home_from": 25},
    "break": {"frames": span(1.0, 3.25, 4) + span(3.25, 4.3, 2) + [103, 139] + span(6.4, 7.3, 2) + span(7.3, 8.6, 3),
              "hit_at": 4.29, "crop": (0, 0, 1280, 720), "qi": True, "in_place": True, "home_from": 29},
}


def video_frames(video, numbers, crop):
    x0, y0, x1, y1 = crop
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    every = np.frombuffer(data, np.uint8).reshape(-1, y1 - y0, x1 - x0, 3)
    return {n: Image.fromarray(every[n]) for n in numbers}


def cut_one(im, session, qi=True, near=None):
    """Her alone: the cut-out, plus (qi) the blue Qi touching her, which the cutter fades, with a soft edge; the mark
    and loose sparks gone. The slash's arc is not kept (its pale glow can't be told from the backdrop cleanly): the
    fight draws its own sword trail."""
    from rembg import remove
    a = np.asarray(remove(im, session=session)).copy()
    px = np.asarray(im).astype(np.float32)
    if qi:
        blue = np.clip((px[..., 2] - px[..., 0] - 30) / 40, 0, 1) * (px[..., 2] > 110)   # blue Qi, not the grey backdrop
        glow = ndimage.gaussian_filter(blue, 1.2) * 255
        a[..., 3] = np.maximum(a[..., 3], glow).astype(np.uint8)
        a[..., :3] = np.where((glow > 20)[..., None], px, a[..., :3]).astype(np.uint8)
    solid = a[..., 3] > 40
    lab, n = ndimage.label(ndimage.binary_dilation(solid, iterations=2))
    if n > 1:                                                                    # her, and whatever is joined to her
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        if near is not None:                                                     # the piece where she was a moment ago:
            over = ndimage.sum(solid & near, lab, range(1, n + 1))               # a painted blow can be bigger than she is
            sizes = over if over.max() > 0 else sizes
        a[..., 3] = np.where(lab == 1 + int(np.argmax(sizes)), a[..., 3], 0)
    a[..., 3] = np.where(a[..., 3] < 20, 0, a[..., 3])
    return Image.fromarray(a, "RGBA")


def stance_first():
    """Her stance's first frame on the fight canvas (the stance sheet's cell placed as the fight places it)."""
    sheet = Image.open(os.path.join(OUT, "hero_female_stance.webp")).convert("RGBA")
    cell = sheet.crop((0, 0, 320, 360)).resize((480, 540), Image.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(cell, STANCE_AT)
    return canvas


def body_x(im):
    """Where her body is across the frame: the middle of what isn't Qi glow, weighted to the torso."""
    a = np.asarray(im).astype(np.float32)
    body = (a[..., 3] > 128) & (a[..., 2] - a[..., 0] < 32)
    ys, xs = np.where(body)
    top, bot = ys.min(), ys.max()
    mid = (ys > top + 0.2 * (bot - top)) & (ys < top + 0.65 * (bot - top))
    return float(xs[mid].mean())


def offset(a, b, reach=120):
    """How far (px, across) frame b must move to lie best over frame a: the shift where their outlines overlap most."""
    ma, mb = solid(a), solid(b)
    best = (-1, 0)
    for dx in range(-reach, reach + 1):
        shifted = np.roll(mb, dx, axis=1)
        if dx > 0:
            shifted[:, :dx] = False
        elif dx < 0:
            shifted[:, dx:] = False
        score = (ma & shifted).sum()
        if score > best[0]:
            best = (score, dx)
    return best[1]


def home(frames, start):
    """She ends on the spot she started from: the last frame is moved onto the first (where their outlines overlap
    most), and the frames from `start` on are moved by a growing share of that, so she drifts home as she steps back."""
    off = offset(frames[0], frames[-1])
    if not off:
        return frames
    out = frames[:start]
    n = len(frames) - 1
    for i in range(start, len(frames)):
        dx = round(off * (i - start) / max(1, n - start))
        im = frames[i]
        moved = Image.new("RGBA", im.size, (0, 0, 0, 0))
        moved.alpha_composite(im.crop((max(0, -dx), 0, im.width - max(0, dx), im.height)), (max(0, dx), 0))
        out.append(moved)
    print(f"  last frame moved {off:+d} px onto the first, from frame {start}")
    return out


def solid(im):
    return np.asarray(im.getchannel("A")) > 128


def feet(m):
    ys, xs = np.where(m)
    low = ys >= ys.max() - (ys.max() - ys.min()) * 0.04
    return float(xs[low].mean()), int(ys.max()), int(ys.max() - ys.min())


def main(videos, cache=None):
    from rembg import new_session
    session = None
    ref = feet(solid(stance_first()))
    data = {}
    for kind, video in videos.items():
        pk = PICKS[kind]
        cut = []
        raw = None
        for n in pk["frames"]:
            path = os.path.join(cache, kind, f"{n:03d}.png") if cache else None
            if path and os.path.exists(path):
                cut.append(Image.open(path).convert("RGBA"))
                continue
            if raw is None:
                raw = video_frames(video, pk["frames"], pk["crop"])
            if session is None:
                session = new_session("isnet-general-use")
            im = cut_one(raw[n], session, pk["qi"])
            if path:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                im.save(path)
            cut.append(im)
            print(f"  {kind} {n}", flush=True)
        fx, gy, h = feet(solid(cut[0]))                                          # frame 0 onto her stance
        s = ref[2] / h
        dx, dy = ref[0] - fx * s, ref[1] - gy * s
        travel = [0.0] * len(cut)
        if pk["in_place"]:                                                       # her leap across the frame is taken out:
            cx = [body_x(im) for im in cut]                                      # the fight's own dash carries her there
            sm = [np.mean(cx[max(0, i - 1):i + 2]) for i in range(len(cx))]
            travel = [v - sm[0] for v in sm]
        placed = [(im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS), round(dx - travel[i] * s), round(dy))
                  for i, im in enumerate(cut)]
        boxes = [(b[0] + x, b[1] + y, b[2] + x, b[3] + y) for big, x, y in placed for b in [big.getbbox()]]
        X0, Y0 = min(b[0] for b in boxes) - 6, min(b[1] for b in boxes) - 6
        X1, Y1 = max(b[2] for b in boxes) + 6, max(b[3] for b in boxes) + 4
        cw, ch = round((X1 - X0) / CELL_SCALE), round((Y1 - Y0) / CELL_SCALE)
        frames = [big.crop((X0 - x, Y0 - y, X1 - x, Y1 - y)).resize((cw, ch), Image.LANCZOS) for big, x, y in placed]
        frames = home(frames, pk["home_from"])
        rows = -(-len(frames) // COLS)
        sheet = Image.new("RGBA", (cw * COLS, ch * rows), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.alpha_composite(f, ((i % COLS) * cw, (i // COLS) * ch))
        name = f"hero_female_{kind}_sheet.webp"
        sheet.save(os.path.join(OUT, name), quality=84, method=6)
        hit = min(range(len(pk["frames"])), key=lambda i: abs(pk["frames"][i] - pk["hit_at"] * FPS))
        tip = max(b[2] for b in boxes[hit:hit + 3]) / CANVAS[0]
        data[kind] = {"src": f"/art/portraits/fight/{name}", "frames": len(frames), "cols": COLS, "rows": rows,
                      "box": [round(X0 / CANVAS[0], 4), round(Y0 / CANVAS[1], 4), round((X1 - X0) / CANVAS[0], 4),
                              round((Y1 - Y0) / CANVAS[1], 4)],
                      "hit_frame": hit, "tip": round(tip, 4)}
        print(f"{name}: {len(frames)} frames, {COLS} x {rows}, cell {cw} x {ch}, hit frame {hit}")
    print(json.dumps(data, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = None
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    main({"strike": args[0], "break": args[1]}, cache)
