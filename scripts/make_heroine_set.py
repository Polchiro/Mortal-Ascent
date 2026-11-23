"""Build the female cultivator's kick, Guard, fist, palm and finger movements from SHOAIB's Nov 23 videos of her
(looks.MOTION_SHEETS[...]["female"], looks.GUARD_SHEETS["female"]; docs/web.md "Her movements"). Each video starts
and ends in her fighting stance (its first frame was her stance picture), as her Strike and Break do
(scripts/make_heroine_attacks.py, whose tools this uses), so she goes stance, move, stance without a jump.

The videos (Gemini, 1280 x 720, 24 fps, 10 s) are one figure on a plain grey backdrop, sword held low in her right
hand, the move made with her free left hand or her front leg:
- kick: she gathers (1.4 s), lifts her front leg and snaps a high side kick out (2.5 s), holds it (to 4.4 s), draws
  the leg back and settles (by 6.2 s);
- guard: she steps in and raises the sword across her body (1.0-2.0 s), the blow lands on the blade in sparks
  (2.2 s), her sleeves and skirt whip round, she steadies behind the blade (to 6 s) and lowers it (by 7.3 s);
- fist: a quick jab with her left fist (1.3 s), drawn back (3.1 s), a lunging punch (3.6 s), held, back by 7.8 s;
- palm: her arm drawn back (1.6 s), a lunging open-palm strike (2.7 s), held (to 4.5 s), back by 6.5 s;
- finger: her arm drawn in (1.7 s), a deep lunge with two fingers thrust out (2.3 s), held (to 5.2 s), back by 6.7 s.
The slow parts are thinned and the fast ones kept whole (MOVES `frames`: the video frames taken). Every frame is cut
out (rembg), Gemini's mark, the Guard video's painted streak and loose sparks dropped (only what is joined to her
stays). The Guard's step forward is taken out (`in_place`): the beast comes to her, and stops at her front.

Each video is placed on her stance by its own first frame (the stance picture: as tall, feet on the same line and over
the same spot), so two videos framed differently still give the same woman in the same place. Each sheet has a cell of
its own that holds the whole move (`box`: where it sits on the 1024 x 559 fight canvas, as shares; 1 cell px = 1.5
canvas px, as every cultivator sheet), and ends on the spot it started from (`home`).

    python -m scripts.make_heroine_set kick.mp4 guard.mp4 fist.mp4 palm.mp4 finger.mp4 [--cache DIR]

Writes art/portraits/fight/hero_female_{kick,guard,fist,palm,finger}.webp and prints the entries for looks.py: the
key frames (`jab`, `windup`, `release`, `back`; the Guard's `first`), and `hand`: where the fist, palm, fingertip or
foot is at the release, as shares of the fighter's box (the effects fly from there).
Needs ffmpeg, numpy, Pillow, scipy and rembg.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

from scripts.make_heroine_attacks import (CANVAS, CELL_SCALE, COLS, OUT, body_x, cut_one, feet, home, solid,
                                          stance_first, video_frames)

ORDER = ("kick", "guard", "fist", "palm", "finger")


def r(a, b, step=3):
    return list(range(a, b + 1, step))


# (`jab` matters only to the fist, whose jab Nine Dragons throws; the others give their windup)
# the video frames taken (0-based, 24 a second; each from frame 0, her stance picture, so the sheet starts exactly in
# her stance), and the frames that matter among them (by video frame)
MOVES = {
    "kick": {"frames": [0, 11, 22, 28, 34] + r(37, 61) + [64, 67, 73, 79, 85, 91, 97, 103] + r(106, 148),
             "windup": 49, "release": 61, "back": 106, "jab": 49},
    # (the video loses her sword for two frames just before the sparks, 51-52: left out)
    "guard": {"frames": [0, 11] + r(22, 49) + [50, 53, 54, 56, 58] + r(61, 82) + [91, 100, 109, 118, 127, 136, 145] + r(148, 175),
              "first": 53, "in_place": True},
    "fist": {"frames": [0, 9, 17, 23, 26, 29, 32, 38, 44, 47, 50, 56, 62, 68, 71, 74, 77, 80, 83, 86, 89, 92, 98, 104, 110, 116,
                        122, 128, 134, 140, 146] + r(149, 188),
             "jab": 32, "windup": 74, "release": 86, "back": 149},
    "palm": {"frames": [0, 13] + r(26, 71) + [77, 83, 89, 95, 101, 107] + r(110, 155),
             "windup": 53, "release": 65, "back": 110, "jab": 53},
    "finger": {"frames": [0, 12, 24] + r(34, 61) + [67, 73, 79, 85, 91, 97, 103, 109, 115, 121] + r(124, 160),
               "windup": 49, "release": 55, "back": 124, "jab": 49},
}
START = 0                                # the video frame that is her stance picture: each video is placed by it


def cut_frames(kind, video, numbers, cache):
    from rembg import new_session
    out, raw, session = {}, None, None
    for n in numbers:
        path = os.path.join(cache, kind, f"{n:03d}.png") if cache else None
        if path and os.path.exists(path):
            out[n] = Image.open(path).convert("RGBA")
            continue
        if raw is None:
            raw = video_frames(video, numbers, (0, 0, 1280, 720))
            session = new_session("isnet-general-use")
        out[n] = cut_one(raw[n], session, False)
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            out[n].save(path)
        print(f"  {kind} {n}", flush=True)
    return out


def reach(m):
    """The point furthest right (the fist, palm, fingertip or foot at the release), in px."""
    ys, xs = np.where(m)
    far = xs >= xs.max() - 5
    return float(xs.max()), float(ys[far].mean())


def fit(ref, im, s0):
    """How to lay her stance picture `im` over her stance `ref` (a mask on the fight canvas): the scale and the move
    (px) where the two outlines overlap most. Her feet alone can't say (one foot shows in one, two in the other)."""
    K = 4                                                                        # searched at a quarter of the size
    small = ref[::K, ::K]
    best = (-1.0, s0, 0, 0)
    for s in np.linspace(s0 * 0.9, s0 * 1.1, 21):
        big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        m = solid(big)[::K, ::K]
        ys, xs = np.where(m)
        m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        ry, rx = np.where(small)
        for oy in range(ry.min() - 6, ry.min() + 7):
            for ox in range(rx.min() - 14, rx.min() + 15):
                if oy < 0 or ox < 0 or oy + m.shape[0] > small.shape[0] or ox + m.shape[1] > small.shape[1]:
                    continue
                win = small[oy:oy + m.shape[0], ox:ox + m.shape[1]]
                iou = (win & m).sum() / ((win | m).sum() + small.sum() - win.sum())
                if iou > best[0]:
                    best = (iou, s, (ox - xs.min()) * K, (oy - ys.min()) * K)
    print(f"  stance picture laid on her stance: scale {best[1]:.3f}, overlap {best[0]:.2f}")
    return best[1:]


def build(kind, video, ref, cache):
    mv = MOVES[kind]
    cut = cut_frames(kind, video, [START] + mv["frames"], cache)
    s, dx, dy = fit(ref, cut[START], feet(ref)[2] / feet(solid(cut[START]))[2])    # her stance picture onto her stance
    seq = [cut[n] for n in mv["frames"]]
    travel = [0.0] * len(seq)
    if mv.get("in_place"):                                                       # her step forward is taken out
        cx = [body_x(im) for im in seq]
        sm = [np.mean(cx[max(0, i - 2):i + 3]) for i in range(len(cx))]
        travel = [v - body_x(cut[START]) for v in sm]
    placed = [(im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS), round(dx - travel[i] * s), round(dy))
              for i, im in enumerate(seq)]
    boxes = [(b[0] + x, b[1] + y, b[2] + x, b[3] + y) for big, x, y in placed for b in [big.getbbox()]]
    X0, Y0 = min(b[0] for b in boxes) - 6, min(b[1] for b in boxes) - 6
    X1, Y1 = max(b[2] for b in boxes) + 6, max(b[3] for b in boxes) + 4
    cw, ch = round((X1 - X0) / CELL_SCALE), round((Y1 - Y0) / CELL_SCALE)
    frames = [big.crop((X0 - x, Y0 - y, X1 - x, Y1 - y)).resize((cw, ch), Image.LANCZOS) for big, x, y in placed]
    at = {k: mv["frames"].index(mv[k]) for k in ("jab", "windup", "release", "back", "first") if k in mv}
    frames = home(frames, at.get("back", len(frames) - 10))
    rows = -(-len(frames) // COLS)
    sheet = Image.new("RGBA", (cw * COLS, ch * rows), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, ((i % COLS) * cw, (i // COLS) * ch))
    name = f"hero_female_{kind}.webp"
    sheet.save(os.path.join(OUT, name), quality=84, method=6)
    entry = {"src": f"/art/portraits/fight/{name}", "frames": len(frames), "cols": COLS, "rows": rows,
             "box": [round(X0 / CANVAS[0], 4), round(Y0 / CANVAS[1], 4), round((X1 - X0) / CANVAS[0], 4),
                     round((Y1 - Y0) / CANVAS[1], 4)]}
    entry.update(at)
    if "release" in at:
        big, x, y = placed[at["release"]]
        hx, hy = reach(solid(big))
        entry["hand"] = [round((hx + x) / CANVAS[0], 3), round((hy + y) / CANVAS[1], 3)]
        entry["shift"] = 0
    print(f"{name}: {len(frames)} frames, {COLS} x {rows}, cell {cw} x {ch}")
    return entry


def main(videos, cache=None):
    ref = solid(stance_first())
    print(json.dumps({k: build(k, videos[k], ref, cache) for k in ORDER}, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = None
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != len(ORDER):
        sys.exit(__doc__)
    main(dict(zip(ORDER, args)), cache)
