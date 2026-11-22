"""Paint the town's ground (art/maps/town.webp) from four textures and web/town.py's GROUND (docs/town.md).

The textures (art/maps/town/tex/: grass, dirt, stone paving, forest floor) are the top faces of SHOAIB's Gemini
ground tiles, lifted flat by scripts/make_town_kit.py's neighbour (`lift` below: the tile's top diamond mapped
back to a square, its rim trimmed). Each is quilted into a large seamless tile: many randomly turned and flipped
copies blended with soft-edged windows, so nothing visibly repeats. Stone paving is laid as mirrored copies
instead, as blending would ghost its joints.

The ground is then painted in the town's own isometric view, pixel by pixel: grass inside the walls, forest floor
outside them, dirt on GROUND["dirt"] and stone on GROUND["stone"] (rectangles in tiles), each edge roughened with
smooth noise; a soft shadow round every building's footprint seats it on the ground; and dusk dims it all to
match the buildings' lighting. Nothing is stretched: every pixel is sampled from a texture at its own scale, so the
ground is as sharp as the textures however big the town is drawn.

    python -m scripts.make_town_ground              (re-quilts and repaints; deterministic)
    python -m scripts.make_town_ground crossroads   (the Crossroads outside the gate: web/crossroads.py, docs/world.md)
    python -m scripts.make_town_ground lift grass=tile.png ...   (lifts new textures from Gemini tiles first)

Writes art/maps/town.webp (or art/maps/crossroads.webp): WIDTH x WIDTH/2 for the 32 x 32 tile diamond (a tile
128 x 64 world px, so WIDTH 6144 is 1.5x the world: crisp when the page zooms in). Needs numpy and Pillow.

A place's GROUND gives rectangles of "dirt" and "stone", optional "roads" (segments: start, end, width in tiles,
for roads that run at any angle), and "walls": the rectangle with grass inside and forest floor outside.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

from web import town

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "art", "maps", "town", "tex")
OUT = os.path.join(ROOT, "art", "maps", "town.webp")
WIDTH = 6144
TILE_PX = 136                     # texture pixels across one tile: how big the grass blades and stones are
QUILT = 2048                      # the seamless textures' size
DUSK = np.array([0.74, 0.72, 0.80], np.float32)    # the buildings were painted at dusk: dim the ground to match
SEED = 7


def lift(path, out, inset=0.13, size=768):
    """A Gemini ground tile's top face as a flat square: its left and right corners and top point, mapped back."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    border = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3)])
    m = np.sqrt(((a - np.median(border, 0)) ** 2).sum(2)) > 30
    m[int(m.shape[0] * 0.88):, int(m.shape[1] * 0.8):] = False          # Gemini's sparkle in the corner
    ys, xs = np.nonzero(m)
    L = np.array([xs.min(), ys[xs == xs.min()].mean()])
    R = np.array([xs.max(), ys[xs == xs.max()].mean()])
    c = (L + R) / 2
    col = m[:, int(c[0]) - 3:int(c[0]) + 4].any(1)
    T = np.array([c[0], np.nonzero(col)[0].min()])
    U, V = np.meshgrid(np.linspace(inset, 1 - inset, size), np.linspace(inset, 1 - inset, size))
    X = T[0] + U * (R[0] - T[0]) + V * (L[0] - T[0])
    Y = T[1] + U * (R[1] - T[1]) + V * (L[1] - T[1])
    Image.fromarray(sample(a.astype(np.float32), X, Y, wrap=False).clip(0, 255).astype(np.uint8)).save(out)


def sample(img, X, Y, wrap=True):
    """Bilinear sample of img at (X, Y) pixels (wrapping round a seamless texture)."""
    h, w = img.shape[:2]
    x0, y0 = np.floor(X).astype(int), np.floor(Y).astype(int)
    fx, fy = (X - x0)[..., None], (Y - y0)[..., None]
    if wrap:
        xa, xb, ya, yb = x0 % w, (x0 + 1) % w, y0 % h, (y0 + 1) % h
    else:
        xa, xb, ya, yb = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1), np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    return (img[ya, xa] * (1 - fx) * (1 - fy) + img[ya, xb] * fx * (1 - fy)
            + img[yb, xa] * (1 - fx) * fy + img[yb, xb] * fx * fy)


def quilt(patch, rng, rotate=True, step=420):
    p = np.asarray(Image.open(patch).convert("RGB")).astype(np.float32)
    n = p.shape[0]
    w1 = np.sin(np.linspace(0, np.pi, n)) ** 2
    win = np.outer(w1, w1)[..., None] + 1e-4
    acc = np.zeros((QUILT, QUILT, 3), np.float32)
    wsum = np.zeros((QUILT, QUILT, 1), np.float32)
    for gy in range(0, QUILT, step):
        for gx in range(0, QUILT, step):
            q = np.rot90(p, rng.integers(4)) if rotate else p
            if rng.random() < .5:
                q = q[:, ::-1]
            ys = (np.arange(n) + gy + rng.integers(-step // 3, step // 3)) % QUILT
            xs = (np.arange(n) + gx + rng.integers(-step // 3, step // 3)) % QUILT
            acc[np.ix_(ys, xs)] += q * win
            wsum[np.ix_(ys, xs)] += win
    out = acc / wsum
    mean = out.mean((0, 1))
    return ((out - mean) * 1.18 + mean).clip(0, 255)        # blending flattens contrast a little: restore it


def mirrored(patch):
    p = np.asarray(Image.open(patch).convert("RGB")).astype(np.float32)
    row = np.concatenate([p, p[:, ::-1]], 1)
    return np.concatenate([row, row[::-1]], 0)


def textures():
    rng = np.random.default_rng(SEED)
    return {"grass": quilt(os.path.join(TEX, "grass.webp"), rng), "dirt": quilt(os.path.join(TEX, "dirt.webp"), rng),
            "forest": quilt(os.path.join(TEX, "forest.webp"), rng), "stone": mirrored(os.path.join(TEX, "stone.webp"))}


def rect_dist(X, Y, r):
    """Signed distance (tiles) into a rectangle: positive inside."""
    x0, y0, x1, y1 = r
    return np.minimum(np.minimum(X - x0, x1 - X), np.minimum(Y - y0, y1 - Y))


def union(X, Y, rects):
    return np.max([rect_dist(X, Y, r) for r in rects], axis=0)


def road_dist(X, Y, roads):
    """Signed distance (tiles) into the nearest road: positive inside."""
    out = np.full(X.shape, -99.0, np.float32)
    for (ax, ay), (bx, by), w in roads:
        dx, dy = bx - ax, by - ay
        t = np.clip(((X - ax) * dx + (Y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
        d = np.hypot(X - (ax + t * dx), Y - (ay + t * dy))
        out = np.maximum(out, w / 2 - d)
    return out


def footprint_shadow(X, Y, place=town):
    """How much a building's foot darkens the ground: strongest at its edge, fading over half a tile."""
    d = np.full(X.shape, 99.0, np.float32)
    for b in place.BUILDINGS:
        if b["img"] == "wall":
            continue
        inside = rect_dist(X, Y, (b["x0"], b["y0"], b["x0"] + b["a"], b["y0"] + b["b"]))
        d = np.minimum(d, np.maximum(-inside, 0))
    return np.exp(-d / 0.45) * 0.38


def paint(tex, width=WIDTH, rows=256, place=town):
    h = width // 2
    rng = np.random.default_rng(SEED + 1)
    def smooth(cells, blur):
        field = Image.fromarray((rng.random((cells, cells)) * 255).astype(np.uint8)).resize((768, 768), Image.BICUBIC)
        a = np.asarray(field.filter(ImageFilter.GaussianBlur(blur))).astype(np.float32)
        return ((a - a.mean()) / (a.std() * 4))[..., None]
    noise = smooth(48, 10) * 1.0 + smooth(192, 3) * 0.45          # wide wobbles and small bites
    out = np.zeros((h, width, 3), np.uint8)
    size, ground = place.SIZE, place.GROUND
    f = width / (size * 128)                               # output px per world px
    us = np.arange(width, dtype=np.float32)
    for v0 in range(0, h, rows):
        vs = np.arange(v0, min(h, v0 + rows), dtype=np.float32)
        U, V = np.meshgrid(us, vs)
        wx, wy = U / f - size * 64, V / f                              # world px, the diamond's top corner at x 0
        X = (wx / 64 + wy / 32) / 2                                     # tiles
        Y = (wy / 32 - wx / 64) / 2
        n = sample(noise, (X + 16) * 12, (Y + 16) * 12)[..., 0]        # smooth noise, about a tile across
        tx, ty = X * TILE_PX, Y * TILE_PX
        g = sample(tex["grass"], tx, ty)
        d = sample(tex["dirt"], tx + 311, ty + 97)
        s = sample(tex["stone"], tx, ty)
        fo = sample(tex["forest"], tx + 53, ty + 211)
        inroad = union(X, Y, ground["dirt"]) if ground["dirt"] else np.full(X.shape, -99.0, np.float32)
        if ground.get("roads"):
            inroad = np.maximum(inroad, road_dist(X, Y, ground["roads"]))
        dirt = np.clip((inroad + n * 1.8) / 0.45, 0, 1)[..., None]
        stone = (np.clip((union(X, Y, ground["stone"]) + n * 0.25) / 0.12, 0, 1)[..., None] if ground["stone"]
                 else np.zeros(X.shape + (1,), np.float32))
        inside = np.clip((rect_dist(X, Y, ground["walls"]) + n * 0.6) / 0.3, 0, 1)[..., None]
        px = g * (1 - dirt) + d * 0.86 * dirt                          # the dirt a little darker, as the grass
        px = px * (1 - stone) + s * stone
        px = px * inside + fo * 0.82 * (1 - inside)                     # the forest floor outside, a little darker
        px = px * (1 - footprint_shadow(X, Y, place)[..., None]) * DUSK
        out[v0:v0 + len(vs)] = px.clip(0, 255).astype(np.uint8)
    return Image.fromarray(out)


def main(argv):
    if argv[:1] == ["lift"]:
        for pair in argv[1:]:
            name, _, src = pair.partition("=")
            lift(src, os.path.join(TEX, f"{name}.png"))
            Image.open(os.path.join(TEX, f"{name}.png")).save(os.path.join(TEX, f"{name}.webp"), "WEBP", quality=92)
            os.remove(os.path.join(TEX, f"{name}.png"))
    if argv[:1] == ["crossroads"]:
        from web import crossroads
        out = os.path.join(ROOT, "art", "maps", "crossroads.webp")
        paint(textures(), place=crossroads).save(out, "WEBP", quality=84, method=6)
        print(f"wrote {out}")
        return
    paint(textures()).save(OUT, "WEBP", quality=84, method=6)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
