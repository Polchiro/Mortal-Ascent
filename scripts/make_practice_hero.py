"""
Your character's unarmed movements in Practice (docs/technique.md "Practice on the website"), cut from SHOAIB's Flow
videos (Veo 3.1 Fast, 1920x1080 or 1280x720, a plain grey backdrop, the character side-on facing right):

  python -m scripts.make_practice_hero female stance=<video> strike=<video> block=<video> struck=<video>
                                             [kick=<video>] [finger=<video>] [duck=<video>] [jump=<video>]

writes art/practice/hero/<gender>/<move>.webp (a sprite sheet), <move>.mp3 (its sound, raised to full level) and
sheets.json. Each move keeps only the part of its video the drill needs (MOVES, per character): the videos are 8 s
long and the character stands still around the move. kick and finger are optional: without them the strike stands in.

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

# What each move keeps of its video, for each character: "cut" (from s, to s, frames a second), "sound" (from s, to s)
# and its key frames (seconds into the video). The videos differ (Flow never moves twice the same way), so each has
# its own times, found by looking at the frames.
#   stance  standing between blows: a loop ("loop": the script finds the two most alike frames near the ends); no
#           sound (a loop of breath tires)
#   strike  the punch, from drawn back (`set`) to the fist at full reach (`out`); the page plays it back in reverse
#           to return. Also kick and finger (optional): the same, for kick and finger techniques
#   block   the arms come up and cross (`up`), the blow is absorbed until the end; the page reverses to return
#   struck  the blow lands, the stagger, the recovery; the page fades back to the stance after it
#   duck    (optional, sidestep techniques) down under a high blow (`down`: the lowest frame); the page reverses up
#   jump    (optional, sidestep techniques) up over a low sweep (`apex`: the highest frame) and down to `land`
# "alone": only the biggest piece (the character) is kept: Flow drew a smear of the sweep under the jump.
# "thin": Flow drew a blade or needle past the fingers of the finger strike; everything thinner than a fist to the
# right of the hand is cut away, so the hands stay empty.
MOVES = {
    "female": {
        "stance": {"cut": (0.0, 7.67, 12), "loop": True},
        "strike": {"cut": (0.0, 1.25, 24), "sound": (1.22, 1.95), "keys": {"set": 0.5, "out": "reach"}},
        "block": {"cut": (0.5, 3.6, 24), "sound": (2.5, 3.25), "keys": {"set": 0.8, "up": 2.05}},
        "struck": {"cut": (1.0, 4.6, 24), "sound": (2.05, 2.95), "keys": {"hit": 1.85}},
        # her big kick goes to the left; the small front kick before it (to the right) is the one kept
        "kick": {"cut": (2.0, 2.65, 24), "sound": (2.45, 2.88), "keys": {"set": 2.05, "out": "reach"}},
        "finger": {"cut": (2.3, 2.95, 24), "sound": (2.75, 3.2), "keys": {"set": 2.35, "out": "reach"}, "thin": True},
        "jump": {"cut": (1.8, 4.6, 24), "sound": (2.7, 3.2), "keys": {"set": 1.9, "apex": "highest", "land": 4.45},
                 "alone": True},
    },
    "male": {
        "stance": {"cut": (0.0, 7.67, 12), "loop": True},
        "strike": {"cut": (2.3, 3.05, 24), "sound": (2.45, 3.05), "keys": {"set": 2.3, "out": "reach"}},
        "block": {"cut": (1.2, 4.9, 16), "sound": (2.95, 3.5), "keys": {"set": 1.3, "up": 2.5}},
        "struck": {"cut": (1.2, 5.0, 16), "sound": (1.55, 2.15), "keys": {"hit": 1.5}},
        "kick": {"cut": (3.25, 4.05, 24), "sound": (3.85, 4.5), "keys": {"set": 3.3, "out": "reach"}},
        "finger": {"cut": (2.2, 3.0, 24), "sound": (2.35, 2.9), "keys": {"set": 2.25, "out": "reach"}, "thin": True},
        "duck": {"cut": (1.5, 3.2, 24), "sound": (1.9, 2.6), "keys": {"set": 1.6, "down": "lowest"}},
        # from the moment his feet leave the floor: before it, Flow's smear of the sweep runs through his feet
        "jump": {"cut": (2.75, 4.3, 24), "sound": (2.95, 3.5), "keys": {"set": 2.75, "apex": "highest", "land": 4.1},
                 "alone": True},
    },
}
NEEDED = ("stance", "strike", "block", "struck")
FIST = 16                              # px (at 1280x720): anything thinner than this past the hand is a blade


def frames_of(video, a, b, fps, folder):
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", video,
                    "-vf", f"scale={W}:{H}", "-r", str(fps), os.path.join(folder, "%04d.png")], check=True)
    return sorted(os.path.join(folder, f) for f in os.listdir(folder))


def backdrop(im):
    edge = [im[:30, :300], im[-30:, :300], im[:30, -300:]]
    return np.median(np.concatenate([e.reshape(-1, 3) for e in edge]), axis=0)


def cut(im, alone=False):
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
        body = lab == 1 + int(np.argmax(sizes)) if alone else np.isin(lab, 1 + np.nonzero(sizes >= sizes.max() * 0.04)[0])
    gaps, n = ndi.label(ndi.binary_opening(body & (score < 6), iterations=2))   # backdrop seen through her
    for i in range(1, n + 1):
        if (gaps == i).sum() > 300:
            body &= ~ndi.binary_dilation(gaps == i, iterations=1)
    soft = np.clip((score - 5) / 16, 0, 1) * ndi.binary_dilation(body, iterations=2)
    a = ndi.gaussian_filter(np.maximum(ndi.binary_erosion(body, iterations=1).astype(np.float32), soft), 0.6)
    aa = np.clip(a, 0.08, 1)[..., None]
    col = np.where(a[..., None] < 0.95, np.clip((im - bg * (1 - aa)) / aa, 0, 255), im)
    return np.dstack([col, a * 255])


def empty_hand(rgba):
    """Cut away what is thinner than a fist to the right of the hand (a blade, a needle)."""
    tall = (rgba[..., 3] > 128).sum(axis=0)
    thick = np.nonzero(tall >= FIST)[0]
    if len(thick):
        rgba[:, thick.max() + 2:, 3] = 0
    return rgba


def best_loop(frames):
    """(first, last) frames of the most seamless loop: an early frame and a late one that look most alike."""
    small = [np.asarray(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8), "RGBA").resize((160, 90)))
             .astype(np.float32) for f in frames]
    n = len(small)
    pairs = [(np.abs(small[a] - small[b]).mean(), a, b) for a in range(0, max(1, n // 8)) for b in range(n - n // 5, n)]
    _, a, b = min(pairs)
    return a, b


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
    moves = {n: spec for n, spec in MOVES[gender].items() if n in videos}
    for name, spec in moves.items():
        a, b, fps = spec["cut"]
        with tempfile.TemporaryDirectory() as tmp:
            files = frames_of(videos[name], a, b, fps, tmp)
            cuts[name] = [cut(np.asarray(Image.open(f).convert("RGB")).astype(np.float32), spec.get("alone"))
                          for f in files]
        if spec.get("thin"):
            cuts[name] = [empty_hand(f) for f in cuts[name]]
        if name == "stance":
            base = bbox(cuts[name][0][..., 3])                 # the standing figure: the unit every box is in
            first, last = best_loop(cuts[name])
            cuts[name] = cuts[name][first:last]
        print(name, len(cuts[name]), "frames")
    bx0, by0, bx1, by1 = base
    bw, bh = bx1 - bx0, by1 - by0
    sheets = {}
    for name, spec in moves.items():
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
            elif at in ("lowest", "highest"):                   # the head at its lowest (duck) or feet at their highest
                tops = [bbox(f[..., 3])[1] for f in frames]
                feet = [bbox(f[..., 3])[3] for f in frames]
                keys[k] = int(np.argmax(tops)) if at == "lowest" else int(np.argmin(feet))
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
    if gender not in MOVES or set(NEEDED) - set(videos):
        sys.exit(__doc__)
    build(gender, videos)


if __name__ == "__main__":
    main(sys.argv[1:])
