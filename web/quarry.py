"""
The Ironvein Quarry (docs/world.md "The Ironvein Quarry"): a small safe land off the Crossroads where forging
materials are mined. Its ground is one of the open lands (web/land.py LANDS["ironvein_quarry"]); this module says
what stands on it: the rock walls round the pit, the keeper's hut, a few loose rocks (web/env.py pieces), the keeper
himself, and the spots along the walls where a seam may open (SPOTS). The mining itself is web/mine_play.py.
"""
import math

from . import env, land

KEY = "ironvein_quarry"
NAME = "Ironvein Quarry"
SIZE = land.size(KEY)

# (asset, x, y, scale, flip): the walls stand round the worked floor, the hut by the way in
PLACED = [
    ("cliff_01", 9.0, 16.0, 1.0, False), ("cliff_02", 6.5, 22.5, 1.0, True), ("cliff_01", 8.5, 29.5, 0.9, True),
    ("cliff_02", 14.5, 34.0, 1.0, False), ("cliff_01", 22.0, 35.5, 1.0, False), ("cliff_02", 29.0, 33.0, 1.0, True),
    ("cliff_01", 33.5, 26.5, 0.95, True), ("cliff_02", 33.0, 19.0, 1.0, False), ("cliff_01", 29.5, 12.5, 0.9, False),
    ("quarry_hut_01", 22.5, 7.5, 0.9, False),
    ("boulder_01", 12.4, 9.4, 0.8, False),                       # the keeper leans on his pick behind it
    ("stones_cluster_01", 25.0, 15.5, 0.8, True), ("rock_small_01", 14.5, 20.0, 1.0, False),
    ("rock_small_01", 26.5, 27.0, 1.1, True), ("mossy_rock_01", 6.0, 8.5, 1.0, False),
]
# where a seam may open: at the foot of the walls, facing the floor
SPOTS = [(12.2, 18.0), (10.4, 24.0), (12.2, 28.6), (17.0, 30.6), (22.4, 31.2), (27.0, 29.4), (29.6, 24.6),
         (29.2, 20.6), (26.2, 16.4), (14.6, 14.2), (19.0, 27.4), (24.4, 22.0)]
KEEPER = {"key": "quarry_keeper", "name": "Old Shen", "title": "Quarry Keeper", "x": 12.0, "y": 9.0,
          "src": "/art/gather/keeper.webp", "h": 150, "prop": False, "flip": False, "go": []}
TONE = [0.92, 0.82, 0.72]


def _each():
    cat = env.catalog()
    for name, x, y, s, flip in PLACED:
        if name in cat:
            yield name, x, y, s, flip, env.ASSETS[name], cat[name]


def blocked():
    """What blocks the way: circles (x, y, radius) in tiles. A wall blocks a row of them along its length."""
    out = []
    for name, x, y, s, flip, a, c in _each():
        r = a.get("block", 0) * s
        if not r:
            continue
        if name.startswith("cliff"):
            for d in (-2.0, 0.0, 2.0):                        # a wall lies along the screen's width: x up, y down
                out.append((round(x + d * s, 2), round(y - d * s, 2), round(r, 2)))
        else:
            out.append((x, y, round(r, 2)))
    return out


_BLOCKED = None


def walkable(x, y):
    global _BLOCKED
    if _BLOCKED is None:
        _BLOCKED = blocked()
    return land.walkable(KEY, x, y) and all(math.dist((x, y), (cx, cy)) > r for cx, cy, r in _BLOCKED)


def pieces():
    """The pieces for the page (web/static/town.js): each picture's rectangle on the ground picture (world px, its
    left edge at 0), where it stands, its shadow. As web/env.pieces, with the land's own width."""
    out = []
    for name, x, y, s, flip, a, c in _each():
        k = (a["h"] / c["h"] if "h" in a else a["w"] / c["w"]) * s
        w, h = c["w"] * k, c["h"] * k
        foot = c["foot"] if not name.startswith("cliff") else [c["w"] / 2, c["foot"][1]]   # a wall stands on its middle
        fx = (c["w"] - foot[0]) if flip else foot[0]
        sx, sy = SIZE * 64 + (x - y) * 64, (x + y) * 32
        out.append({"src": "/" + env.path(name), "env": True, "lit": False, "flip": flip, "at": [x, y],
                    "rect": [round(sx - fx * k, 1), round(sy - foot[1] * k, 1), round(w, 1), round(h, 1)],
                    "shadow": {"rx": round(w * 0.4, 1), "ry": round(w * 0.1, 1)}})
    return out


def npcs(left=None):
    line = ("Old Shen leans on his pick. “Dig where the rock glints, young one. Iron for blades, coal for the "
            "forge’s fire, and now and then jade. The rock gives each of us two dozen seams a day and no more.”")
    if left is not None:
        line += (f" He squints at the walls. “You have {left} left today.”" if left
                 else " “You’ve had today’s. Come back tomorrow.”")
    return [dict(KEEPER, line=line)]
