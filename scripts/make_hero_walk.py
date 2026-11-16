"""Build the male cultivator's walk for the hunting-ground map (looks.WALK_SHEETS, web/static/huntmap.js) from
SHOAIB's walk video (docs/hunting.md "The map").

The video (Gemini, 1280 x 720, 24 fps, 10 s) is one cultivator walking in place, camera fixed, on a dark plain
backdrop, turning slowly: front (S) → SE → E → NE → back (N) → and the same way back to the front. He never faces
left, so SW, W and NW are his SE, E and NE mirrored. One stride (two steps) is about 32 frames; he turns while he
walks, so each direction's loop is the stride centred where that view is truest (WINDOWS, picked by eye and by how
well the last frame meets the first).

    python -m scripts.make_hero_walk path/to/walk.mp4

Writes art/portraits/map/hero_male_walk.webp: the spec sheet, 8 rows (S SW W NW N NE E SE) x 8 frames, cells
256 x 256, the point between the feet at (128, 232), about 200 px tall, and prints each row's standing frame
(feet closest together) for looks.WALK_SHEETS["male"]["stand"].
Needs ffmpeg, numpy, Pillow and rembg (the isnet-general-use model).
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageOps

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "portraits", "map",
                   "hero_male_walk.webp")
CROP = (320, 0, 960, 720)              # x0, y0, x1, y1 of the video around him
ORDER = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
# direction → (video frame the loop starts at, frames in the stride); SW, W, NW mirror SE, E, NE
WINDOWS = {"S": (202, 35), "SE": (30, 28), "E": (62, 28), "NE": (122, 28), "N": (100, 32)}
MIRROR = {"SW": "SE", "W": "E", "NW": "NE"}
CELL, FEET, HEIGHT = 256, (128, 232), 200
SRC_FEET, SRC_HEIGHT = (320, 672), 590  # in the crop: between his feet, and his height


def frames(video, folder):
    x0, y0, x1, y1 = CROP
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}",
                    os.path.join(folder, "f%03d.png")], check=True)
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("f"))


def cut(paths):
    from rembg import new_session, remove
    session = new_session("isnet-general-use")
    return [remove(Image.open(p), session=session).convert("RGBA") for p in paths]


def feet_spread(im):
    a = np.asarray(im)[:, :, 3] > 100
    ys, xs = np.nonzero(a)
    _, xx = np.nonzero(a[ys.max() - 70:ys.max() + 1])
    return int(xx.max() - xx.min())


def sheet(cuts):
    """The spec sheet, and each row's standing frame."""
    scale = HEIGHT / SRC_HEIGHT
    at = (round(FEET[0] - SRC_FEET[0] * scale), round(FEET[1] - SRC_FEET[1] * scale))
    out, stand = Image.new("RGBA", (CELL * 8, CELL * 8)), []
    for r, d in enumerate(ORDER):
        start, n = WINDOWS[MIRROR.get(d, d)]
        idx = [start + round(j * n / 8) for j in range(8)]
        for j, i in enumerate(idx):
            im = cuts[i].resize((round(cuts[i].width * scale), round(cuts[i].height * scale)), Image.LANCZOS)
            cell = Image.new("RGBA", (CELL, CELL))
            cell.alpha_composite(im, at)
            out.alpha_composite(ImageOps.mirror(cell) if d in MIRROR else cell, (j * CELL, r * CELL))
        stand.append(min(range(8), key=lambda j: feet_spread(cuts[idx[j]])))
    return out, stand


def check(im, rows=8, cols=8):
    """The spec (docs/hunting.md): a list of what is wrong, empty when the sheet is right."""
    bad = []
    if im.mode != "RGBA":
        bad.append("no transparency")
    if im.size != (CELL * cols, CELL * rows):
        bad.append(f"size {im.size}, expected {(CELL * cols, CELL * rows)}")
        return bad
    a = np.asarray(im)[:, :, 3]
    for r in range(rows):
        for c in range(cols):
            cell = a[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 100
            if not cell.any():
                bad.append(f"row {r + 1} ({ORDER[r]}) frame {c + 1} is empty")
                continue
            ys, xs = np.nonzero(cell)
            if xs.min() == 0 or xs.max() == CELL - 1 or ys.min() == 0:
                bad.append(f"row {r + 1} ({ORDER[r]}) frame {c + 1} touches the cell edge")
            if abs(ys.max() - FEET[1]) > 24:
                bad.append(f"row {r + 1} ({ORDER[r]}) frame {c + 1}: feet at y {ys.max()}, expected about {FEET[1]}")
    return bad


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        cuts = cut(frames(video, tmp))
    out, stand = sheet(cuts)
    bad = check(out)
    if bad:
        sys.exit("The sheet does not meet the spec:\n  " + "\n  ".join(bad))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, "WEBP", quality=88, method=6)
    print(f"wrote {OUT}; stand frames per row ({' '.join(ORDER)}): {stand}")


if __name__ == "__main__":
    main(sys.argv[1])
