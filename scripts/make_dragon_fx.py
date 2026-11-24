"""Build Nine Dragons Ascending Fist's moving effects from SHOAIB's two videos (Gemini / Veo, 1920 x 1080, 24 fps,
golden light on pure black; docs/web.md "Nine Dragons, moving"):

- fly: one golden dragon flying to the right, body undulating. The stretch where the whole dragon is in frame is cut
  into a strip that follows it (art/fx/tech/nine_dragons_fly.webp); fight.js plays it for each dragon loosed by a punch.
- finale: the dragons burst from the ground and coil upward in a column (video frames 0-30), lightning plays round
  them (to 78, thinned), they explode in golden light and a ring of fire spreads (82-124). The whole frame is kept
  (art/fx/tech/nine_dragons_finale.webp); fight.js plays it over the beast, the damage landing on the explosion.

Black becomes clear: each pixel's opacity is its brightness, its colour is kept at full strength, so the light lies
over the scene as light does. Prints the entries for web/technique_fx.py (SHEETS).

    python -m scripts.make_dragon_fx fly.mp4 finale.mp4

Needs ffmpeg, numpy and Pillow.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "fx", "tech")
COLS = 8
FLY = list(range(54, 86, 2))                       # the whole dragon in frame
FLY_CELL = (400, 190)
FINALE = list(range(0, 32, 2)) + list(range(34, 80, 4)) + list(range(82, 126, 2))
BOOM = 84                                          # the video frame of the explosion
FINALE_CELL = (480, 270)


def frames(video, picks, size=None):
    vf = "select='" + "+".join(f"eq(n\\,{k})" for k in picks) + "'" + (f",scale={size[0]}:{size[1]}" if size else "")
    w, h = size or (1920, 1080)
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", vf, "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          capture_output=True, check=True).stdout
    return np.frombuffer(data, np.uint8).reshape(-1, h, w, 3)


def lit(rgb, floor=10):
    """Light on black as a picture with opacity: opacity from brightness, colour at full strength."""
    f = rgb.astype(np.float32)
    a = np.clip((f.max(axis=2) - floor) / (255 - floor), 0, 1) ** 0.8
    colour = np.clip(f / np.maximum(f.max(axis=2, keepdims=True), 1) * 255 * np.clip(a[..., None] * 3, 0, 1) ** 0.3, 0, 255)
    return Image.fromarray(np.dstack([colour, a[..., None] * 255]).astype(np.uint8), "RGBA")


def sheet(cells, name):
    w, h = cells[0].size
    rows = -(-len(cells) // COLS)
    out = Image.new("RGBA", (w * COLS, h * rows), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        out.paste(c, ((i % COLS) * w, (i // COLS) * h))
    out.save(os.path.join(OUT, name), quality=60, alpha_quality=70, method=6)
    return {"src": f"/art/fx/tech/{name}", "frames": len(cells), "cols": COLS, "rows": rows}


def fly(video):
    fs = frames(video, FLY)
    boxes = []
    for f in fs:                                   # the dragon's body: the bright mass
        ys, xs = np.where(f.max(axis=2) > 110)
        boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    w = max(b[2] - b[0] for b in boxes) + 80
    h = round(w * FLY_CELL[1] / FLY_CELL[0])
    n = len(fs)
    cx = np.polyval(np.polyfit(range(n), [(b[0] + b[2]) / 2 for b in boxes], 1), range(n))   # its steady drift
    cy = np.mean([(b[1] + b[3]) / 2 for b in boxes])
    cells = []
    for f, x in zip(fs, cx):
        im = Image.new("RGB", (w, h))
        im.paste(Image.fromarray(f), (round(w / 2 - x), round(h / 2 - cy)))
        cells.append(lit(np.asarray(im.resize(FLY_CELL, Image.LANCZOS)), 24))
    return sheet(cells, "nine_dragons_fly.webp")


def finale(video):
    cells = [lit(f) for f in frames(video, FINALE, FINALE_CELL)]
    return dict(sheet(cells, "nine_dragons_finale.webp"), boom=FINALE.index(BOOM))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(json.dumps({"fly": fly(sys.argv[1]), "finale": finale(sys.argv[2])}))
