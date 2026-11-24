"""Build the Martial Master's spar movements and sounds from SHOAIB's Nov 24 videos (art/spar/master/; web/spar_master.py
reads the sheets.json this writes; docs/technique.md "On the website").

The videos (Gemini, 1280 x 720, 24 fps, 10 s, with sound) are one figure on a plain grey backdrop, bare-handed,
facing right, each starting in his fighting stance:
- stance: he breathes in his stance (the loop);
- strike: he relaxes with his hands at his hips (to 1.1 s: his Strike tell), steps in and drives a palm out (2.1-2.8 s),
  holds it, draws back (4.4-6.2 s);
- guard: he raises both forearms (to 1.1 s: his Guard tell), a blow lands on them in sparks (2.25 s), his robes whip
  and he slides back, steadies and lowers his arms (4.3-6.2 s);
- break: he plants his feet and gathers gold Qi round his arm and feet (1.2-2.7 s: his Break tell), slams a palm in a
  burst of light (2.9 s), holds the low lunge and rises (5.4-7.5 s);
- bow: he stands, presses fist into palm, bows his head and returns to his stance;
- hit: a blow lands on his chest (0.5 s), he is thrown a step back with an arm flung out, catches himself and comes
  back to his stance (by 4 s). The sheet starts just before the blow.

No cut-out model is needed: the backdrop is flat grey, so the man is everything darker than it (filled in), and
light (Qi, sparks: brighter than the backdrop) is kept as light, with its colour taken back out of the grey. Gemini's
sparkle is blanked. The slow parts are thinned and the fast ones kept whole (MOVES `frames`: the video frames taken);
each frame's own time is kept (`at`, ms from the first), so the page plays the move at the video's pace.

Every sheet is a grid of equal cells. `box` says where the cell sits on his stance (as shares of BASE, the box round
his standing figure), so every move stands on the same feet. `hit`: the ms at which the blow lands (his palm
arriving, the blow on his guard, the slam). `tell`: the frame he holds while you choose, when he gives a tell.

Sounds: the videos' own, cut round the moment (art/spar/master/<move>.mp3; `lead`: ms from the clip's start to the hit).

    python -m scripts.make_master_sheets stance=stance.mp4 strike=strike.mp4 guard=guard.mp4 break=break.mp4 bow=bow.mp4 hit=hit.mp4

Needs ffmpeg, numpy, Pillow and scipy.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "spar", "master")
FPS = 24
SCALE = 0.5                               # sheet px per video px: he is ~670 px tall in the videos
MARK = (1105, 560, 1215, 670)             # Gemini's sparkle
BASE = (415, 15, 875, 715)                # the box round his standing figure in the videos (x0, y0, x1, y1)
GLOW_REACH = 190                          # how far past his body light is kept, video px (it fades out over FEATHER)
FEATHER = 70


def every(a, b, step):
    return list(range(a, b + 1, step))


MOVES = {
    "stance": {"frames": every(1, 235, 6), "loop": True},
    "strike": {"frames": [1, 6, 11, 16, 21, 26, 40, 48, 51, 53, 55, 57, 59, 61, 63, 65, 67, 70, 74, 80, 90,
                          106, 110, 114, 118, 122, 126, 130, 134, 138, 142, 148, 156],
               "hit": 66, "tell": 40, "sound": (2.50, 3.25, 2.75)},
    "guard": {"frames": [1, 5, 9, 13, 17, 21, 25, 40, 53, 54, 55, 56, 57, 58, 59, 61, 63, 65, 67, 70, 73, 76, 80, 84,
                         88, 92, 96, 100, 106, 112, 118, 124, 130, 136, 142, 150],
              "hit": 54, "tell": 40, "sound": (2.15, 4.90, 2.27)},
    "break": {"frames": every(1, 25, 4) + every(30, 62, 4) + every(65, 74, 1) + [76, 78, 80, 83, 86, 90, 95, 100, 106,
                         112, 118] + every(129, 165, 4) + [170, 176, 182],
              "hit": 69, "tell": 46, "sound": (1.25, 5.60, 2.90)},
    "hit": {"frames": [9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 26, 28, 31, 35, 39, 43, 47, 51, 55, 59,
                       63, 67, 71, 75, 79, 83, 87, 91, 95],
            "hit": 12, "sound": (0.35, 2.05, 0.55)},
    "bow": {"frames": every(1, 69, 4) + [75, 90] + every(105, 145, 4) + [152] + every(159, 215, 4) + [225]},
}


def frames_of(video, folder):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, os.path.join(folder, "%03d.png")], check=True)


def backdrop(im):
    edge = [im[:30, :300], im[-30:, :300], im[:30, -300:]]
    return np.median(np.concatenate([e.reshape(-1, 3) for e in edge]), axis=0)


def cut(im):
    """(RGBA float 0-255 with straight alpha, the man's own mask): the man solid, light kept as light."""
    im = im.copy()
    bg = backdrop(im)
    x0, y0, x1, y1 = MARK
    im[y0:y1, x0:x1] = bg
    dark = ndi.binary_closing((bg - im).max(axis=2) > 14, iterations=2)
    body = ndi.binary_fill_holes(dark)
    lab, n = ndi.label(body)
    if n > 1:                                                   # only the biggest piece is him
        body = ndi.binary_fill_holes(lab == 1 + int(np.argmax(ndi.sum(body, lab, range(1, n + 1)))))
    d = np.abs(im - bg).max(axis=2)
    soft = np.clip((d - 9) / 22, 0, 1) * ndi.binary_dilation(body, iterations=2)
    a_body = np.maximum(body.astype(np.float32), soft)
    a_glow = np.clip(((im - bg).clip(0).max(axis=2) - 6) / 70, 0, 1)
    reach = ndi.distance_transform_edt(~body)                   # light fades out away from him
    a_glow *= np.clip((GLOW_REACH - reach) / FEATHER, 0, 1)
    a = np.maximum(a_body, a_glow)
    col = im.copy()
    light = (a_body < 0.5) & (a > 0.02)
    aa = np.clip(a, 0.05, 1)[..., None]
    col[light] = np.clip((im - bg * (1 - aa)) / aa, 0, 255)[light]
    return np.dstack([col, a * 255]), body


def build(name, video, spec):
    with tempfile.TemporaryDirectory() as tmp:
        frames_of(video, tmp)
        cuts = []
        for n in spec["frames"]:
            im = np.asarray(Image.open(os.path.join(tmp, f"{n:03d}.png")).convert("RGB")).astype(np.float32)
            cuts.append(cut(im)[0])
    if name == "stance":                                        # his standing picture: the yard's page, and the fallback
        bx0, by0, bx1, by1 = BASE
        Image.fromarray(cuts[0][by0:by1, bx0:bx1].astype(np.uint8), "RGBA").save(os.path.join(OUT, "still.webp"), quality=90)
    seen = np.max([c[..., 3] for c in cuts], axis=0) > 8
    ys, xs = np.where(seen)
    x0, y0 = max(0, xs.min() - 6), max(0, ys.min() - 6)
    x1, y1 = min(1280, xs.max() + 7), min(720, ys.max() + 7)
    cw, ch = round((x1 - x0) * SCALE), round((y1 - y0) * SCALE)
    count = len(cuts)
    cols = min(count, max(1, int(np.ceil(np.sqrt(count * ch / cw)))))
    rows = int(np.ceil(count / cols))
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    for i, c in enumerate(cuts):
        cell = Image.fromarray(c[y0:y1, x0:x1].astype(np.uint8), "RGBA").resize((cw, ch), Image.LANCZOS)
        sheet.paste(cell, ((i % cols) * cw, (i // cols) * ch))
    sheet.save(os.path.join(OUT, f"{name}.webp"), quality=86, method=6)
    bx, by, bw, bh = BASE[0], BASE[1], BASE[2] - BASE[0], BASE[3] - BASE[1]
    first = spec["frames"][0]
    out = {"src": f"/art/spar/master/{name}.webp", "frames": count, "cols": cols, "rows": rows,
           "box": [round((x0 - bx) / bw, 4), round((y0 - by) / bh, 4), round((x1 - x0) / bw, 4), round((y1 - y0) / bh, 4)],
           "at": [round((n - first) * 1000 / FPS) for n in spec["frames"]]}
    if spec.get("loop"):
        out["loop"] = round((spec["frames"][-1] - first + 6) * 1000 / FPS)
    if "hit" in spec:
        out["hit"] = round((spec["hit"] - first) * 1000 / FPS)
    if "tell" in spec:
        out["tell"] = spec["frames"].index(spec["tell"])
    if "sound" in spec:
        a, b, hit = spec["sound"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", video, "-vn", "-ac", "1",
                        "-af", f"afade=t=in:d=0.03,afade=t=out:st={b - a - 0.25}:d=0.25", "-b:a", "96k",
                        os.path.join(OUT, f"{name}.mp3")], check=True)
        out["sound"] = {"src": f"/art/spar/master/{name}.mp3", "lead": round((hit - a) * 1000)}
    print(name, f"{count} frames, cell {cw}x{ch}, sheet {sheet.size}")
    return out


def main(args):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "sheets.json")
    data = json.load(open(path)) if os.path.exists(path) else {"sheets": {}}
    data["aspect"] = round((BASE[2] - BASE[0]) / (BASE[3] - BASE[1]), 4)
    for arg in args:
        name, video = arg.split("=", 1)
        data["sheets"][name] = build(name, video, MOVES[name])
    with open(path, "w") as fh:
        json.dump(data, fh, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
