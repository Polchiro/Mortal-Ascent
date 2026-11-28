"""Half-size copies of Practice's and Spar's animation sheets, for phones (docs/technique.md "Practice: smooth on phones").

A phone draws the fighter and Senior Sister Xue about 130 px tall, so the full sheets (made for a big screen) are
far more than it can show, and decoded they fill 30 to 60 MB of a phone's memory per drill, which is what made the
drill stutter there. Each sheet <name>.webp gets a <name>.small.webp beside it: the same grid of frames, each frame
half as wide and half as tall (a quarter of the memory), and sheets.json gets its address as "small". The page
picks the small ones on a phone (a narrow screen or a touch screen).

    python scripts/make_small_sheets.py                 # every Practice folder: both heroes and the instructor
    python scripts/make_small_sheets.py art/practice/hero/male

make_practice_hero.py and make_master_sheets.py --instructor run this themselves after they cut new sheets.
"""
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDERS = [os.path.join(ROOT, "art", "practice", "hero", "female"), os.path.join(ROOT, "art", "practice", "hero", "male"),
           os.path.join(ROOT, "art", "practice", "instructor"), os.path.join(ROOT, "art", "spar", "master")]
SCALE = 0.5


def halve(folder):
    """Write <name>.small.webp for every sheet in folder/sheets.json and record it there as "small"."""
    path = os.path.join(folder, "sheets.json")
    if not os.path.exists(path):
        return
    with open(path) as fh:
        data = json.load(fh)
    for name, S in data["sheets"].items():
        big = os.path.join(folder, os.path.basename(S["src"]))
        if not os.path.exists(big):
            continue
        im = Image.open(big).convert("RGBA")
        cols, rows = S["cols"], S["rows"]
        fw, fh_ = im.width // cols, im.height // rows
        sw, sh = max(1, round(fw * SCALE)), max(1, round(fh_ * SCALE))
        out = Image.new("RGBA", (sw * cols, sh * rows), (0, 0, 0, 0))
        for r in range(rows):                                  # frame by frame, so no frame bleeds into the next
            for c in range(cols):
                cell = im.crop((c * fw, r * fh_, (c + 1) * fw, (r + 1) * fh_)).resize((sw, sh), Image.LANCZOS)
                out.paste(cell, (c * sw, r * sh))
        stem = os.path.splitext(os.path.basename(S["src"]))[0]
        out.save(os.path.join(folder, stem + ".small.webp"), quality=84, method=6)
        S["small"] = S["src"].rsplit("/", 1)[0] + "/" + stem + ".small.webp"
        print(name, im.size, "->", out.size)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=1)


if __name__ == "__main__":
    for f in sys.argv[1:] or FOLDERS:
        halve(os.path.abspath(f))
