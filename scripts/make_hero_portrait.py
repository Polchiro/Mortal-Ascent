"""Cut a cultivator's profile painting and round face from SHOAIB's painting of them (looks.portrait, looks.face;
docs/appearance.md, docs/web.md "The profile page").

The painting (Gemini, 16:9) is the cultivator standing calm on a plain grey backdrop, no sword, the whole body in
the picture. The script cuts them out (rembg, as every hero script does), drops Gemini's sparkle mark (bottom
right), trims to the figure and writes:

    art/portraits/hero_<gender>.webp        the painting, see-through, HEIGHT px tall (feet at the bottom edge)
    art/portraits/hero_<gender>_face.webp   FACE x FACE, head and shoulders on the page's dark jade, for the circles

    python -m scripts.make_hero_portrait male path/to/his_painting.png

Needs numpy, Pillow, scipy and rembg.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "portraits")
HEIGHT = 880                      # the painting as saved (the source figure is about 400 px tall: scaled up smoothly)
FACE = 256
FACE_BG = (16, 34, 40)            # the circles' backdrop
HEAD = 0.27                      # the head and shoulders: this share of the figure's height, from the top
PAD = 12                          # clear pixels kept around the figure


def cut_out(im):
    """The painting with its backdrop made see-through: the model's mask, then only the figure's own piece."""
    from rembg import new_session, remove
    from scipy import ndimage
    big = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)              # the model sees more detail
    m = remove(big, session=new_session("isnet-general-use"), only_mask=True).resize(im.size, Image.LANCZOS)
    a = np.asarray(m).copy()
    lab, n = ndimage.label(a > 40)
    if n > 1:                                                                  # Gemini's sparkle, stray specks
        sizes = ndimage.sum(a > 40, lab, range(1, n + 1))
        a[lab != 1 + int(np.argmax(sizes))] = 0
    inside = ndimage.binary_erosion(ndimage.binary_fill_holes(a > 40), iterations=5)
    a[inside] = 255                                                            # pale silk the model half-dropped
    out = im.convert("RGBA")
    out.putalpha(Image.fromarray(a))
    return out


def trim(rgba):
    box = rgba.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return rgba.crop(box)


def painting(fig):
    s = HEIGHT / fig.height
    fig = fig.resize((round(fig.width * s), HEIGHT), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.6, 60, 2))
    out = Image.new("RGBA", (fig.width + 2 * PAD, HEIGHT + PAD))
    out.alpha_composite(fig, (PAD, PAD))
    return out


def face(fig):
    """Head and shoulders, the head in the middle of a square."""
    a = np.asarray(fig.getchannel("A")) > 60
    top = a[: max(4, round(fig.height * 0.09))]                                # the hair and brow: where the head is
    xs = np.where(top.any(0))[0]
    cx = (xs.min() + xs.max()) / 2
    side = fig.height * HEAD
    box = (round(cx - side / 2), round(-side * 0.1), round(cx + side / 2), round(side * 0.9))
    crop = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]))
    crop.alpha_composite(fig, (-box[0], -box[1]))
    crop = crop.resize((FACE, FACE), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.4, 50, 2))
    out = Image.new("RGBA", (FACE, FACE), FACE_BG + (255,))
    out.alpha_composite(crop)
    return out.convert("RGB")


def main(gender, path):
    fig = trim(cut_out(Image.open(path).convert("RGB")))
    full = painting(fig)
    full.save(os.path.join(OUT, f"hero_{gender}.webp"), quality=92, method=6)
    face(fig).save(os.path.join(OUT, f"hero_{gender}_face.webp"), quality=92, method=6)
    print(f"hero_{gender}.webp {full.size}, hero_{gender}_face.webp {FACE}x{FACE}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("male", "female"):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
