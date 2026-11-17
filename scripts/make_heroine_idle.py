"""Build the female cultivator's idle (standing, breathing) for the hunting-ground map (looks.WALK_SHEETS["female"]
["idle"], web/static/huntmap.js) from SHOAIB's five idle videos (docs/hunting.md "The map").

Each video (Gemini, 720 x 1280, 24 fps, 10 s) is her standing in place facing one way, breathing, robes stirring:
front (S), front-right (SE), "right" (E), back (N) and back-right (NE). As made:
- the right one came out turned only a little more than front-right, so E is that, not a true profile;
- the back-right one faces back-LEFT once she has turned round (its first 5 s), so it is mirrored for NE and used
  as it is for NW;
- the back two have long hair down her back that her walk does not.
In each video the script finds the stretch (2-4.6 s) whose last frame best meets its first, takes 8 frames from it,
and lines them up exactly like her walk (scripts/make_heroine_walk.py).

    python -m scripts.make_heroine_idle front.mp4 front_right.mp4 right.mp4 back_right.mp4 back.mp4

Writes art/portraits/map/hero_female_idle.webp: 8 rows (S SW W NW N NE E SE) x 8 frames, cells 256 x 256, the
point between the feet at (128, 232), about 200 px tall, and prints the loop length for looks.WALK_SHEETS.
"""
import os
import sys

from PIL import Image, ImageOps

from scripts.make_hero_walk import CELL, ORDER, check
from scripts.make_heroine_walk import cut, probe, raw, row, stride

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "portraits", "map",
                   "hero_female_idle.webp")
VIEWS = ["S", "SE", "E", "NE", "N"]         # the order the videos are given in
SKIP = {"NE": 120, "N": 30}                 # frames spent turning round before she stands
SPAN = (48, 110)                            # frames in one loop, at least and most
# row → (view it comes from, mirrored?)
SOURCE = {"S": ("S", False), "SE": ("SE", False), "E": ("E", False), "SW": ("SE", True), "W": ("E", True),
          "NE": ("NE", True), "NW": ("NE", False), "N": ("N", False)}


def main(videos):
    if len(videos) != len(VIEWS):
        sys.exit(f"give the five videos in this order: {', '.join(VIEWS)}")
    from rembg import new_session
    session = new_session("isnet-general-use")
    rows, loops = {}, []
    for view, video in zip(VIEWS, videos):
        w, h = probe(video)
        a, n = stride(video, SKIP.get(view, 0), SPAN)
        frames = raw(video, w, h)
        rows[view] = row(cut([frames[a + round(j * n / 8)] for j in range(8)], session))
        loops.append(n / 24)
        print(f"{view}: frames {a}-{a + n}")
    out = Image.new("RGBA", (CELL * 8, CELL * 8))
    for r, d in enumerate(ORDER):
        view, flip = SOURCE[d]
        for j, cell in enumerate(rows[view]):
            out.alpha_composite(ImageOps.mirror(cell) if flip else cell, (j * CELL, r * CELL))
    bad = check(out)
    if bad:
        sys.exit("The sheet does not meet the spec:\n  " + "\n  ".join(bad))
    out.save(OUT, "WEBP", quality=88, method=6)
    print(f"wrote {OUT}; loop {sum(loops) / len(loops):.2f} s")


if __name__ == "__main__":
    main(sys.argv[1:])
