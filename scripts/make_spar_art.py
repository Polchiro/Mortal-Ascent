"""Prepare the spar's still pictures from SHOAIB's Nov 24 Gemini images (art/spar/; docs/technique.md "On the website").

    python -m scripts.make_spar_art seal=a.png ripple=b.png yard=c.png front=d.png shield=e.png dust=f.png \
        emblem=g.png banners=h.png header=i.png ambience=yard_video.mp4

- seal, ripple, shield, dust, emblem (painted on black): black becomes clear (how bright a pixel is, is how solid it
  is), Gemini's sparkle is blanked, the picture is trimmed to what is painted.
- banners (two brush strokes on black, gold above grey): the same, cut into banner_win and banner_lose.
- front (a blossom branch and a lantern under an eave, on green): green becomes clear, cut into front_left and
  front_right, each trimmed.
- yard (the arena's background) and header (the Master in the yard): Gemini's sparkle painted out; saved as JPEG.

- ambience=<the yard's background video>: its own sound (a soft wind and chimes), made into a loop with no seam (its
  last 1.5 s faded into its first) and raised until it is plainly heard (art/spar/yard.wav; a WAV so it loops with no
  gap). The moving picture itself is made by scripts/make_background_loop.py (art/spar/yard.mp4), and yard.jpg is that
  loop's first frame, so the still and the video are the same picture.

Needs numpy, Pillow, scipy, opencv (for painting out the sparkle) and ffmpeg (for the ambience).
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "spar")


def mark_box(w, h):
    """Gemini's sparkle sits near the bottom right corner, whatever the picture's shape."""
    return int(w * 0.845), int(h - w * 0.165), int(w * 0.945), int(h - w * 0.065)


def trim(rgba, pad=4):
    ys, xs = np.where(rgba[..., 3] > 6)
    return rgba[max(0, ys.min() - pad):ys.max() + pad + 1, max(0, xs.min() - pad):xs.max() + pad + 1]


def from_black(path, gain=1.0):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    x0, y0, x1, y1 = mark_box(w, h)
    im[y0:y1, x0:x1] = 0
    a = np.clip((im.max(axis=2) - 10) / 245 * gain, 0, 1)
    col = np.clip(im / np.clip(a, 0.04, 1)[..., None], 0, 255)
    return np.dstack([col, a * 255])


def save(rgba, name, width=None):
    im = Image.fromarray(rgba.astype(np.uint8), "RGBA")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, name + ".webp"), quality=88, method=6)
    print(name, im.size)


def from_green(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    x0, y0, x1, y1 = mark_box(w, h)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    spill = g - np.maximum(r, b)                                # how much greener than anything painted would be
    a = 1 - np.clip((spill - 40) / 90, 0, 1)
    a[y0:y1, x0:x1] = 0
    a = ndi.gaussian_filter(a, 0.6)
    col = im.copy()
    edge = a < 0.98
    col[..., 1][edge] = np.minimum(g, np.maximum(r, b) + 12)[edge]          # take the green cast off the soft edges
    return np.dstack([col, a * 255])


def paint_out(path):
    import cv2
    im = cv2.imread(path)
    h, w = im.shape[:2]
    x0, y0, x1, y1 = mark_box(w, h)
    patch = im[y0:y1, x0:x1].astype(np.int16)
    base = cv2.medianBlur(im, 31)[y0:y1, x0:x1].astype(np.int16)
    m = np.zeros((h, w), np.uint8)
    m[y0:y1, x0:x1] = ((patch - base).max(axis=2) > 10).astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    return cv2.cvtColor(cv2.inpaint(im, m, 7, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)


def ambience(video, loop=1.5, rate=24000, level=0.11):
    import subprocess
    import wave
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(rate), "-af", "highpass=f=70",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = int(loop * rate)
    fade = np.linspace(0, 1, n, dtype=np.float32)
    head = x[:n] * np.sqrt(fade) + x[-n:] * np.sqrt(1 - fade)           # the end flows into the start
    y = np.concatenate([head, x[n:-n]])
    y *= level / max(1e-6, float(np.sqrt((y ** 2).mean())))            # how loud it is on the whole
    y = np.tanh(y * 1.2) / 1.2                                          # and no peak clips
    with wave.open(os.path.join(OUT, "yard.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    print("yard.wav", f"{len(y) / rate:.1f} s")


def main(args):
    os.makedirs(OUT, exist_ok=True)
    got = dict(a.split("=", 1) for a in args)
    if "ambience" in got:
        ambience(got["ambience"])
    for name, width in (("seal", 640), ("ripple", 640), ("shield", 520), ("dust", 760), ("emblem", 720)):
        if name in got:
            save(trim(from_black(got[name], 1.25 if name in ("dust", "shield") else 1.0)), name, width)
    if "banners" in got:
        b = from_black(got["banners"], 1.6)
        half = b.shape[0] // 2
        save(trim(b[:half]), "banner_win", 900)
        save(trim(b[half:]), "banner_lose", 900)
    if "front" in got:
        f = from_green(got["front"])
        half = f.shape[1] // 2
        save(trim(f[:, :half]), "front_left")
        save(trim(f[:, half:]), "front_right")
    for name in ("yard", "header"):
        if name in got:
            Image.fromarray(paint_out(got[name])).save(os.path.join(OUT, name + ".jpg"), quality=90)
            print(name)


if __name__ == "__main__":
    main(sys.argv[1:])
