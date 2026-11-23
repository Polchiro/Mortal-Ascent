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

- art/forge/reveal_burst.mp4: the golden burst behind a forged piece's reveal (on black, `screen`; its flash at
  REVEAL_FLASH s, when the piece appears; the page tints it to the rarity), static/forge_reveal.js;
- art/forge/crack.mp4: a glowing bar cracking apart in sparks and smoke, for a failed forge (on black, `screen`);
- art/forge/embers.mp4: embers drifting up through the whole workshop (on black, `screen`), a seamless loop;
- art/forge/splash.mp4: water bursting up from the trough at a water quench (with the steam; on black, `screen`);
- art/forge/aura.mp4: a ring of golden spirit energy turning behind a Legendary or Mythical piece (a loop, tinted);
- art/forge/rune_circle.mp4 / rune_flash.mp4: a golden magic circle turning behind the piece while you carve (a loop,
  before its flare), and its flare, played when a clean rune resonates;
- art/forge/chisel.mp4: a burst of golden sparks where each good stroke is carved (from after the chisel leaves the
  frame);
- art/forge/tool_bellows.webp (+ sheets.json "tool" / "bellows"): the bellows alone, one pump from open to squeezed and
  open again (keyed from green; the stand and Gemini's mark in its corner cut away). The page steps it only while you
  pump.

    python -m scripts.make_forge_fx DIR [NAME ...]   (DIR holds the videos, named as SHOAIB sent them; NAMEs: only those,
                                                     of fire steam oil_flare reveal_burst crack embers splash aura rune_circle
                                                     rune_flash chisel tool bellows)
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
    "reveal_burst": ("Reveal_burst", 0, 6, "720:720:280:0", "540:540"),
    "crack": ("Failure_crack", 1.2, 7.2, "960:540:160:160", "640:360"),
    "embers": ("Drifting_embers", 0, 10, "1120:720:0:0", "700:450"),
    "splash": ("Water_splash", 0.15, 3.65, "960:720:160:0", "480:360"),
    "aura": ("Spirit_aura", 0, 10, "720:720:280:0", "480:480"),
    "rune_circle": ("Rune_circle", 0, 4.6, "720:720:280:0", "540:540"),
    "rune_flash": ("Rune_circle", 4.65, 7.15, "720:720:280:0", "540:540"),
    "chisel": ("Chisel_spark", 1.3, 3.1, "600:600:340:60", "300:300"),
}
LOOPS = ("fire", "embers", "aura", "rune_circle")
REVEAL_FLASH, CRACK_AT = 1.0, 0.97                  # seconds into reveal_burst.mp4 / crack.mp4
# the bellows: one pump (open at BELLOWS_FROM, squeezed halfway, open again at BELLOWS_TO), its crop in the video, and
# the corner where a stand and Gemini's mark sit (cut away); NOZZLE: the nozzle's tip in the crop's pixels
BELLOWS_FROM, BELLOWS_TO, BELLOWS_CROP, BELLOWS_SCALE = 1.0, 2.0, (0, 110, 1280, 530), 0.45
BELLOWS_CUT, BELLOWS_NOZZLE = (1080, 430), (1125, 360)
BELLOWS_KEY = (14, 58)                              # its green is paler (about 83 greener than red and blue, not 120+)
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
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "31" if name == "embers" else "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    base = f"crop={crop},scale={size},{BLACK},fps=24"
    if name in LOOPS:
        T = b - a
        graph = (f"[0:v]{base},split=3[x][y][z];[x]trim=0:{LOOP},setpts=PTS-STARTPTS[head];"
                 f"[y]trim={T - LOOP}:{T},setpts=PTS-STARTPTS[tail];[z]trim={LOOP}:{T - LOOP},setpts=PTS-STARTPTS[mid];"
                 f"[tail][head]xfade=transition=fade:duration={LOOP}:offset=0[xf];[xf][mid]concat=n=2:v=1:a=0[out]")
        run("-i", find(src, video), "-filter_complex", graph, "-map", "[out]", *enc, out)
    else:
        fade = "" if name == "crack" else f",fade=t=out:st={b - a - 1}:d=1"     # the crack ends on the broken bar
        run("-ss", str(a), "-t", str(b - a), "-i", find(src, video), "-vf", base + fade, *enc, out)
        if name == "crack":                         # its last frame, for a page that has already seen it
            run("-sseof", "-0.1", "-i", out, "-frames:v", "1", "-q:v", "4", os.path.join(OUT, "crack_end.jpg"))
    print(name, f"{os.path.getsize(out) // 1024} KB")


def bellows(src):
    video = find(src, "bellows_pumping")
    fr = frames(video, BELLOWS_FROM, BELLOWS_TO, BELLOWS_CROP, 24)
    fw, fh = round(BELLOWS_CROP[2] * BELLOWS_SCALE), round(BELLOWS_CROP[3] * BELLOWS_SCALE)
    rows = -(-len(fr) // COLS)
    sheet = Image.new("RGBA", (fw * COLS, fh * rows))
    cx, cy = BELLOWS_CUT
    for i, f in enumerate(fr):
        k = key(f, *BELLOWS_KEY)
        k[cy:, cx:, 3] = 0                          # the stand and the mark
        sheet.paste(Image.fromarray(k, "RGBA").resize((fw, fh), Image.LANCZOS), ((i % COLS) * fw, (i // COLS) * fh))
    sheet.save(os.path.join(OUT, "tool_bellows.webp"), quality=82, method=6)
    meta_path = os.path.join(OUT, "sheets.json")
    meta = json.load(open(meta_path))
    meta.setdefault("tool", {})["bellows"] = {
        "src": "/art/forge/tool_bellows.webp", "frames": len(fr), "cols": COLS, "rows": rows, "w": fw, "h": fh, "fps": 24,
        "crop": BELLOWS_CROP, "nozzle": list(BELLOWS_NOZZLE), "props": {}, "impact": None}
    json.dump(meta, open(meta_path, "w"), indent=1)
    print("tool bellows", len(fr), "frames", f"{os.path.getsize(os.path.join(OUT, 'tool_bellows.webp')) // 1024} KB")


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
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    only = set(sys.argv[2:])
    for n in FX:
        if not only or n in only:
            clip(sys.argv[1], n)
    if not only or "tool" in only:
        tool(sys.argv[1])
    if not only or "bellows" in only:
        bellows(sys.argv[1])
