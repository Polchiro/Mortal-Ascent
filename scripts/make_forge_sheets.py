"""SHOAIB's blacksmith videos (Gemini, 1280 x 720, 24 fps, on green) into frame sheets the forge page plays on
demand (art/forge/<look>_<clip>.webp + sheets.json; static/forge_live.js, docs/web.md "Live forge").

Sheets, not videos: the page steps the frames itself, so the bellows move only while you pump and the hammer falls
only when you strike, and the green is gone everywhere (a video with transparency doesn't play in every browser).

- keyed: how much greener than red and blue a pixel is; where it is partly see-through (hair, sparks, smoke) the green
  is taken back out of its colour (the background's green, measured on the frame), so sparks stay orange, not green;
- cut to CLIPS[clip]["crop"] (Gemini's sparkle at about 1150, 600 falls outside), made SCALE smaller;
- stepped at FPS from start to end.
The props in the videos (anvil, bucket, bowl) stay in the frames: the page lays SHOAIB's own prop pictures over
them (art/forge/anvil.webp ...), lined up by "props" below.

    python -m scripts.make_forge_sheets male DIR [CLIP ...]   (DIR holds male_blacksmith_<video>.mp4; CLIPs: only those)
Needs ffmpeg, numpy and Pillow.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "forge")
FPS, SCALE, COLS = 12, 0.5, 6
KEY_SOLID, KEY_CLEAR = 30, 90
# clip: the video's name, seconds from/to, crop (x, y, w, h) in the video, and where SHOAIB's prop picture covers
# the video's own prop (x, y, scale of the picture's width) in the same crop's pixels
CLIPS = {
    "hammer": {"video": "hard_strike", "from": 0.8, "to": 3.6, "crop": (300, 0, 700, 720),
               "props": {"anvil": (220, 452, 0.43)}, "impact": 1.6},
    "bellows": {"video": "bellows_loop", "from": 2.833, "to": 4.5, "crop": (300, 0, 830, 720), "props": {}},
    # the quenches: holding the glowing blade over the bucket / bowl, then the plunge and its steam / fire
    "water": {"video": "quench_in_water", "from": 1.0, "to": 8.5, "crop": (160, 0, 950, 720), "fps": 10, "scale": 0.4,
              "props": {"trough": (362, 466, 0.64)}, "impact": 3.0},
    "oil": {"video": "quench_in_oil", "from": 1.0, "to": 8.5, "crop": (160, 0, 950, 720), "fps": 10, "scale": 0.4,
            "props": {"cauldron_oil": (467, 478, 0.43)}, "impact": 2.3},
}


def frames(video, start, end, crop, fps=FPS):
    x, y, w, h = crop
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-to", str(end), "-i", video, "-vf",
                          f"fps={fps},crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32)


def key(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    excess = g - np.maximum(r, b)
    alpha = np.clip((KEY_CLEAR - excess) / (KEY_CLEAR - KEY_SOLID), 0, 1)
    green = a[excess > KEY_CLEAR + 30]
    bg = np.median(green, axis=0) if len(green) else np.array([45, 180, 60], np.float32)
    al = alpha[..., None]
    fg = np.where(al > 0.02, (a - (1 - al) * bg) / np.maximum(al, 0.02), 0)     # take the green back out
    fg[..., 1] = np.minimum(fg[..., 1], (fg[..., 0] + fg[..., 2]) / 2 + 8)    # average despill: no green fringe
    return np.dstack([fg.clip(0, 255), alpha * 255]).astype(np.uint8)


def main(look, src, only=None):
    meta_path = os.path.join(OUT, "sheets.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    for name, c in CLIPS.items():
        if only and name not in only:
            continue
        fps, scale = c.get("fps", FPS), c.get("scale", SCALE)
        fr = frames(os.path.join(src, f"{look}_blacksmith_{c['video']}.mp4"), c["from"], c["to"], c["crop"], fps)
        w, h = round(c["crop"][2] * scale), round(c["crop"][3] * scale)
        rows = -(-len(fr) // COLS)
        sheet = Image.new("RGBA", (w * COLS, h * rows))
        for i, f in enumerate(fr):
            sheet.paste(Image.fromarray(key(f), "RGBA").resize((w, h), Image.LANCZOS), ((i % COLS) * w, (i // COLS) * h))
        sheet.save(os.path.join(OUT, f"{look}_{name}.webp"), quality=82, method=6)
        meta.setdefault(look, {})[name] = {
            "src": f"/art/forge/{look}_{name}.webp", "frames": len(fr), "cols": COLS, "rows": rows, "w": w, "h": h,
            "fps": fps, "crop": c["crop"], "props": c["props"],
            "impact": round((c["impact"] - c["from"]) * fps) if "impact" in c else None}
        print(look, name, len(fr), "frames", f"{os.path.getsize(os.path.join(OUT, f'{look}_{name}.webp')) // 1024} KB")
    json.dump(meta, open(meta_path, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:] or None)
