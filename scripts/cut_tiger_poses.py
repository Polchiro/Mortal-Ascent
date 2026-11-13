"""Cuts the Mountain Tiger's fight poses (art/beasts/poses/mountain_tiger/) out of SHOAIB's reference video
(a sprite sheet on white paper): keys out the paper, the grid lines and the pale dust, takes the white out of the
edges so there is no pale fringe, flips them to face left, and writes poses.json (each pose's size and place in %
of the idle pose, read by web/explore_play.beast_poses).

  ffmpeg -i video.mp4 -vf fps=4 <frames>/f%02d.png
  python -m scripts.cut_tiger_poses <frames> <scratch>      (needs numpy, scipy)
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
F = sys.argv[1].rstrip('/') + '/' if len(sys.argv) > 1 else 'frames/'
O = sys.argv[2].rstrip('/') + '/' if len(sys.argv) > 2 else 'cut/'
CROPS = {  # pose: (frame, box, loose zones (x0, y0, x1, y1) as shares of the crop: pale dust / flagstones go too)
    "idle":   (40, (330, 40, 640, 352), []),
    "crouch": (40, (0, 40, 327, 352), [(0, 0.8, 0.3, 1)]),
    "leap":   (23, (640, 18, 1268, 355), [(0, 0.55, 0.55, 1)]),
    "slam":   (40, (0, 360, 560, 708), [(0, 0.62, 1, 1), (0.62, 0.45, 1, 1), (0, 0.52, 0.4, 1)]),
    "roar":   (40, (645, 330, 1268, 708), [(0, 0.66, 1, 1), (0.8, 0, 1, 1)]),
}

ERASE = {(645, 330, 1268, 708): [(0.04, 0.45, 0.2, 0.7), (0.25, 0.44, 0.58, 0.68)],
         (0, 360, 560, 708): [(0, 0, 0.14, 0.5), (0.1, 0.5, 0.45, 0.75)]}
frame_fade = {(0, 360, 560, 708): (0.55, 0.84, 0.47, 0.17), (645, 330, 1268, 708): (0.48, 0.86, 0.47, 0.15)}


def cut(frame, box, zones, thr=208, minsize=400):
    im = np.asarray(Image.open(F + f"f{frame:02d}.png").convert("RGB").crop(box)).astype(np.float32)
    mn = im.min(axis=2)
    mx = im.max(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1)
    light = (mn > thr) | ((mn > 170) & (sat < 0.06))        # paper white, grid lines, faint shadows
    h, w = mn.shape
    for x0, y0, x1, y1 in zones:
        z = np.zeros_like(light)
        z[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = True
        light |= z & (mn > 120) & (sat < 0.22)
    lab, n = ndi.label(light)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(edge))
    for x0, y0, x1, y1 in ERASE.get(box, []):
        z = np.zeros_like(bg)
        z[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = True
        bg |= z & (mn > 165) & (sat < 0.16)
    pure = (mn > 231) & (sat < 0.045)                          # white paper shut in between the legs
    lp, npure = ndi.label(pure)
    big = np.zeros(npure + 1, bool)
    big[1:] = ndi.sum(pure, lp, range(1, npure + 1)) >= 250
    bg |= ndi.binary_dilation(big[lp], iterations=1)
    fg = ~bg
    # drop specks (numbers, stray stones) but keep anything big
    lab2, n2 = ndi.label(fg)
    sizes = ndi.sum(fg, lab2, range(1, n2 + 1))
    keep = np.zeros(n2 + 1, bool)
    keep[1:] = sizes >= max(minsize, sizes.max() * 0.04)
    fg = keep[lab2]
    fg = ndi.binary_fill_holes(fg) if False else fg
    # soft edge: within 3px of the background, alpha follows how far the colour is from white
    near = ndi.binary_dilation(~fg, iterations=3) & fg
    soft = np.clip((255 - mn - 6) / 70.0, 0, 1)
    alpha = np.where(near, soft, fg.astype(np.float32))
    alpha = ndi.gaussian_filter(alpha, 0.6) * fg
    # take the white out of the edge pixels (no pale fringe)
    if frame_fade.get(box):
        cx, cy, rx, ry = frame_fade[box]
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx / w - cx) / rx) ** 2 + ((yy / h - cy) / ry) ** 2)
        f = np.clip((1.12 - d) / 0.32, 0, 1)
        ground = yy / h > cy - ry * 0.5
        alpha = np.where(ground, alpha * f, alpha)
    a = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.clip((im - (1 - a) * 255) / a, 0, 255)
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")

for pose, (fr, box, zones) in CROPS.items():
    img = cut(fr, box, zones)
    img.save(O + pose + ".png")
    bg = Image.new("RGBA", img.size, (40, 46, 60, 255)); bg.alpha_composite(img); bg.save(O + pose + "_dark.png")
    print(pose, img.size, img.getchannel("A").getbbox())

# ── assemble: flip to face left, scale the roar to the others, geometry relative to the idle pose ──
import json
import os
SCALE = {"roar": 0.78}
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "art", "beasts", "poses", "mountain_tiger") + "/"
os.makedirs(OUTDIR, exist_ok=True)
imgs = {}
for pose in CROPS:
    im = Image.open(O + pose + ".png")
    im = im.crop(im.getchannel("A").getbbox()).transpose(Image.FLIP_LEFT_RIGHT)
    k = SCALE.get(pose, 1.0) * 1.5            # a little larger than the video, for sharp edges on big screens
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    imgs[pose] = im
iw, ih = imgs["idle"].size
geo = {}
for pose, im in imgs.items():
    im.save(OUTDIR + pose + ".webp", "WEBP", quality=90, method=6)
    # centred on the idle pose, feet on the same ground line
    geo[pose] = {"w": round(im.width / iw * 100, 2), "h": round(im.height / ih * 100, 2),
                 "left": round((iw - im.width) / 2 / iw * 100, 2), "bottom": 0}
geo["leap"]["bottom"] = 8
geo["slam"]["bottom"] = -6
geo["roar"]["bottom"] = -8
json.dump({"aspect": [iw, ih], "poses": geo}, open(OUTDIR + "poses.json", "w"), indent=1)
print(geo, iw, ih)
