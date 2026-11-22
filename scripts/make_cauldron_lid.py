"""Split the cauldron picture (art/scenes/cauldron.png) into its body and its lid, so the pill reveal can blow the lid
off (art/scenes/cauldron_body.png, cauldron_lid.png; alchemy_play.html .preveal, docs/web.md "The pill reveal").

Both are the cauldron's own canvas (628 x 700), so they stack exactly where the whole picture stood. The lid is the
flat disc on top (LID: the ellipse of its top face and of its bottom edge); the body gets a dark mouth where the lid
sat (MOUTH), shaded darker toward its back, with a thin bronze lip.

    python -m scripts.make_cauldron_lid
Needs Pillow.
"""
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "art", "scenes", "cauldron.png")
LID = [(127, 110, 496, 202), (127, 124, 496, 219)]     # the disc's top face and bottom edge (union = the lid)
MOUTH = (150, 186, 478, 232)                            # the opening under it


def main():
    im = Image.open(SRC).convert("RGBA")
    mask = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(mask)
    for box in LID:
        d.ellipse(box, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    lid = im.copy()
    lid.putalpha(ImageChops.multiply(im.split()[3], mask))
    body = im.copy()
    body.putalpha(ImageChops.multiply(im.split()[3], ImageChops.invert(mask)))
    inside = Image.new("RGBA", im.size, (0, 0, 0, 0))            # the dark mouth, under the body's own rim
    di = ImageDraw.Draw(inside)
    di.ellipse(MOUTH, fill=(18, 26, 22, 255), outline=(92, 120, 96, 255), width=4)
    x0, y0, x1, y1 = MOUTH
    di.ellipse((x0 + 20, y0 + 4, x1 - 20, y1 - 12), fill=(6, 10, 9, 255))
    inside = inside.filter(ImageFilter.GaussianBlur(1.5))
    out = Image.alpha_composite(inside, body)
    out.save(os.path.join(ROOT, "art", "scenes", "cauldron_body.png"), optimize=True)
    lid.crop(lid.getbbox()).save(os.path.join(ROOT, "art", "scenes", "cauldron_lid.png"), optimize=True)
    print("lid box", lid.getbbox())


if __name__ == "__main__":
    main()
