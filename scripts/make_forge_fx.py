"""SHOAIB's forge effect videos (Gemini, 1280 x 720, 24 fps, 10 s) into what the live forge plays when the smith is
hidden (static/forge_live.js, docs/web.md "Live forge"):

- art/forge/fire.mp4: the furnace fire (on black, laid on with `screen` over the furnace's coals), a seamless loop
  (its last LOOP seconds fade into its first); it grows and roars with the heat as you pump;
- art/forge/steam.mp4, art/forge/oil_flare.mp4: the quench's steam burst over the trough and the fire over the oil
  bath (on black, `screen`), played once at the plunge;
- art/forge/tool_hammer.webp (+ sheets.json "tool" / "hammer"): the hammer alone, swinging down onto the anvil (on
  green, keyed like scripts/make_forge_sheets.py). Its frame 0 is the hammer raised, then the swing, the blow and its
  sparks, and the hammer lifting back. The video's own anvil and glowing bar are cut away (below BAR_TOP only what
  moves stays: the sparks and the flash), so SHOAIB's anvil and the piece on it show through.

The crops leave out Gemini's sparkle (about 1160, 600).

    python -m scripts.make_forge_fx DIR      (DIR holds the four videos, named as SHOAIB sent them)
Needs ffmpeg, numpy and Pillow.
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

from scripts.make_forge_sheets import COLS, OUT, frames, key

LOOP = 1.5
BLACK = "curves=all='0/0 0.07/0 1/1'"              # the clips' black is not quite black: make it so, for `screen`
# name: (video, from, to, crop x:y:w:h, size w:h)
FX = {
    "fire": ("Furnace_fire", 0, 10, "960:720:160:0", "640:480"),
    "steam": ("Quench_steam_burst", 0, 5, "1000:720:100:0", "560:404"),
    "oil_flare": ("Oil_flare", 0.3, 5.3, "800:720:240:0", "480:432"),
}
# the hammer: the raised pose, then from the start of the swing to the hammer back up (seconds in the video)
REST, SWING_FROM, SWING_TO, IMPACT = 3.0, 4.583, 7.5, 4.917
TOOL_CROP, TOOL_SCALE, TOOL_FPS = (0, 0, 1280, 620), 0.4, 12
BAR_TOP = 488                                       # the video's anvil and bar start here; below it only what moves stays
HIT = (660, 495)                                    # where the hammer's face meets the bar


def find(src, name):
    hits = glob.glob(os.path.join(src, f"*{name}*.mp4"))
    if not hits:
        sys.exit(f"no {name} video in {src}")
    return hits[0]


def run(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def clip(src, name):
    video, a, b, crop, size = FX[name]
    out = os.path.join(OUT, f"{name}.mp4")
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    base = f"crop={crop},scale={size},{BLACK},fps=24"
    if name == "fire":
        T = b - a
        graph = (f"[0:v]{base},split=3[x][y][z];[x]trim=0:{LOOP},setpts=PTS-STARTPTS[head];"
                 f"[y]trim={T - LOOP}:{T},setpts=PTS-STARTPTS[tail];[z]trim={LOOP}:{T - LOOP},setpts=PTS-STARTPTS[mid];"
                 f"[tail][head]xfade=transition=fade:duration={LOOP}:offset=0[xf];[xf][mid]concat=n=2:v=1:a=0[out]")
        run("-i", find(src, video), "-filter_complex", graph, "-map", "[out]", *enc, out)
    else:
        run("-ss", str(a), "-t", str(b - a), "-i", find(src, video), "-vf", f"{base},fade=t=out:st={b - a - 1}:d=1", *enc, out)
    print(name, f"{os.path.getsize(out) // 1024} KB")


def tool(src):
    video = find(src, "Hammer_strike")
    x, y, w, h = TOOL_CROP
    rest = frames(video, REST, REST + 0.05, TOOL_CROP, TOOL_FPS)[:1]
    swing = frames(video, SWING_FROM, SWING_TO, TOOL_CROP, TOOL_FPS)
    fr = np.concatenate([rest, swing])
    still = rest[0]                                 # nothing moves on the anvil before the blow
    cut = BAR_TOP - y
    fw, fh = round(w * TOOL_SCALE), round(h * TOOL_SCALE)
    rows = -(-len(fr) // COLS)
    sheet = Image.new("RGBA", (fw * COLS, fh * rows))
    for i, f in enumerate(fr):
        k = key(f)
        moved = np.abs(f[cut:] - still[cut:]).max(axis=2)
        k[cut:, :, 3] = (k[cut:, :, 3] * np.clip((moved - 40) / 60, 0, 1)).astype(np.uint8)
        sheet.paste(Image.fromarray(k, "RGBA").resize((fw, fh), Image.LANCZOS), ((i % COLS) * fw, (i // COLS) * fh))
    sheet.save(os.path.join(OUT, "tool_hammer.webp"), quality=82, method=6)
    meta_path = os.path.join(OUT, "sheets.json")
    meta = json.load(open(meta_path))
    meta.setdefault("tool", {})["hammer"] = {
        "src": "/art/forge/tool_hammer.webp", "frames": len(fr), "cols": COLS, "rows": rows, "w": fw, "h": fh,
        "fps": TOOL_FPS, "crop": TOOL_CROP, "hit": [HIT[0] - x, HIT[1] - y], "props": {},
        "impact": 1 + round((IMPACT - SWING_FROM) * TOOL_FPS)}
    json.dump(meta, open(meta_path, "w"), indent=1)
    print("tool hammer", len(fr), "frames", f"{os.path.getsize(os.path.join(OUT, 'tool_hammer.webp')) // 1024} KB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    for n in FX:
        clip(sys.argv[1], n)
    tool(sys.argv[1])
