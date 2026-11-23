"""Paint the open lands' ground (web/land.py LANDS, docs/world.md) from the town's four textures.

    python -m scripts.make_land                 (every land)
    python -m scripts.make_land forest_edge     (one)

For each land it writes art/maps/land/<key>/: the ground cut into CHUNK px squares (c_<col>_<row>.webp; squares
wholly outside the diamond are skipped), chunks.json (which exist, their size and scale) and preview.webp (the whole
land, small). The page loads the chunks near you, so a land of any size costs no more than the screen.

The painting is scripts/make_town_ground.py's, pixel by pixel in the isometric view (nothing stretched): the land's
base texture where you walk, its rim texture beyond, round patches of other ground, dirt paths along the land's
curves, every edge roughened with smooth noise, wide soft light and dark so a big field isn't flat, the land's tint,
and darkness at the diamond's rim. Deterministic. Needs numpy and Pillow.
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

from scripts.make_town_ground import TILE_PX, rect_dist, road_dist, sample, textures
from web import land

CHUNK = 1024
F = 1.0                               # output px per world px (a tile is 128 x 64 world px)
V = 1                                 # bump to make browsers fetch repainted chunks
SEED = 23


def paint(tex, key, rows=256):
    spec = land.LANDS[key]
    n, edge = spec["size"], spec["edge"]
    width = int(n * 128 * F)
    h = width // 2
    rng = np.random.default_rng(SEED + sum(map(ord, key)))

    def smooth(cells, blur):
        field = Image.fromarray((rng.random((cells, cells)) * 255).astype(np.uint8)).resize((768, 768), Image.BICUBIC)
        a = np.asarray(field.filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
        return ((a - a.mean()) / (a.std() * 4))[..., None]
    noise = smooth(48, 10) * 1.0 + smooth(192, 3) * 0.45          # wide wobbles and small bites
    shade = smooth(10, 26)                                         # light and dark, many tiles across
    segs = [(a, b, w) for a, b, w in land.segments(key)]
    # how far into the nearest path (tiles), worked out once on a fine grid of the land and read from it after
    G = 8
    gx, gy = np.meshgrid(np.arange(-2 * G, (n + 2) * G + 1, dtype=np.float32) / G,
                         np.arange(-2 * G, (n + 2) * G + 1, dtype=np.float32) / G)
    field = road_dist(gx, gy, segs)[..., None] if segs else None

    def in_path(X, Y):
        return sample(field, (X + 2) * G, (Y + 2) * G, wrap=False)[..., 0]
    tint = np.array(spec["tint"], np.float32)
    out = np.zeros((h, width, 3), np.uint8)
    us = np.arange(width, dtype=np.float32)
    for v0 in range(0, h, rows):
        vs = np.arange(v0, min(h, v0 + rows), dtype=np.float32)
        U, V_ = np.meshgrid(us, vs)
        wx, wy = U / F - n * 64, V_ / F
        X = (wx / 64 + wy / 32) / 2
        Y = (wy / 32 - wx / 64) / 2
        nz = sample(noise, (X + 16) * 12, (Y + 16) * 12)[..., 0]
        tx, ty = X * TILE_PX, Y * TILE_PX
        t = {"grass": sample(tex["grass"], tx, ty), "dirt": sample(tex["dirt"], tx + 311, ty + 97) * 0.86,
             "stone": sample(tex["stone"], tx, ty), "forest": sample(tex["forest"], tx + 53, ty + 211) * 0.9}
        px = t[spec["base"]]
        for cx, cy, r, name in spec.get("patches", ()):
            if name in ("stone", "dirt"):
                continue
            m = np.clip((r - np.hypot(X - cx, Y - cy) + nz * 2.4) / 1.4, 0, 1)[..., None]
            px = px * (1 - m) + t[name] * m
        for cx, cy, r, name in spec.get("patches", ()):
            if name != "dirt":
                continue
            m = np.clip((r - np.hypot(X - cx, Y - cy) + nz * 1.6) / 0.6, 0, 1)[..., None]
            px = px * (1 - m) + t[name] * m
        if segs:
            m = np.clip((in_path(X, Y) + nz * 0.9) / 0.45, 0, 1)[..., None]
            px = px * (1 - m) + t["dirt"] * m
        for cx, cy, r, name in spec.get("patches", ()):
            if name != "stone":
                continue
            m = np.clip((r - np.hypot(X - cx, Y - cy) + nz * 0.3) / 0.14, 0, 1)[..., None]
            px = px * (1 - m) + t[name] * m
        inside = np.clip((rect_dist(X, Y, (edge, edge, n - edge, n - edge)) + nz * 0.6) / 0.3, 0, 1)[..., None]
        if spec["rim"] != spec["base"]:
            rim = t[spec["rim"]] * 0.82
            keep = np.maximum(inside, np.clip((in_path(X, Y) + 0.4) / 0.4, 0, 1)[..., None]) if segs else inside
            px = px * keep + rim * (1 - keep)
        px = px * (1 + sample(shade, (X + 8) * 3.1, (Y + 8) * 3.1) * 0.5)
        dark = np.clip((rect_dist(X, Y, (0, 0, n, n)) + nz * 0.5) / (edge + 0.6), 0, 1)[..., None]     # into the rim
        px = px * (0.18 + 0.82 * dark ** 1.3) * tint
        px[(rect_dist(X, Y, (0, 0, n, n)) < 0)] = (11, 11, 13)                 # beyond the diamond: the page's dark
        out[v0:v0 + len(vs)] = px.clip(0, 255).astype(np.uint8)
    return Image.fromarray(out)


def write(key, tex):
    im = paint(tex, key)
    d = os.path.join(land.DIR, key)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    a = np.asarray(im)
    have = []
    for row in range(0, im.height, CHUNK):
        for col in range(0, im.width, CHUNK):
            c = a[row:row + CHUNK, col:col + CHUNK]
            if (c.max(2) <= 13).all():
                continue
            name = f"{col // CHUNK}_{row // CHUNK}"
            Image.fromarray(c).save(os.path.join(d, f"c_{name}.webp"), "WEBP", quality=80, method=6)
            have.append(name)
    im.resize((1536, 768), Image.LANCZOS).save(os.path.join(d, "preview.webp"), "WEBP", quality=78, method=6)
    with open(os.path.join(d, "chunks.json"), "w") as f:
        json.dump({"chunk": CHUNK, "f": F, "have": have, "v": V, "w": im.width, "h": im.height}, f)
    size = sum(os.path.getsize(os.path.join(d, n)) for n in os.listdir(d))
    print(f"{key}: {im.width}x{im.height}, {len(have)} chunks, {size // 1024} KB")


def main(argv):
    tex = textures()
    for key in argv or list(land.LANDS):
        write(key, tex)


if __name__ == "__main__":
    main(sys.argv[1:])
