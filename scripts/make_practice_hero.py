"""
Your character's unarmed movements in Practice (docs/technique.md "Practice on the website"), cut from SHOAIB's Flow
videos (Veo 3.1 Fast, 1920x1080 or 1280x720, a plain grey backdrop, the character side-on facing right):

  python -m scripts.make_practice_hero female stance=<video> strike=<video> block=<video> struck=<video>

writes art/practice/hero/<gender>/<move>.webp (a sprite sheet), <move>.mp3 (its sound, raised to full level) and
sheets.json. Each move keeps only the part of its video the drill needs (MOVES): the videos are 8 s long and the
character stands still around the move.

The character is cut by colour, not by brightness: the robes are light blue, lighter than the grey in places, so
anything that isn't the flat grey (lighter, darker or bluer) is the character; the biggest piece is kept, and Gemini's
sparkle in the corner is painted over first. Each sheet's frames share one box (the union of the character over the
move); `box` gives it in units of her standing figure in the stance video's first frame (`base`), so the page can lay
every move over the same spot.
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
W, H = 1280, 720                       # the videos are worked at this size
MARK = (1150, 590, 1240, 680)          # the sparkle, at 1280x720
SCALE = 0.42                           # sheet px per video px: she is ~600 px tall in the videos
PAD = 6
LOUD = -1.0

# what each move keeps: (from s, to s, fps), the sound (from s, to s), and its key frames (as seconds into the video)
MOVES = {
    # standing between blows: the whole video, looping (it ends as it begins); no sound (a loop of breath tires)
    "stance": {"cut": (0.0, 7.67, 12), "loop": True},
    # the punch: from the stance to the fist at full reach (the rest turns to the camera); the page plays it back
    # in reverse to return. `set` is where the step begins, `out` the fist fully out
    "strike": {"cut": (0.0, 1.25, 24), "sound": (1.22, 1.95), "keys": {"set": 0.5, "out": "reach"}},
    # the block: the arms come up and cross (`up`), the blow is absorbed until `end`; the page reverses to return
    "block": {"cut": (0.5, 3.6, 24), "sound": (2.5, 3.25), "keys": {"set": 0.8, "up": 2.05}},
    # struck: the blow lands (`hit`), the stagger, the recovery; the page fades back to the stance after it
    "struck": {"cut": (1.0, 4.6, 24), "sound": (2.05, 2.95), "keys": {"hit": 1.85}},
}


def frames_of(video, a, b, fps, folder):
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", video,
                    "-vf", f"scale={W}:{H}", "-r", str(fps), os.path.join(folder, "%04d.png")], check=True)
    return sorted(os.path.join(folder, f) for f in os.listdir(folder))


def backdrop(im):
    edge = [im[:30, :300], im[-30:, :300], im[:30, -300:]]
    return np.median(np.concatenate([e.reshape(-1, 3) for e in edge]), axis=0)


def cut(im):
    """RGBA (0-255 floats) of the character off the flat grey backdrop."""
    im = im.copy()
    bg = backdrop(im)
    x0, y0, x1, y1 = MARK
    im[y0:y1, x0:x1] = bg
    d = np.abs(im - bg).max(axis=2)
    tint = (im[..., 2] - im[..., 0]) - (bg[2] - bg[0])          # the robes are blue; the backdrop is neutral
    score = np.maximum(d, tint * 1.4)
    body = ndi.binary_fill_holes(ndi.binary_closing(score > 13, iterations=3))
    lab, n = ndi.label(body)
    if n > 1:                                                   # her, and any loose strand of hair or sleeve
        sizes = ndi.sum(body, lab, range(1, n + 1))
        body = np.isin(lab, 1 + np.nonzero(sizes >= sizes.max() * 0.04)[0])
    gaps, n = ndi.label(ndi.binary_opening(body & (score < 6), iterations=2))   # backdrop seen through her
    for i in range(1, n + 1):
        if (gaps == i).sum() > 300:
            body &= ~ndi.binary_dilation(gaps == i, iterations=1)
    soft = np.clip((score - 5) / 16, 0, 1) * ndi.binary_dilation(body, iterations=2)
    a = ndi.gaussian_filter(np.maximum(ndi.binary_erosion(body, iterations=1).astype(np.float32), soft), 0.6)
    aa = np.clip(a, 0.08, 1)[..., None]
    col = np.where(a[..., None] < 0.95, np.clip((im - bg * (1 - aa)) / aa, 0, 255), im)
    return np.dstack([col, a * 255])


def bbox(alpha, thr=128):
    ys, xs = np.nonzero(alpha > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def sound(video, a, b, out):
    """The move's sound, raised so its loudest moment is at LOUD dB."""
    probe = subprocess.run(["ffmpeg", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", video, "-af", "volumedetect",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    peak = float(probe.split("max_volume:")[1].split("dB")[0])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", video, "-vn",
                    "-af", f"volume={LOUD - peak}dB,afade=t=in:d=0.02,afade=t=out:st={b - a - 0.12}:d=0.12",
                    "-ac", "1", "-ar", "44100", "-b:a", "96k", out], check=True)


def build(gender, videos):
    out = os.path.join(ROOT, "art", "practice", "hero", gender)
    url = f"/art/practice/hero/{gender}"
    os.makedirs(out, exist_ok=True)
    cuts, base = {}, None
    for name, spec in MOVES.items():
        a, b, fps = spec["cut"]
        with tempfile.TemporaryDirectory() as tmp:
            files = frames_of(videos[name], a, b, fps, tmp)
            cuts[name] = [cut(np.asarray(Image.open(f).convert("RGB")).astype(np.float32)) for f in files]
        if name == "stance":
            base = bbox(cuts[name][0][..., 3])                 # her standing figure: the unit every box is in
        print(name, len(cuts[name]), "frames")
    bx0, by0, bx1, by1 = base
    bw, bh = bx1 - bx0, by1 - by0
    sheets = {}
    for name, spec in MOVES.items():
        frames = cuts[name]
        boxes = [bbox(f[..., 3], 40) for f in frames]
        x0 = max(0, min(b[0] for b in boxes) - PAD)
        y0 = max(0, min(b[1] for b in boxes) - PAD)
        x1 = min(W, max(b[2] for b in boxes) + PAD)
        y1 = min(H, max(b[3] for b in boxes) + PAD)
        fw, fh = round((x1 - x0) * SCALE), round((y1 - y0) * SCALE)
        cols = max(1, min(len(frames), int(4000 // fw)))
        rows = -(-len(frames) // cols)
        sheet = Image.new("RGBA", (cols * fw, rows * fh))
        for i, f in enumerate(frames):
            im = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8), "RGBA").crop((x0, y0, x1, y1))
            sheet.paste(im.resize((fw, fh), Image.LANCZOS), ((i % cols) * fw, (i // cols) * fh))
        sheet.save(os.path.join(out, name + ".webp"), quality=82, method=6)
        a, b, fps = spec["cut"]
        S = {"src": f"{url}/{name}.webp", "frames": len(frames), "cols": cols, "rows": rows, "fps": fps,
             "box": [round((x0 - bx0) / bw, 4), round((y0 - by0) / bh, 4), round((x1 - x0) / bw, 4),
                     round((y1 - y0) / bh, 4)]}
        if spec.get("loop"):
            S["loop"] = True
        keys = {}
        for k, at in spec.get("keys", {}).items():
            if at == "reach":                                   # the frame where the fist is furthest out
                i = int(np.argmax([bbox(f[..., 3])[2] for f in frames]))
                keys[k] = i
                ys, xs = np.nonzero(frames[i][..., 3] > 128)
                tip = xs.max()
                S["hand"] = [round((tip - bx0) / bw, 4), round((np.median(ys[xs > tip - 12]) - by0) / bh, 4)]
            else:
                keys[k] = max(0, min(len(frames) - 1, round((at - a) * fps)))
        if keys:
            S["keys"] = keys
        if spec.get("sound"):
            sa, sb = spec["sound"]
            sound(videos[name], sa, sb, os.path.join(out, name + ".mp3"))
            S["sound"] = {"src": f"{url}/{name}.mp3"}
        sheets[name] = S
        print(name, S)
    with open(os.path.join(out, "sheets.json"), "w") as fh:
        json.dump({"aspect": round(bw / bh, 4), "sheets": sheets}, fh, indent=1)


def main(args):
    gender, videos = args[0], dict(a.split("=", 1) for a in args[1:])
    missing = set(MOVES) - set(videos)
    if gender not in ("male", "female") or missing:
        sys.exit(__doc__)
    build(gender, videos)


if __name__ == "__main__":
    main(sys.argv[1:])
