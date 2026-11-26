"""Cut SHOAIB's painted forging materials (Nov 26 2026) into the game's icons (docs/forge.md "Pictures").

    python -m scripts.make_material_art metals=grid.png hides=grid.png jades=grid.png bindings=grid.png \
                                        fuels=grid.png liquids=grid.png \
                                        base:weapon:2=one.png fuel:5=one.png base:artifact:4=one.png

Each grid is 3 x 2 cells read left to right, top row first: a family's five tiers, then one extra in the sixth cell
(GRIDS below; fuels and liquids leave it empty). A single picture replaces one material (a redo). A source may end
in @x,y,r;... to paint Gemini's sparkle out where it touches an object (shares of the picture, as make_gather_art).

Every object is cut off its flat grey backdrop as the herbs are (scripts/make_gather_art.cut), fitted into a
transparent ICON x ICON square and written to art/icons/mat/<key>.webp, where cards/art_icons.resolve finds it
for "mat:<key>": the Discord cards, the bag, the forge and the quarry all show it from there. No ring or rarity
colour is painted in: each page and card adds its own.

The three essence shapes (shard, crystal, heart) are painted colourless. They are kept as
art/icons/mat/essence_shape_<shape>.webp and tinted once per family colour (cards/material_icons.FAMILY_COLOR)
into the 39 essence icons, art/icons/mat/essence_<family>_<shape>.webp. Run with no pictures to re-tint only.

The source files are only read. Needs numpy, opencv, Pillow and rembg (isnet-general-use).
"""
import os
import sys

import numpy as np
from PIL import Image

import forge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "icons", "mat")
ICON = 256                   # the square's side (px)
FILL = 0.9                   # the object's longest side, as a share of it
SHAPES = ("shard", "crystal", "heart")

GRIDS = {
    "metals":   ["base:weapon:1", "base:weapon:2", "base:weapon:3", "base:weapon:4", "base:weapon:5", "seal"],
    "hides":    ["base:armor:1", "base:armor:2", "base:armor:3", "base:armor:4", "base:armor:5", "shape:shard"],
    "jades":    ["base:artifact:1", "base:artifact:2", "base:artifact:3", "base:artifact:4", "base:artifact:5",
                 "shape:crystal"],
    "bindings": ["binding:1", "binding:2", "binding:3", "binding:4", "binding:5", "shape:heart"],
    "fuels":    ["fuel:1", "fuel:2", "fuel:3", "fuel:4", "fuel:5"],
    "liquids":  ["liquid:1", "liquid:2", "liquid:3", "liquid:4", "liquid:5"],
}


def file_name(key):
    """'base:weapon:2' -> 'base_weapon_2' (as cards/art_icons.resolve looks it up); 'shape:heart' -> 'essence_shape_heart'."""
    if key.startswith("shape:"):
        return "essence_shape_" + key[6:]
    return key.replace(":", "_")


def square(obj):
    """The cut-out object centred in a transparent ICON x ICON square, its longest side ICON * FILL."""
    s = ICON * FILL / max(obj.size)
    obj = obj.resize((max(1, round(obj.width * s)), max(1, round(obj.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    out.alpha_composite(obj, ((ICON - obj.width) // 2, (ICON - obj.height) // 2))
    return out


def tint(shape, color):
    """A colourless essence shape in a family's colour: its shading kept (dark parts take the colour deeper, the
    brightest stay near white, as light inside a coloured crystal does)."""
    a = np.asarray(shape.convert("RGBA")).astype(np.float32) / 255
    lum = (a[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    c = np.array(color, np.float32)[None, None, :] / 255
    lo = 2 * lum * c                                         # overlay: shade toward the colour ...
    hi = 1 - 2 * (1 - lum) * (1 - c)                         # ... light toward white
    rgb = np.where(lum < 0.5, lo, hi)
    rgb = rgb * 0.7 + c * 0.3 * np.minimum(lum * 1.6, 1)       # more of the colour all over
    return Image.fromarray((np.dstack([np.clip(rgb, 0, 1), a[..., 3:]]) * 255).astype(np.uint8))


def essences():
    from cards.material_icons import FAMILY_COLOR
    fams = sorted({k.split(":")[1] for k in forge.all_materials() if k.startswith("essence:")})
    for shape in SHAPES:
        src = os.path.join(OUT, f"essence_shape_{shape}.webp")
        if not os.path.exists(src):
            print(f"no {shape} shape yet: its essences keep their drawn icons", flush=True)
            continue
        base = Image.open(src)
        for fam in fams:
            tint(base, FAMILY_COLOR[fam]).save(os.path.join(OUT, f"essence_{fam}_{shape}.webp"), "WEBP",
                                               quality=90, method=6)
        print(f"{shape}: {len(fams)} essences tinted", flush=True)


def main(args):
    from scripts.make_gather_art import cut, pairs, unsparkle
    jobs = pairs(args)
    if jobs:
        from rembg import new_session
        session = new_session("isnet-general-use")
    os.makedirs(OUT, exist_ok=True)
    known = set(forge.all_materials())
    for name, (src, spots) in jobs.items():
        im = Image.open(src).convert("RGB")
        if spots:
            im = unsparkle(im, spots)
        if name in GRIDS:
            w, h = im.size
            cells = [(k, im.crop(((i % 3) * w // 3, (i // 3) * h // 2, (i % 3 + 1) * w // 3, (i // 3 + 1) * h // 2)))
                     for i, k in enumerate(GRIDS[name])]
        elif name in known:
            cells = [(name, im)]
        else:
            raise SystemExit(f"{name}: not a grid ({', '.join(GRIDS)}) or a material key")
        for key, pic in cells:
            obj, _ = cut(pic, session, shadows=False)
            square(obj).save(os.path.join(OUT, file_name(key) + ".webp"), "WEBP", quality=90, method=6)
            print(f"{key}: {obj.width} x {obj.height}", flush=True)
    essences()


if __name__ == "__main__":
    main(sys.argv[1:])
