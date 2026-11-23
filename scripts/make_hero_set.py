"""Build the new male cultivator's fight pictures from SHOAIB's Nov 24 videos of him: his fighting stance, Strike,
Break, Guard, and the fist, kick, palm and finger movements (looks.IDLE_SHEETS, ATTACK_SHEETS, GUARD_SHEETS,
MOTION_SHEETS[...]["male"]; docs/web.md "His movements"). Made exactly as hers are (scripts/make_heroine_set.py,
whose tools this uses): every video starts and ends in his stance, so he goes stance, move, stance without a jump.

The videos (Gemini, 1280 x 720, 24 fps, 10 s) are one figure on a plain grey backdrop, in white robes, sword held
low in his right hand:
- stance: he stands on guard, breathing, sleeves and hair stirring (a loop is found in it);
- strike: he raises the sword (1.3-2.0 s), cuts in one sweep with a ring of blue Qi (2.25 s, the hit), holds while it
  fades (to 4.5 s), draws the sword back and stands (by 6 s);
- break: Qi coils round him (1.2-3.5 s), he leaps with the sword overhead (3.6-4.3 s) and drives it into the ground
  (4.75 s, the hit), a dome of blue light bursts (to 6 s), he rises from one knee (by 7.7 s);
- guard: he raises the blade upright before him (1.0-2.0 s), the blow lands on it (2.1 s), his robes whip back, he
  steadies (to 4 s) and lowers it (by 6 s);
- fist: a quick jab with his left fist (1.4 s), drawn back, a deep lunging punch (3.6 s), held, back by 7.5 s;
- kick: he gathers, snaps a front kick out (2.4 s), holds it (to 4 s), draws the leg back (by 5.5 s);
- palm: a step, then an open-palm push from a low stance (2.3 s), held (to 4.8 s), back by 6 s;
- finger: a step, then a deep lunge with two fingers thrust out (2.5 s), held (to 5.3 s), back by 6.3 s.
The slow parts are thinned and the fast ones kept whole (MOVES `frames`). Every frame is cut out (rembg); the painted
Qi, Gemini's mark and loose sparks are dropped (the fight draws its own trails and bursts), and the Break's burst
frames are left out as hers are. His leap across the Break video is taken out (`in_place`): the fight's dash carries him.

The stance is placed on the fight canvas where a cultivator stands (FEET, TALL), in the shared 320 x 360 cell; every
other video is laid on that stance by its own first frame.

    python -m scripts.make_hero_set stance=stance.mp4 strike=strike.mp4 break=break.mp4 guard=block.mp4 \\
        fist=punch.mp4 kick=kick.mp4 palm=palm.mp4 finger=finger.mp4 [--cache DIR]

(any of them, each as name=video; the stance must exist before the others). Writes art/portraits/fight/hero_male_*.webp
(and the still poses hero_male_idle / windup / strike.webp) and prints the entries for looks.py.
Needs ffmpeg, numpy, Pillow, scipy and rembg.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

from scripts.make_heroine_attacks import CANVAS, COLS, OUT, STANCE_AT, feet, solid, video_frames
from scripts.make_heroine_set import build, cut_frames, r

ORDER = ("strike", "break", "guard", "fist", "kick", "palm", "finger")
FEET, TALL = (472, 523), 440             # where his feet stand on the 1024 x 559 canvas, and how tall he is (px)
ROWS = 9                                 # the stance: COLS x ROWS frames fill the grid, stepped through in CSS
LOOP = (72, 150)                         # the stance loop: 3 s to 6.25 s of video

MOVES = {
    "strike": {"frames": [0, 24, 30, 33, 36, 39, 42, 45, 48, 50, 52, 54, 56, 58, 60, 63, 66, 72, 78, 84, 90, 96, 102, 108]
               + r(111, 150), "hit": 54, "back": 111},
    "break": {"frames": [0, 24] + r(28, 84, 4) + r(86, 112, 2) + [114, 150] + r(153, 192),
              "hit": 114, "back": 153, "in_place": True},
    "guard": {"frames": [0, 12] + r(22, 46) + [48, 50, 52, 54, 56, 58] + r(61, 82) + [88, 94, 100, 106] + r(108, 144),
              "first": 50},
    "fist": {"frames": [0, 12, 22, 26, 28, 30, 33, 36, 40, 44, 48, 54, 62, 70, 74, 77, 80, 83, 86, 89, 92, 98, 104, 110, 116,
                        122, 128, 134, 140, 146] + r(149, 188),
             "jab": 36, "windup": 77, "release": 89, "back": 149},
    "kick": {"frames": [0, 14, 28, 34, 38] + r(41, 62) + [65, 70, 76, 82, 88, 94] + r(97, 150),
             "windup": 50, "release": 59, "back": 97, "jab": 50},
    "palm": {"frames": [0, 14, 26] + r(30, 63) + [69, 75, 81, 87, 93, 99, 105] + r(108, 150),
             "windup": 48, "release": 60, "back": 108, "jab": 48},
    "finger": {"frames": [0, 14, 26] + r(32, 65) + [71, 77, 83, 89, 95, 101, 107, 113, 119, 125] + r(128, 158),
               "windup": 50, "release": 62, "back": 128, "jab": 50},
}


def on_canvas(cell):
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(cell.resize((480, 540), Image.LANCZOS), STANCE_AT)
    return canvas


def stance_first():
    """His stance's first frame on the fight canvas."""
    return on_canvas(Image.open(os.path.join(OUT, "hero_male_stance.webp")).convert("RGBA").crop((0, 0, 320, 360)))


def loop(video):
    """(first frame, frames) of the stretch of the stance video whose end best meets its start."""
    import subprocess
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                          capture_output=True, check=True).stdout
    small = np.frombuffer(data, np.uint8).reshape(-1, 90, 160).astype(float)
    best = None
    for a in range(12, len(small) - LOOP[0]):
        for n in range(LOOP[0], min(LOOP[1], len(small) - a)):
            d = np.abs(small[a] - small[a + n]).mean()
            if best is None or d < best[0]:
                best = (d, a, n)
    return best[1], best[2]


def stance(video, cache):
    a, n = loop(video)
    count = COLS * ROWS
    picks = [a + round(j * n / count) for j in range(count)]
    cut = cut_frames("stance", video, picks, cache)
    fx, gy, h = feet(solid(cut[picks[0]]))
    s = TALL / h
    sheet = Image.new("RGBA", (320 * COLS, 360 * ROWS), (0, 0, 0, 0))
    first = None
    for i, k in enumerate(picks):
        big = cut[k].resize((round(1280 * s), round(720 * s)), Image.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        x, y = round(FEET[0] - fx * s), round(FEET[1] - gy * s)
        canvas.alpha_composite(big.crop((max(0, -x), max(0, -y), big.width, big.height)), (max(0, x), max(0, y)))
        cell = canvas.crop((STANCE_AT[0], STANCE_AT[1], STANCE_AT[0] + 480, STANCE_AT[1] + 540)).resize((320, 360), Image.LANCZOS)
        sheet.alpha_composite(cell, ((i % COLS) * 320, (i // COLS) * 360))
        first = first or canvas
    sheet.save(os.path.join(OUT, "hero_male_stance.webp"), quality=84, method=6)
    first.save(os.path.join(OUT, "hero_male_idle.webp"), quality=90, method=6)       # the still he stands in
    print(f"hero_male_stance.webp: {count} frames, video frames {a}-{a + n}, loop {n / 24:.2f} s, scale {s:.3f}")
    return {"src": "/art/portraits/fight/hero_male_stance.webp", "frames": count, "cols": COLS, "rows": ROWS,
            "loop": round(n / 24, 2), "shift": 0}


def still(entry, frame, name):
    """One frame of a sheet as a still pose on the canvas (the page's three poses: idle, windup, strike)."""
    sheet = Image.open(os.path.join(OUT, os.path.basename(entry["src"]))).convert("RGBA")
    cw, ch = sheet.width // entry["cols"], sheet.height // entry["rows"]
    cell = sheet.crop(((frame % COLS) * cw, (frame // COLS) * ch, (frame % COLS + 1) * cw, (frame // COLS + 1) * ch))
    b = entry["box"]
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(cell.resize((round(b[2] * CANVAS[0]), round(b[3] * CANVAS[1])), Image.LANCZOS),
                           (round(b[0] * CANVAS[0]), round(b[1] * CANVAS[1])))
    canvas.save(os.path.join(OUT, name), quality=90, method=6)


def main(videos, cache=None):
    out = {}
    if "stance" in videos:
        out["stance"] = stance(videos["stance"], cache)
    ref = solid(stance_first())
    for k in ORDER:
        if k in videos:
            out[k] = build(k, videos[k], ref, cache, MOVES, "hero_male")
    if "strike" in out:
        e, f = out["strike"], MOVES["strike"]["frames"]
        still(e, f.index(48), "hero_male_windup.webp")
        still(e, f.index(56), "hero_male_strike.webp")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    cache = None
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    videos = dict(a.split("=", 1) for a in args if "=" in a)
    if not videos or len(videos) != len(args) or set(videos) - set(ORDER) - {"stance"}:
        sys.exit(__doc__)
    main(videos, cache)
