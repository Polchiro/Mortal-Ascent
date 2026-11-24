"""
Train's art (docs/training.md "Train on the website"), cut from SHOAIB's Flow pictures and videos into art/train/.

  python -m scripts.make_train_art hero female loop=<video> surge=<video> deviation=<video> scatter=<video>
  python -m scripts.make_train_art hero male   loop=... surge=... deviation=... scatter=...
  python -m scripts.make_train_art chamber <picture> <video>
  python -m scripts.make_train_art fx dantian=<picture> dantian_upper=... seal=... lotus=... knot=... bloom=...
                                      crack=... scatter=... badge=... rival=... hermit=...
  python -m scripts.make_train_art keeper <picture>        (the Quiet Pavilion's keeper, for the town)

hero: the videos are Veo 3.1 Fast, 1920x1080, the character seated in lotus pose facing the viewer on plain grey.
  loop      the meditation loop. Only its calm part is kept (LOOP: the robe opens for a moment in his video, and
            both billow at the start), as a sprite sheet the page plays forwards then backwards, so it never jumps.
  surge / deviation / scatter   the three endings. Their glow, smoke and aura reach far past the body, so each is
            kept as a small video the page can draw over the chamber: the picture on top and its see-through mask
            (white = solid) underneath, in one mp4 ("stacked alpha": it plays in every browser). Its sound is saved
            beside it at full level.
  It also writes sheets.json: where each piece sits, and `fit`: where the figure's acupoints are, so the page can lay
  the meridian map on the body (POINTS below, measured on each first frame; the map's own BODY points are warped to
  them).

chamber: the background picture (the still, and the Hermit's peak the same way), the video as a loop that ends where
  it begins (its last second cross-fades into its first), and its sound as the room's ambience, looped the same way.

fx: glowing pictures painted on pure black become see-through (the brighter, the more solid); Gemini's sparkle in the
  corner and any border are cut away.

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

from . import make_practice_hero as cutter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "train")
URL = "/art/train"
W, H = 1280, 720                       # the videos are worked at this size
SPARKLE = (1120, 570, 1280, 720)       # Gemini's mark (and Flow's, in some videos), at 1280x720: painted over
LOOP = {"female": (4.5, 7.75), "male": (5.0, 7.75)}      # the calm part of each meditation video (s)
LOOP_FPS, LOOP_SCALE = 10, 0.62
END = {"surge": (0.0, 7.6), "deviation": (0.0, 7.6), "scatter": (0.0, 7.6)}
END_FPS, END_SCALE = 24, 0.7
LOUD = -1.0
# The figure's acupoints on the first frame of each meditation video, in 1920x1080 px (left = the viewer's left)
POINTS = {
    "female": {"crown": (968, 140), "throat": (968, 375), "heart": (968, 500), "dantian": (968, 745),
               "l_shoulder": (840, 420), "r_shoulder": (1100, 420), "l_elbow": (745, 640), "r_elbow": (1195, 640),
               "l_palm": (665, 780), "r_palm": (1280, 775), "l_hip": (880, 770), "r_hip": (1060, 770),
               "l_sole": (800, 930), "r_sole": (1140, 930)},
    "male": {"crown": (968, 250), "throat": (968, 415), "heart": (968, 540), "dantian": (968, 770),
             "l_shoulder": (850, 470), "r_shoulder": (1085, 470), "l_elbow": (770, 660), "r_elbow": (1170, 660),
             "l_palm": (690, 770), "r_palm": (1255, 768), "l_hip": (890, 790), "r_hip": (1050, 790),
             "l_sole": (760, 960), "r_sole": (1175, 960)},
}


def run(*cmd):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *cmd], check=True)


def frames_of(video, a, b, fps):
    with tempfile.TemporaryDirectory() as tmp:
        run("-ss", str(a), "-t", str(b - a), "-i", video, "-vf", f"scale={W}:{H}", "-r", str(fps),
            os.path.join(tmp, "%04d.png"))
        return [np.asarray(Image.open(os.path.join(tmp, f)).convert("RGB")).astype(np.float32)
                for f in sorted(os.listdir(tmp))]


def ends_of(video, a, b):
    """An ending's frames, cut one at a time and kept as bytes (a whole video of floats would not fit in memory)."""
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        run("-ss", str(a), "-t", str(b - a), "-i", video, "-vf", f"scale={W}:{H}", "-r", str(END_FPS),
            os.path.join(tmp, "%04d.png"))
        for f in sorted(os.listdir(tmp)):
            im = np.asarray(Image.open(os.path.join(tmp, f)).convert("RGB")).astype(np.float32)
            out.append(np.clip(matte(im), 0, 255).astype(np.uint8))
    return out


def clean(im):
    im = im.copy()
    x0, y0, x1, y1 = SPARKLE
    im[y0:y1, x0:x1] = cutter.backdrop(im)
    return im


def matte(im, glow=True):
    """RGBA of the character off the grey; with `glow`, also the light, smoke and aura around the body, as
    see-through as they are faint."""
    im = clean(im)
    if not glow:
        return cutter.cut(im)
    # An ending lights the backdrop itself, so the plain cut would keep a slab of lit grey. Here the body is what is
    # clearly not backdrop (far from it, or robe-blue), with the gaps it shuts in filled; light and smoke round it
    # are as see-through as they are faint.
    bg = cutter.backdrop(im)
    raw = np.abs(im - bg).max(axis=2)
    tint = (im[..., 2] - im[..., 0]) - (bg[2] - bg[0])
    strong = (raw > 46) | (tint * 1.4 > 16)
    body = ndi.binary_fill_holes(ndi.binary_closing(ndi.binary_opening(strong, iterations=1), iterations=3))
    lab, n = ndi.label(body)
    if n > 1:
        sizes = ndi.sum(body, lab, range(1, n + 1))
        body = np.isin(lab, 1 + np.nonzero(sizes >= sizes.max() * 0.02)[0])
    d = ndi.gaussian_filter(raw, 1.4)
    soft = np.clip((d - 8) / 44, 0, 1)
    a = np.maximum(ndi.gaussian_filter(body.astype(np.float32), 1.0), soft)
    aa = np.clip(a, 0.12, 1)[..., None]
    col = np.where(a[..., None] > 0.97, im, np.clip((im - bg * (1 - aa)) / aa, 0, 255))
    return np.dstack([col, a * 255])


def union_box(frames, thr=24, pad=6):
    xs0, ys0, xs1, ys1 = W, H, 0, 0
    for f in frames:
        ys, xs = np.nonzero(f[..., 3] > thr)
        if len(xs):
            xs0, ys0, xs1, ys1 = min(xs0, xs.min()), min(ys0, ys.min()), max(xs1, xs.max() + 1), max(ys1, ys.max() + 1)
    return int(max(0, xs0 - pad)), int(max(0, ys0 - pad)), int(min(W, xs1 + pad)), int(min(H, ys1 + pad))


def sound(video, a, b, out, fade=0.25):
    probe = subprocess.run(["ffmpeg", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", video, "-af", "volumedetect",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    peak = float(probe.split("max_volume:")[1].split("dB")[0])
    run("-ss", str(a), "-t", str(b - a), "-i", video, "-vn",
        "-af", f"volume={LOUD - peak}dB,afade=t=in:d=0.03,afade=t=out:st={b - a - fade}:d={fade}",
        "-ac", "1", "-ar", "44100", "-b:a", "96k", out)


def fit_of(gender):
    """Where the map's body box (100 units, crown at y 4, Dantian at y 61) sits on the video, and each acupoint in
    those units."""
    p = POINTS[gender]
    k = (p["dantian"][1] - p["crown"][1]) / 57.0
    x0, y0 = p["crown"][0] - 50 * k, p["crown"][1] - 4 * k
    return {"k": round(k, 4), "x0": round(x0, 2), "y0": round(y0, 2),
            "points": {n: [round((x - x0) / k, 2), round((y - y0) / k, 2)] for n, (x, y) in p.items()}}


def hero(gender, videos):
    out = os.path.join(OUT, "hero", gender)
    url = f"{URL}/hero/{gender}"
    os.makedirs(out, exist_ok=True)
    up = 1920 / W                                              # boxes are written in 1920x1080 px, like POINTS
    data = {"fit": fit_of(gender), "ends": {}}
    a, b = LOOP[gender]
    frames = [matte(f, glow=False) for f in frames_of(videos["loop"], a, b, LOOP_FPS)]
    x0, y0, x1, y1 = union_box(frames, 40)
    fw, fh = round((x1 - x0) * LOOP_SCALE), round((y1 - y0) * LOOP_SCALE)
    cols = max(1, min(len(frames), 4096 // fw))
    rows = -(-len(frames) // cols)
    sheet = Image.new("RGBA", (cols * fw, rows * fh))
    for i, f in enumerate(frames):
        im = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8), "RGBA").crop((x0, y0, x1, y1))
        sheet.paste(im.resize((fw, fh), Image.LANCZOS), ((i % cols) * fw, (i // cols) * fh))
    sheet.save(os.path.join(out, "loop.webp"), quality=84, method=6)
    data["loop"] = {"src": f"{url}/loop.webp", "frames": len(frames), "cols": cols, "rows": rows, "fps": LOOP_FPS,
                    "fw": fw, "fh": fh, "box": [round(float(v) * up, 1) for v in (x0, y0, x1 - x0, y1 - y0)]}
    print(gender, "loop", data["loop"])
    for name, (a, b) in END.items():
        frames = ends_of(videos[name], a, b)
        x0, y0, x1, y1 = union_box(frames)
        fw, fh = round((x1 - x0) * END_SCALE) // 2 * 2, round((y1 - y0) * END_SCALE) // 2 * 2
        with tempfile.TemporaryDirectory() as tmp:
            for i, f in enumerate(frames):
                rgba = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8), "RGBA").crop((x0, y0, x1, y1)) \
                    .resize((fw, fh), Image.LANCZOS)
                arr = np.asarray(rgba).astype(np.float32)
                al = arr[..., 3:] / 255
                both = Image.new("RGB", (fw, fh * 2))
                both.paste(Image.fromarray((arr[..., :3] * al).astype(np.uint8), "RGB"), (0, 0))   # on black
                both.paste(Image.merge("RGB", [rgba.getchannel("A")] * 3), (0, fh))
                both.save(os.path.join(tmp, f"{i:04d}.png"))
            run("-framerate", str(END_FPS), "-i", os.path.join(tmp, "%04d.png"), "-c:v", "libx264", "-crf", "24",
                "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                os.path.join(out, name + ".mp4"))
        sound(videos[name], a, b, os.path.join(out, name + ".mp3"))
        data["ends"][name] = {"src": f"{url}/{name}.mp4", "sound": f"{url}/{name}.mp3", "w": fw, "h": fh,
                              "fps": END_FPS, "ms": round(len(frames) / END_FPS * 1000),
                              "box": [round(float(v) * up, 1) for v in (x0, y0, x1 - x0, y1 - y0)]}
        print(gender, name, data["ends"][name])
    with open(os.path.join(out, "sheets.json"), "w") as fh_:
        json.dump(data, fh_, indent=1)


def chamber(picture, video, fade=1.0):
    os.makedirs(OUT, exist_ok=True)
    Image.open(picture).convert("RGB").resize((1920, 1080), Image.LANCZOS).save(
        os.path.join(OUT, "chamber.jpg"), quality=86)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                               capture_output=True, text=True).stdout)
    body = dur - 0.1 - fade
    # the loop: [fade .. end-fade] then the last `fade` seconds cross-fading into the first, so its end meets `fade`
    run("-i", video, "-filter_complex",
        f"[0:v]trim={fade}:{body + fade},setpts=PTS-STARTPTS[a];[0:v]trim={body}:{body + fade},setpts=PTS-STARTPTS[t];"
        f"[0:v]trim=0:{fade},setpts=PTS-STARTPTS[h];[t][h]xfade=transition=fade:duration={fade}:offset=0[x];"
        f"[a][x]concat=n=2:v=1[v0];[v0]trim={0}:{body},setpts=PTS-STARTPTS,drawbox=x=1680:y=860:w=240:h=220:"
        f"color=black@0:t=fill[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", os.path.join(OUT, "chamber.mp4"))
    run("-i", video, "-filter_complex",
        f"[0:a]atrim={fade}:{body},asetpts=PTS-STARTPTS[a];[0:a]atrim={body}:{body + fade},asetpts=PTS-STARTPTS[t];"
        f"[0:a]atrim=0:{fade},asetpts=PTS-STARTPTS[h];[t][h]acrossfade=d={fade}:c1=tri:c2=tri[x];"
        f"[a][x]concat=n=2:v=0:a=1,volume=-6dB[o]",
        "-map", "[o]", "-ac", "1", "-ar", "32000", os.path.join(OUT, "chamber.wav"))
    print("chamber", os.path.getsize(os.path.join(OUT, "chamber.mp4")), os.path.getsize(os.path.join(OUT, "chamber.wav")))


def glow_cut(path, size, inner=None, solid=False, feather=False):
    """A glowing picture on black as a see-through one: `inner` (x0, y0, x1, y1 as fractions) keeps only that part
    (a border round it), `solid` for a thing with a body (the seal), `feather` fades it out towards the edges."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    if inner:
        x0, y0, x1, y1 = (round(inner[0] * w), round(inner[1] * h), round(inner[2] * w), round(inner[3] * h))
        im = im[y0:y1, x0:x1]
        h, w = im.shape[:2]
    else:
        im[round(h * 0.84):, round(w * 0.84):] = 0            # the sparkle
    top = im.max(axis=2)
    if solid:
        a = ndi.binary_fill_holes(ndi.binary_closing(top > 30, iterations=2)).astype(np.float32)
        a = ndi.gaussian_filter(np.maximum(a, np.clip((top - 8) / 60, 0, 1)), 0.8)
        col = im
    else:
        a = np.clip((top - 6) / 150, 0, 1) ** 0.75
        col = np.clip(im / np.clip(a, 0.08, 1)[..., None], 0, 255)
    if feather:
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
        a *= np.clip((1 - r) / 0.35, 0, 1)
    ys, xs = np.nonzero(a > 0.04)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    out = Image.fromarray(np.dstack([col, a * 255]).astype(np.uint8), "RGBA").crop(box)
    out.thumbnail((size, size), Image.LANCZOS)
    return out


def person(path, backdrop_tol=20):
    """Someone standing on a plain backdrop, cut out by colour (the backdrop's is read from the corners)."""
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    bg = np.median(np.concatenate([im[:40, :40].reshape(-1, 3), im[:40, -40:].reshape(-1, 3),
                                   im[-40:, :40].reshape(-1, 3)]), axis=0)
    im[round(h * 0.88):, round(w * 0.82):] = bg                # the sparkle
    d = np.abs(im - bg).max(axis=2)
    body = ndi.binary_fill_holes(ndi.binary_closing(d > backdrop_tol, iterations=3))
    lab, n = ndi.label(body)
    if n > 1:
        sizes = ndi.sum(body, lab, range(1, n + 1))
        body = lab == 1 + int(np.argmax(sizes))
    a = ndi.gaussian_filter(ndi.binary_erosion(body, iterations=1).astype(np.float32), 0.8)
    ys, xs = np.nonzero(a > 0.5)
    return Image.fromarray(np.dstack([im, a * 255]).astype(np.uint8), "RGBA").crop(
        (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def fx(files):
    out = os.path.join(OUT, "fx")
    os.makedirs(out, exist_ok=True)
    spec = {"dantian": (384, {}), "dantian_upper": (384, {}), "seal": (256, {"solid": True}),
            "lotus": (256, {"inner": (0.17, 0.145, 0.83, 0.94)}), "knot": (256, {}), "bloom": (768, {}),
            "crack": (768, {}), "scatter": (640, {"inner": (0.252, 0.252, 0.748, 0.748), "feather": True})}
    for name, path in files.items():
        if name in spec:
            size, more = spec[name]
            im = glow_cut(path, size, **more)
            im.save(os.path.join(out, name + ".webp"), quality=88, method=6)
        elif name == "badge":
            im = Image.open(path).convert("RGB")
            w, h = im.size
            im = im.crop((round(w * 0.14), round(h * 0.1), round(w * 0.86), round(h * 0.82))).resize((256, 256), Image.LANCZOS)
            im.save(os.path.join(OUT, "badge.webp"), quality=88, method=6)
        elif name == "rival":
            im = person(path)
            im.thumbnail((520, 520), Image.LANCZOS)
            im.save(os.path.join(OUT, "rival.webp"), quality=86, method=6)
        elif name == "hermit":
            im = Image.open(path).convert("RGB").resize((1920, 1080), Image.LANCZOS)
            px = im.load()
            for y in range(900, 1010):                           # the sparkle, on the mist: smoothed away
                for x in range(1690, 1800):
                    px[x, y] = px[1680, y]
            im.save(os.path.join(OUT, "hermit.jpg"), quality=86)
        else:
            sys.exit(f"unknown picture: {name}")
        print(name, im.size)


def keeper(path):
    out = os.path.join(ROOT, "art", "portraits", "town", "keeper.webp")
    im = person(path, 16)
    im.thumbnail((400, 900), Image.LANCZOS)
    im.save(out, quality=88, method=6)
    print("keeper", im.size)


def main(args):
    if len(args) >= 2 and args[0] == "hero" and args[1] in POINTS:
        videos = dict(a.split("=", 1) for a in args[2:])
        if {"loop", *END} - set(videos):
            sys.exit(__doc__)
        hero(args[1], videos)
    elif len(args) == 3 and args[0] == "chamber":
        chamber(args[1], args[2])
    elif len(args) >= 2 and args[0] == "fx":
        fx(dict(a.split("=", 1) for a in args[1:]))
    elif len(args) == 2 and args[0] == "keeper":
        keeper(args[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
