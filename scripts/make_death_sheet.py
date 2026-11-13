"""Cuts a shared death animation (art/fx/death/<category>.webp) out of SHOAIB's reference video: a sprite sheet on
white paper, 4 x 2 numbered cells, the beast staggering and going down. Keys out the paper, the grid, the frame
numbers and the painted shadow, and writes the frames as one transparent grid (same cell size, every frame on the same ground line). Prints the numbers beasts.DEATH_ANIMATIONS needs (the standing body's box, the ground).

  python -m scripts.make_death_sheet <video.mp4> [category] [seconds into the video where the sheet is complete]
  (needs ffmpeg, numpy, scipy)
"""
import io
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLS, ROWS = 4, 2
XS = [(24, 319), (336, 631), (649, 944), (962, 1256)]         # the cells on the 1280 x 720 video frame
YS = [(36, 351), (370, 685)]
INSET, LABEL = 5, 40                                          # skip the grid line; the number sits in a corner


def still(video, at):
    """The sheet itself: the median of three video frames in a row (the drawing keeps shifting a little through the
    video, so no more than that), which takes the video noise out."""
    shots = []
    for i in range(3):
        png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at + i / 24:.3f}", "-i", video, "-frames:v", "1",
                              "-f", "image2pipe", "-vcodec", "png", "-"], check=True, capture_output=True).stdout
        shots.append(np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(np.float32))
    return np.median(np.stack(shots), axis=0)


def cut(cell):
    mn, mx = cell.min(axis=2), cell.max(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1)
    light = (mn > 205) | ((mn > 128) & (sat < 0.07))          # paper, and the soft grey shadow painted under it
    light[:LABEL, :LABEL] = True                               # the frame number
    lab, _ = ndi.label(light)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fg = ~np.isin(lab, list(edge))
    paper = (mn > 222) & (sat < 0.05)                          # white paper shut in between the legs (teeth are smaller)
    lp, npaper = ndi.label(paper)
    big = np.zeros(npaper + 1, bool)
    big[1:] = ndi.sum(paper, lp, range(1, npaper + 1)) >= 45
    fg &= ~ndi.binary_dilation(big[lp], iterations=2)
    lab2, n = ndi.label(fg)                                    # keep the beast, drop specks
    sizes = ndi.sum(fg, lab2, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= sizes.max() * 0.03
    fg = keep[lab2]
    fg = ndi.binary_erosion(ndi.binary_opening(fg, iterations=1), iterations=1)
    alpha = ndi.gaussian_filter(fg.astype(np.float32), 0.8)
    alpha = np.clip((alpha - 0.35) / 0.4, 0, 1)                # a soft edge pulled in a little: no pale fringe
    rgb = cell.copy()
    rim = (alpha > 0) & ~ndi.binary_erosion(fg, iterations=3)  # the edge is mixed with paper: hold it to the dark outline
    scale = np.minimum(1, 62 / np.maximum(mx, 1))
    rgb[rim] *= scale[rim][:, None]
    return np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8)


def main():
    video = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else "quadruped"
    at = float(sys.argv[3]) if len(sys.argv) > 3 else 6.5
    sheet = still(video, at)
    w = min(x1 - x0 for x0, x1 in XS) - 2 * INSET
    h = min(y1 - y0 for y0, y1 in YS) - 2 * INSET
    out = Image.new("RGBA", (w * COLS, h * ROWS))
    boxes = []
    for r, (y0, _) in enumerate(YS):
        for c, (x0, _) in enumerate(XS):
            frame = cut(sheet[y0 + INSET:y0 + INSET + h, x0 + INSET:x0 + INSET + w])
            ys, xs = np.nonzero(frame[:, :, 3] > 128)
            drop = h - 2 - ys.max()                            # every frame stands or lies on the same ground line
            frame = np.concatenate([np.zeros_like(frame[:drop]), frame[:h - drop]])
            out.paste(Image.fromarray(frame), (c * w, r * h))
            ys, xs = np.nonzero(frame[:, :, 3] > 128)
            boxes.append((xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h))
    folder = os.path.join(ROOT, "art", "fx", "death")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{category}.webp")
    out.save(path, "WEBP", quality=92, method=6)
    ground = max(b[3] for b in boxes)
    print(path, out.size, f"cell {w} x {h}")
    print("body (frame 1, standing): left %.3f top %.3f right %.3f bottom %.3f" % boxes[0])
    print("ground: %.3f" % ground)
    for i, b in enumerate(boxes):
        print(i + 1, "%.3f %.3f %.3f %.3f" % b)


if __name__ == "__main__":
    main()
