"""Build the new male cultivator's map animations (looks.WALK_SHEETS["male"], web/static/town.js, huntmap.js) from
SHOAIB's fifteen videos of him (Nov 25; docs/hunting.md "The map"): standing (idle), walking and running in place,
each facing one way: front (S), front-right (SE), right (E), back-right (NE) and back (N). He never faces left, so
SW, W and NW are SE, E and NE mirrored. Made as hers are (scripts/make_heroine_walk.py, whose tools this uses), but
with FRAMES pictures per cycle instead of 8, so his steps and breathing play smoother (the maps read `cols`).

In each video the script finds the stretch (a stride of two steps, or a breath) whose last frame best meets its
first, takes FRAMES pictures from it evenly, cuts him out (rembg), and sets every picture of a row on the same spot
between his feet, all at the same height.

    python -m scripts.make_hero_map idle front.mp4 front_right.mp4 right.mp4 back_right.mp4 back.mp4
    python -m scripts.make_hero_map walk ...
    python -m scripts.make_hero_map run ...

The videos as made: some are tall (720 x 1280), some wide; the run ones begin with a second or so of him standing
before he gets going (SKIP). Writes art/portraits/map/hero_male_<idle|walk|run>.webp: 8 rows (S SW W NW N NE E SE)
x FRAMES pictures, cells 256 x 256, the point between the feet at (128, 232), about 200 px tall, and prints what
looks.WALK_SHEETS needs (each row's standing frame: feet closest together; the idle's loop length).
Needs ffmpeg, numpy, scipy, Pillow and rembg (the isnet-general-use model).
"""
import os
import sys

from PIL import Image, ImageOps

from scripts.make_hero_walk import CELL, MIRROR, ORDER, check, feet_spread
from scripts.make_heroine_walk import cut, probe, raw, row, stride

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "portraits", "map")
VIEWS = ["S", "SE", "E", "NE", "N"]     # the order the videos are given in
FRAMES = 16
SPAN = {"idle": (48, 110), "walk": (36, 64), "run": (19, 32)}     # frames in one cycle, at least and most
SKIP = {"idle": 12, "walk": 12, "run": 36}                         # frames left out at the start


def build(gait, videos):
    if len(videos) != len(VIEWS):
        sys.exit(f"give the five videos in this order: {', '.join(VIEWS)}")
    from rembg import new_session
    session = new_session("isnet-general-use")
    rows, stand, loops = {}, {}, []
    for view, video in zip(VIEWS, videos):
        w, h = probe(video)
        a, n = stride(video, SKIP[gait], SPAN[gait])
        frames = raw(video, w, h)
        rows[view] = row(cut([frames[a + round(j * n / FRAMES)] for j in range(FRAMES)], session))
        stand[view] = min(range(FRAMES), key=lambda j: feet_spread(rows[view][j]))
        loops.append(n / 24)
        print(f"{gait} {view}: video frames {a}-{a + n} ({n / 24:.2f} s)", flush=True)
    out = Image.new("RGBA", (CELL * FRAMES, CELL * 8))
    for r, d in enumerate(ORDER):
        for j, cell in enumerate(rows[MIRROR.get(d, d)]):
            out.alpha_composite(ImageOps.mirror(cell) if d in MIRROR else cell, (j * CELL, r * CELL))
    bad = check(out, cols=FRAMES)
    if bad:
        sys.exit("The sheet does not meet the spec:\n  " + "\n  ".join(bad))
    path = os.path.join(OUT, f"hero_male_{gait}.webp")
    out.save(path, "WEBP", quality=86, method=6)
    print(f"wrote {path}; cols {FRAMES}; stand per row ({' '.join(ORDER)}): {[stand[MIRROR.get(d, d)] for d in ORDER]};"
          f" loop {sum(loops) / len(loops):.2f} s")


if __name__ == "__main__":
    if len(sys.argv) != 7 or sys.argv[1] not in SPAN:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2:])
