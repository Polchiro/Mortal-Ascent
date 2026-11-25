"""
The open lands (docs/world.md): big, empty, walkable ground outside the town. A land is only ground for now: grass,
forest floor, dirt paths and a few clearings, laid out by hand here. What stands on it (trees, rocks, ruins) is added
later, piece by piece, once the land itself feels right to walk.

Each land is a SIZE x SIZE diamond of the same 2:1 tiles as the town (x runs down-right on screen, y down-left). Its
ground is painted from the town's four textures by `python -m scripts.make_land` into square chunks
(art/maps/land/<key>/c_<col>_<row>.webp, with a small preview.webp of the whole land), which the page loads as you
come near them: a land can be any size without one huge picture.

LANDS[key]:
  size      tiles across
  edge      how far in from the diamond's rim you can walk
  base/rim  the ground's texture where you walk / beyond it (grass, forest, dirt, stone)
  tint      the light there (r, g, b multipliers: dusk on the Crossroads, darker and bluer under the trees)
  paths     dirt paths: (width in tiles, [waypoints]); drawn as smooth curves through the waypoints
  patches   round areas of another ground: (x, y, radius, texture)
  gates     where you walk in and out (web/overworld.py joins them): key → {"at": (x, y), "side": the edge it is on}
  start     where you stand if you arrive from nowhere
A path that leaves by a gate carries on past the rim, so it looks like it goes somewhere: the next land's path picks
it up at the matching gate, on the opposite edge, in the same ground.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = "/art/maps/land"
DIR = os.path.join(ROOT, "art", "maps", "land")

ROAD_W = 2.4                          # a road's width (tiles); a forest path is narrower
PATH_W = 2.0
MOUTH = 0.8                           # a gate stands this far inside the walkable ground's rim
DUSK = (0.74, 0.72, 0.80)
SCALE = 1.4                           # every land is drawn as big against you as the town is (town.SCALE): the grass,
                                      # the paths and, later, the trees are all one size from the gate to the grove
ZOOM = 0.7                            # ... and the camera stands further back out here, so you see more of it

LANDS = {
    # Outside the town gate: open meadow, six roads. The town's wall runs along the x0 edge (web/crossroads.py).
    "crossroads": {
        "size": 60, "edge": 2.6, "base": "grass", "rim": "forest", "tint": DUSK, "start": (6.4, 37.9),
        "paths": [
            (ROAD_W, [(30, 30), (21, 33.5), (11, 37), (3.6, 38.0), (-4, 38.0)]),              # the town gate
            (ROAD_W, [(30, 30), (21, 22), (12, 13), (5.2, 5.2), (-2, -2)]),                   # Celestial Forbidden Lands
            (ROAD_W, [(30, 30), (19, 27), (10, 20), (3.4, 17.0), (-4, 16)]),                  # Frostpeak Mountains
            (ROAD_W, [(30, 30), (31.5, 20), (27, 11), (28.0, 3.4), (28.5, -4)]),              # Thunderfall Valley
            (ROAD_W, [(30, 30), (38, 23), (47, 13), (54.8, 5.2), (62, -2)]),                  # Crimson Gorge
            (ROAD_W, [(30, 30), (40, 31.5), (49, 27.5), (56.6, 29.0), (64, 29.5)]),           # the Ancient Battlefield
            (ROAD_W, [(30, 30), (33, 39), (41.5, 47), (40.0, 56.6), (40.0, 64)]),             # Moon Forest
            (ROAD_W, [(21, 33.5), (19.5, 41), (16.5, 49), (16.0, 56.6), (16.0, 64)]),         # the Ironvein Quarry
        ],
        "patches": [(30, 30, 3.4, "stone"), (30, 30, 5.2, "dirt"),
                    (44, 44, 9, "forest"), (52, 50, 8, "forest"), (33, 53, 6, "forest")],   # the forest's edge creeps in
        "gates": {"road_moon_forest": {"at": (40.0, 56.6), "side": "y1"},
                  "road_quarry": {"at": (16.0, 56.6), "side": "y1"}},
    },
    # The Ironvein Quarry (docs/world.md): a worked pit off the Crossroads, close to town. Bare earth and broken
    # stone under a late-afternoon light; rock walls stand round it (web/quarry.py), seams glint in them.
    "ironvein_quarry": {
        "size": 40, "edge": 2.6, "base": "dirt", "rim": "forest", "tint": (0.92, 0.80, 0.68), "start": (16.0, 6.0),
        "paths": [
            (ROAD_W, [(16.0, -4), (16.0, 3.4), (17.5, 10), (20, 16), (20, 22)]),
        ],
        "patches": [(16, 2, 9, "grass"), (5, 6, 6, "grass"), (31, 5, 6, "grass"), (20, 23, 5.0, "stone"),
                    (6, 30, 5, "grass"), (35, 33, 4.5, "grass")],
        "gates": {"north": {"at": (16.0, 3.4), "side": "y0"}},
    },
    # Moon Forest, in three parts. Forest Edge: the meadow gives way to the trees' floor; the path winds south.
    "forest_edge": {
        "size": 70, "edge": 3.0, "base": "forest", "rim": "forest", "tint": (0.74, 0.82, 0.86), "start": (40.0, 6.5),
        "paths": [
            (ROAD_W, [(40.0, -4), (40.0, 3.8), (42, 13), (33, 23), (36, 34), (43, 45), (36, 57), (38.0, 66.2),
                      (38.0, 74)]),                                                          # the way through
            (PATH_W, [(36, 34), (47, 31), (56, 24), (60, 15)]),                                # east, to a far clearing
            (PATH_W, [(33, 23), (22, 28), (14, 38), (12, 50)]),                                # west, to the hollow
        ],
        "patches": [(40, 3, 15, "grass"), (28, 8, 9, "grass"), (52, 9, 8, "grass"),          # the last of the meadow
                    (36, 34, 5.5, "grass"), (60, 15, 5, "grass"), (12, 50, 6, "grass"), (52, 52, 4.5, "grass")],
        "gates": {"north": {"at": (40.0, 3.8), "side": "y0"}, "south": {"at": (38.0, 66.2), "side": "y1"}},
        "secret": [(60.5, 13.5), (11.0, 52.0), (52.0, 52.0), (20.0, 12.0)],
    },
    # Deep Woods: darker, the path forks and doubles back; the way on is east.
    "deep_woods": {
        "size": 70, "edge": 3.0, "base": "forest", "rim": "forest", "tint": (0.62, 0.70, 0.80), "start": (38.0, 6.5),
        "paths": [
            (ROAD_W, [(38.0, -4), (38.0, 3.8), (34, 15), (42, 27), (35, 39), (46, 49), (58, 46), (66.2, 44.0),
                      (74, 44.0)]),
            (PATH_W, [(42, 27), (54, 24), (60, 13)]),
            (PATH_W, [(35, 39), (23, 43), (13, 55)]),
            (PATH_W, [(34, 15), (21, 14), (12, 22)]),
        ],
        "patches": [(60, 13, 4.5, "grass"), (13, 55, 5.5, "grass"), (12, 22, 4, "grass"), (46, 49, 4, "grass"),
                    (26, 60, 3.5, "grass")],
        "gates": {"north": {"at": (38.0, 3.8), "side": "y0"}, "east": {"at": (66.2, 44.0), "side": "x1"}},
        "secret": [(61.0, 11.5), (12.0, 57.0), (11.0, 21.0), (26.0, 60.0)],
    },
    # Shrine Grove: the heart of the forest. A wide paved clearing waits for the shrine.
    "shrine_grove": {
        "size": 70, "edge": 3.0, "base": "forest", "rim": "forest", "tint": (0.66, 0.74, 0.88), "start": (6.5, 44.0),
        "paths": [
            (ROAD_W, [(-4, 44.0), (3.8, 44.0), (15, 42), (26, 37), (35, 35)]),
            (PATH_W, [(35, 35), (46, 26), (55, 15)]),
            (PATH_W, [(35, 35), (43, 49), (52, 60)]),
            (PATH_W, [(35, 35), (27, 22), (18, 12)]),
        ],
        "patches": [(35, 35, 9, "grass"), (35, 35, 5.2, "stone"), (55, 15, 5, "grass"), (52, 60, 5, "grass"),
                    (18, 12, 4.5, "grass"), (14, 58, 4, "grass")],
        "gates": {"west": {"at": (3.8, 44.0), "side": "x0"}},
        "secret": [(56.0, 13.5), (53.0, 61.5), (17.0, 10.5), (14.0, 58.0)],
    },
}

# side → (the way out of the land, the direction along the edge), in tiles
SIDES = {"x0": ((-1, 0), (0, 1)), "x1": ((1, 0), (0, 1)), "y0": ((0, -1), (1, 0)), "y1": ((0, 1), (1, 0))}
OPPOSITE = {"x0": "x1", "x1": "x0", "y0": "y1", "y1": "y0"}


def size(key):
    return LANDS[key]["size"]


def area(key):
    n, e = LANDS[key]["size"], LANDS[key]["edge"]
    return [(e, e), (n - e, e), (n - e, n - e), (e, n - e)]


def walkable(key, x, y):
    n, e = LANDS[key]["size"], LANDS[key]["edge"]
    return e < x < n - e and e < y < n - e


def _curve(pts, step=1.0):
    """A smooth curve through the waypoints (Catmull-Rom), as short straight pieces about `step` tiles long."""
    if len(pts) < 3:
        return list(pts)
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = [pts[0]]
    for i in range(1, len(p) - 2):
        a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
        k = max(2, int(math.dist(b, c) / step))
        for j in range(1, k + 1):
            t = j / k
            out.append(tuple(0.5 * ((2 * b[m]) + (-a[m] + c[m]) * t + (2 * a[m] - 5 * b[m] + 4 * c[m] - d[m]) * t * t
                                    + (-a[m] + 3 * b[m] - 3 * c[m] + d[m]) * t ** 3) for m in (0, 1)))
    return out


_SEGS = {}


def segments(key):
    """The land's paths as straight pieces: [((ax, ay), (bx, by), width)]."""
    if key not in _SEGS:
        out = []
        for w, pts in LANDS[key]["paths"]:
            c = _curve(pts)
            out += [(c[i], c[i + 1], w) for i in range(len(c) - 1)]
        _SEGS[key] = out
    return _SEGS[key]


def off_path(key, x, y, room=0.3):
    """Whether (x, y) is clear of every path (a herb doesn't grow in the road)."""
    for (ax, ay), (bx, by), w in segments(key):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ((dx * dx + dy * dy) or 1)))
        if math.dist((x, y), (ax + t * dx, ay + t * dy)) < w / 2 + room:
            return False
    return True


def ground_at(key, x, y):
    """The ground under (x, y): the last patch that covers it ("grass", "forest", "dirt", "stone"), else the land's base."""
    spec = LANDS[key]
    tex = spec["base"]
    for cx, cy, r, t in spec.get("patches", ()):
        if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
            tex = t
    return tex


def path_dist(key, x, y):
    """How far (x, y) is from the edge of the nearest path (tiles; 0 on it)."""
    best = 1e9
    for (ax, ay), (bx, by), w in segments(key):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ((dx * dx + dy * dy) or 1)))
        best = min(best, math.dist((x, y), (ax + t * dx, ay + t * dy)) - w / 2)
    return max(0.0, best)


_GROUND = {}


def ground(key):
    """What the page needs to draw the land's ground: its chunks (scripts/make_land.py wrote the list)."""
    if key not in _GROUND:
        with open(os.path.join(DIR, key, "chunks.json")) as f:
            m = json.load(f)
        _GROUND[key] = {"base": f"{ART}/{key}/", "preview": f"{ART}/{key}/preview.webp", "chunk": m["chunk"],
                        "f": m["f"], "have": m["have"], "v": m.get("v", 1)}
    return _GROUND[key]


def preview(key):
    return f"{ART}/{key}/preview.webp"
