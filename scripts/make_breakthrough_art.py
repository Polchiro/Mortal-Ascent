"""
The art of Breakthrough and chest opening on the website (docs/web.md "Breakthrough", "Opening a chest"), cut from
SHOAIB's Flow pictures and videos into art/breakthrough/ and art/chest/.

  python -m scripts.make_breakthrough_art peaks storm=<video> dawn=<video>
  python -m scripts.make_breakthrough_art hero female inner=<video> ascend=<video>
  python -m scripts.make_breakthrough_art hero male   inner=<video> ascend=<video>
  python -m scripts.make_breakthrough_art vault <video>
  python -m scripts.make_breakthrough_art chestfx burst=<video> glow=<video>
  python -m scripts.make_breakthrough_art pictures shelf=<picture> slip=<picture> lid=<picture>
  python -m scripts.make_breakthrough_art fixchamber <Train's chamber video>

peaks: the storm (the Heavenly Tribulation) as a still, a loop that ends where it begins, and its wind and thunder,
  looped the same way; the dawn (Heaven's Light) as a still and as one 8-second play (the beam comes down at ~3 s),
  with its sound. Flow's "Veo" mark and Gemini's sparkle are painted out.
hero: the inner breakthrough (a phase gate passed) and the realm ascension, made like Train's endings
  (scripts/make_train_art.py): a stacked-alpha video drawn over the scene, its sound beside it, and where it sits
  (1920x1080 px), added to sheets.json.
vault: the treasure vault where a chest opens: its still, its loop and its room tone.
chestfx: the treasure burst (a chest bursts open; the page tints it to the chest's tier) and the treasure moment's
  turning ring of light (its first seconds once, then the ring as a loop). Both are light on black: the page adds
  them to the scene ("screen"), so black stays see-through.
pictures: the Treasure Shelf, the jade slip (the back every reward card shares) and the lid burst (the still used
  for Quick opening).

Needs ffmpeg, numpy, Pillow, scipy and OpenCV.
"""
import json
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from . import make_train_art as train

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BT = os.path.join(ROOT, "art", "breakthrough")
CH = os.path.join(ROOT, "art", "chest")
VEO = "delogo=x=1852:y=1026:w=58:h=42"                         # Flow's "Veo" at the bottom right (1920x1080)
DAWN_SPARKLE = (1684, 844, 1838, 1004)                           # Gemini's sparkle, carried over from the picture
BLACK_VEO = "drawbox=x=1840:y=1020:w=80:h=60:color=black:t=fill"
HERO_END = {"inner": (0.0, 7.6), "ascend": (0.0, 7.6)}


def run(*cmd):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd], check=True)


def duration(video):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                capture_output=True, text=True).stdout)


def still(video, at, vf, out, quality=86):
    run("-ss", str(at), "-i", video, "-frames:v", "1", "-vf", vf + ",scale=1920:1080", "-q:v", "3", out + ".tmp.png")
    Image.open(out + ".tmp.png").convert("RGB").save(out, quality=quality)
    os.remove(out + ".tmp.png")


def loop(video, vf, out_mp4, out_audio, a=0.0, b=None, fade=1.0, crf=27, size="1920:1080", gain=-6):
    """[a+fade .. b] then its last `fade` seconds cross-fading into [a .. a+fade], so the end meets the start."""
    b = (duration(video) - 0.1) if b is None else b
    body = b - a - fade
    run("-ss", str(a), "-t", str(b - a), "-i", video, "-filter_complex",
        f"[0:v]{vf},scale={size},split=3[s0][s1][s2];"
        f"[s0]trim={fade}:{body + fade},setpts=PTS-STARTPTS[m];[s1]trim={body}:{body + fade},setpts=PTS-STARTPTS[t];"
        f"[s2]trim=0:{fade},setpts=PTS-STARTPTS[h];[t][h]xfade=transition=fade:duration={fade}:offset=0[x];"
        f"[m][x]concat=n=2:v=1[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", str(crf), "-preset", "slow", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out_mp4)
    if out_audio:
        run("-ss", str(a), "-t", str(b - a), "-i", video, "-filter_complex",
            f"[0:a]atrim={fade}:{body + fade},asetpts=PTS-STARTPTS[m];[0:a]atrim={body}:{body + fade},asetpts=PTS-STARTPTS[t];"
            f"[0:a]atrim=0:{fade},asetpts=PTS-STARTPTS[h];[t][h]acrossfade=d={fade}:c1=tri:c2=tri[x];"
            f"[m][x]concat=n=2:v=0:a=1,volume={gain}dB[o]",
            "-map", "[o]", "-ac", "1", "-ar", "32000", "-b:a", "80k", out_audio)
    return round(body, 3)


def once(video, vf, out_mp4, a=0.0, b=None, crf=26, size="1920:1080"):
    b = (duration(video) - 0.05) if b is None else b
    run("-ss", str(a), "-t", str(b - a), "-i", video, "-vf", f"{vf},scale={size}", "-an", "-c:v", "libx264",
        "-crf", str(crf), "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_mp4)


def refilm(video, out, fix):
    """Run every frame of `video` (1920x1080) through fix(frame) -> frame, losslessly enough to cut again."""
    w, h = 1920, 1080
    src = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    dst = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                            "-r", "24", "-i", "-", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out],
                           stdin=subprocess.PIPE)
    while True:
        buf = src.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        dst.stdin.write(np.ascontiguousarray(fix(np.frombuffer(buf, np.uint8).reshape(h, w, 3))).tobytes())
    dst.stdin.close()
    src.wait()
    dst.wait()


def sound(video, a, b, out, fade=0.3):
    train.sound(video, a, b, out, fade)


def peaks(storm, dawn):
    os.makedirs(BT, exist_ok=True)
    still(storm, 0.05, VEO, os.path.join(BT, "storm.jpg"))
    ms = loop(storm, VEO, os.path.join(BT, "storm.mp4"), os.path.join(BT, "storm.mp3"), fade=1.2)
    print("storm loop", ms)
    fixed = os.path.join(BT, "_dawn.mp4")
    refilm(dawn, fixed, lambda f: np.asarray(lift(Image.fromarray(f), DAWN_SPARKLE, dx=150, feather=14)))
    still(fixed, 0.05, VEO, os.path.join(BT, "dawn.jpg"))
    once(fixed, VEO, os.path.join(BT, "dawn.mp4"))
    still(fixed, duration(fixed) - 0.1, VEO, os.path.join(BT, "dawn_lit.jpg"))
    os.remove(fixed)
    sound(dawn, 0, duration(dawn) - 0.05, os.path.join(BT, "dawn.mp3"), fade=1.0)
    print("dawn", duration(dawn))


MARKS = [(1150, 594, 1216, 660), (1226, 678, 1280, 716)]       # at 1280x720: Gemini's sparkle and Flow's "Veo"


def clean(im):
    """make_train_art.clean, but only the two small marks are painted over: its one big corner box would also cut
    away the light of a burst that reaches the corner."""
    im = im.copy()
    bg = train.cutter.backdrop(im)
    for x0, y0, x1, y1 in MARKS:
        im[y0:y1, x0:x1] = bg
    return im


def figure_of(video):
    """The seated figure's shape on the video's first frame (before the light reaches it), a little grown."""
    first = train.frames_of(video, 0.0, 0.05, 24)[0]
    a = train.matte(first, glow=False)[..., 3] > 128
    return ndi.binary_dilation(ndi.binary_fill_holes(a), iterations=3)


def matte_figure(figure):
    """make_train_art.matte for the inner breakthrough: only the figure's own shape (figure_of) is solid body. Its
    lightning runs to both edges and lights the grey between its bolts, which the plain matte would keep as body;
    here everything outside the figure is light, as see-through as it is faint (sleeves and hair thrown out in the
    burst are bright or dark enough to stay)."""
    def cut(im):
        im = clean(im)
        bg = train.cutter.backdrop(im)
        raw = np.abs(im - bg).max(axis=2)
        d = ndi.gaussian_filter(raw, 1.4)
        soft = np.clip((d - 32) / 70, 0, 1)
        a = np.maximum(ndi.gaussian_filter(figure.astype(np.float32), 1.0), soft)
        aa = np.clip(a, 0.12, 1)[..., None]
        col = np.where(a[..., None] > 0.97, im, np.clip((im - bg * (1 - aa)) / aa, 0, 255))
        return np.dstack([col, a * 255])
    return cut


def glow_matte(im):
    """make_train_art.matte with the small-mark clean."""
    keep = train.clean
    train.clean = clean
    try:
        return train.matte(im)
    finally:
        train.clean = keep


def ends_with(video, a, b, cut):
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        train.run("-ss", str(a), "-t", str(b - a), "-i", video, "-vf", f"scale={train.W}:{train.H}", "-r",
                  str(train.END_FPS), os.path.join(tmp, "%04d.png"))
        for f in sorted(os.listdir(tmp)):
            im = np.asarray(Image.open(os.path.join(tmp, f)).convert("RGB")).astype(np.float32)
            out.append(np.clip(cut(im), 0, 255).astype(np.uint8))
    return out


def hero(gender, videos):
    """Like make_train_art.hero's endings, into art/breakthrough/hero/<gender>/ with its own sheets.json."""
    out = os.path.join(BT, "hero", gender)
    url = f"/art/breakthrough/hero/{gender}"
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "sheets.json")
    data = json.load(open(path)) if os.path.exists(path) else {"ends": {}}
    up = 1920 / train.W
    for name, video in videos.items():
        a, b = HERO_END[name]
        frames = ends_with(video, a, b, matte_figure(figure_of(video)) if name == "inner" else glow_matte)
        x0, y0, x1, y1 = train.union_box(frames)
        fw, fh = round((x1 - x0) * train.END_SCALE) // 2 * 2, round((y1 - y0) * train.END_SCALE) // 2 * 2
        with tempfile.TemporaryDirectory() as tmp:
            for i, f in enumerate(frames):
                rgba = Image.fromarray(f, "RGBA").crop((x0, y0, x1, y1)).resize((fw, fh), Image.LANCZOS)
                arr = np.asarray(rgba).astype(np.float32)
                al = arr[..., 3:] / 255
                both = Image.new("RGB", (fw, fh * 2))
                both.paste(Image.fromarray((arr[..., :3] * al).astype(np.uint8), "RGB"), (0, 0))
                both.paste(Image.merge("RGB", [rgba.getchannel("A")] * 3), (0, fh))
                both.save(os.path.join(tmp, f"{i:04d}.png"))
            run("-framerate", str(train.END_FPS), "-i", os.path.join(tmp, "%04d.png"), "-c:v", "libx264", "-crf", "24",
                "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                os.path.join(out, name + ".mp4"))
        sound(video, a, b, os.path.join(out, name + ".mp3"))
        data["ends"][name] = {"src": f"{url}/{name}.mp4", "sound": f"{url}/{name}.mp3", "w": fw, "h": fh,
                              "fps": train.END_FPS, "ms": round(len(frames) / train.END_FPS * 1000),
                              "box": [round(float(v) * up, 1) for v in (x0, y0, x1 - x0, y1 - y0)]}
        print(gender, name, data["ends"][name])
    with open(path, "w") as fh_:
        json.dump(data, fh_, indent=1)


def vault(video):
    os.makedirs(CH, exist_ok=True)
    still(video, 0.05, VEO, os.path.join(CH, "vault.jpg"))
    ms = loop(video, VEO, os.path.join(CH, "vault.mp4"), os.path.join(CH, "vault.mp3"), fade=1.2, gain=-4)
    print("vault loop", ms)


def chestfx(burst, glow):
    os.makedirs(CH, exist_ok=True)
    once(burst, BLACK_VEO, os.path.join(CH, "burst.mp4"), 0, 4.6, crf=30, size="1280:720")
    sound(burst, 0, 4.6, os.path.join(CH, "burst.mp3"), fade=0.8)
    once(glow, BLACK_VEO, os.path.join(CH, "glow_in.mp4"), 0, 4.2, crf=25, size="1280:720")
    loop(glow, BLACK_VEO, os.path.join(CH, "glow.mp4"), None, a=4.2, b=7.75, fade=1.0, crf=25, size="1280:720")
    sound(glow, 0, 7.75, os.path.join(CH, "glow.mp3"), fade=1.2)
    print("chest fx done")


def lift(im, box, dy=0, feather=10, dx=0):
    """Paint over the sparkle with the same patch from `dy` px higher or `dx` px to the left (curtains run up and
    down, the peak's ground runs sideways), its edges feathered into what was there."""
    arr = np.asarray(im).astype(np.float32)
    x0, y0, x1, y1 = box
    patch = arr[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    m = np.zeros((y1 - y0, x1 - x0), np.float32)
    m[feather:-feather, feather:-feather] = 1
    m = ndi.gaussian_filter(m, feather / 2)[..., None]
    arr[y0:y1, x0:x1] = patch * m + arr[y0:y1, x0:x1] * (1 - m)
    return Image.fromarray(arr.astype(np.uint8))


def inpaint(arr, boxes, radius=7):
    """Paint the boxes (x0, y0, x1, y1 px) over from what surrounds them (for dark, plain places like the chamber's
    pot, where a smoothed patch doesn't show)."""
    mask = np.zeros(arr.shape[:2], np.uint8)
    for x0, y0, x1, y1 in boxes:
        mask[y0:y1, x0:x1] = 255
    return cv2.inpaint(np.ascontiguousarray(arr), mask, radius, cv2.INPAINT_TELEA)


CHAMBER_MARKS = [(1784, 935, 1900, 1045), (1852, 1030, 1914, 1072)]   # on the chamber video: the sparkle and "Veo"
CHAMBER_PICTURE_MARK = [(1745, 895, 1828, 990)]                      # on its still


def fixchamber(video):
    """Train's meditation chamber (art/train), which Breakthrough's phase gates use too, cut again without Gemini's
    sparkle and Flow's mark: the loop and its still. (make_train_art.chamber only blanked them.)"""
    out = os.path.join(ROOT, "art", "train")
    fixed = os.path.join(out, "_chamber.mp4")
    refilm(video, fixed, lambda f: inpaint(f, CHAMBER_MARKS))
    loop(fixed, "null", os.path.join(out, "chamber.mp4"), None, fade=1.0)
    os.remove(fixed)
    pic = os.path.join(out, "chamber.jpg")
    arr = np.asarray(Image.open(pic).convert("RGB"))
    Image.fromarray(inpaint(arr, CHAMBER_PICTURE_MARK)).save(pic, quality=86)
    print("chamber fixed")


def pictures(files):
    os.makedirs(CH, exist_ok=True)
    for name, path in files.items():
        im = Image.open(path).convert("RGB")
        w, h = im.size
        if name == "shelf":
            im = lift(im, (round(w * 0.895), round(h * 0.79), round(w * 0.965), round(h * 0.945)), 130)
            im.resize((1920, 1080), Image.LANCZOS).save(os.path.join(CH, "shelf.jpg"), quality=86)
        elif name == "slip":
            # the slip is the rectangle inside its gold rim; the tassel is what is strongly red. (Its shadow on the
            # grey has a little colour too, so colour alone would keep it.)
            arr = np.asarray(im)
            hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.float32)
            hue, sat = hsv[..., 0], hsv[..., 1] / 255
            gold = (sat > 0.3) & (hue > 12) & (hue < 35)
            gold[round(h * 0.9):, round(w * 0.82):] = False                 # the sparkle
            lab, n = ndi.label(ndi.binary_closing(gold, iterations=2))
            rim = lab == 1 + int(np.argmax(ndi.sum(gold, lab, range(1, n + 1))))
            ys, xs = np.nonzero(rim)
            body = np.zeros((h, w), bool)
            body[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
            red = (sat > 0.35) & ((hue < 8) | (hue > 170))
            lab, n = ndi.label(ndi.binary_closing(red, iterations=2))
            if n:
                body |= lab == 1 + int(np.argmax(ndi.sum(red, lab, range(1, n + 1))))
            body = ndi.binary_fill_holes(body)
            a = ndi.gaussian_filter(body.astype(np.float32), 0.9)
            ys, xs = np.nonzero(a > 0.5)
            cut = Image.fromarray(np.dstack([arr, (a * 255).astype(np.uint8)]), "RGBA").crop(
                (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
            cut.thumbnail((360, 520), Image.LANCZOS)
            cut.save(os.path.join(CH, "slip.webp"), quality=90, method=6)
            im = cut
        elif name == "lid":
            im = train.glow_cut(path, 1024)
            im.save(os.path.join(CH, "lid.webp"), quality=86, method=6)
        else:
            sys.exit(f"unknown picture: {name}")
        print(name, im.size)


def kv(args):
    return dict(a.split("=", 1) for a in args)


def main(args):
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    if cmd == "peaks":
        peaks(**kv(rest))
    elif cmd == "hero":
        hero(rest[0], kv(rest[1:]))
    elif cmd == "vault":
        vault(rest[0])
    elif cmd == "chestfx":
        chestfx(**kv(rest))
    elif cmd == "fixchamber":
        fixchamber(rest[0])
    elif cmd == "pictures":
        pictures(kv(rest))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
