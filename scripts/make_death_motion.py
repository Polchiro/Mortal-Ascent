"""Measures a shared death animation's MOVEMENT from SHOAIB's reference video: a sprite sheet on white paper, 4 x 2
numbered cells, a beast staggering and going down. Only the movement is taken, never the drawing: for each frame,
how wide the body lies and how high its back stands along its length (tail to head), as shares of the standing
first frame. Prints the "motion" rows for beasts.DEATH_ANIMATIONS; web/static/fight.js plays them on each beast's
own picture. Nothing is written to art/.

  python -m scripts.make_death_motion <video.mp4> [seconds into the video where the sheet is complete]
  (needs ffmpeg, numpy, scipy)
"""
import io
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

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


COLUMNS = 12                                                  # points along the body, tail to head


def profile(alpha):
    """(body width in px, the back's height above the ground at COLUMNS points along the body)."""
    ys, xs = np.nonzero(alpha)
    x0, x1, ground = xs.min(), xs.max() + 1, ys.max() + 1
    tops = np.array([np.nonzero(alpha[:, x])[0].min() if alpha[:, x].any() else np.nan for x in range(x0, x1)])
    high = ground - tops
    at = np.arange(len(high))
    ok = ~np.isnan(high)
    high = np.interp(at, at[ok], high[ok])
    return x1 - x0, np.array([high[int(i * len(high) / COLUMNS):int((i + 1) * len(high) / COLUMNS)].mean()
                              for i in range(COLUMNS)])


def main():
    video = sys.argv[1]
    at = float(sys.argv[2]) if len(sys.argv) > 2 else 6.5
    sheet = still(video, at)
    w = min(x1 - x0 for x0, x1 in XS) - 2 * INSET
    h = min(y1 - y0 for y0, y1 in YS) - 2 * INSET
    rows = []
    for y0, _ in YS:
        for x0, _ in XS:
            rows.append(profile(cut(sheet[y0 + INSET:y0 + INSET + h, x0 + INSET:x0 + INSET + w])[:, :, 3] > 128))
    wide0, high0 = rows[0]
    print('"motion": [   # (width, the back\'s height tail -> head), as shares of frame 1')
    for wide, high in rows:
        r = high / high0
        r[0] = max(r[0], r[1] * 0.9)                           # the tail tip waves about: follow the rump
        r = np.convolve(np.pad(r, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid")
        print(f"    ({wide / wide0:.2f}, ({', '.join(f'{v:.2f}' for v in np.clip(r, 0.2, 1.15))})),")
    print("],")


if __name__ == "__main__":
    main()
