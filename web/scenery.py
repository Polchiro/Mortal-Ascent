"""
Still pools and mossy rocks on the open lands (docs/world.md "Herbs"; the pictures are web/env.py pieces cut from
SHOAIB's art, Nov 25 2026). They are scenery and habitat: you walk round them, water herbs (the lotuses, the Jade
Lily) sprout on a pool when one is free, and Silver Moss beside a mossy rock. Nothing else about a herb changes.

PLACED[land] = (asset, x, y, scale, flip), each clear of the paths, the gates and the far clearings
(tests/test_scenery.py checks it).
"""
import math

from . import env, land

PLACED = {
    "crossroads": [("pond_01", 52.0, 17.2, 1.03, True), ("pond_02", 25.9, 47.7, 0.98, True),
                   ("mossy_rock_01", 47.7, 33.6, 0.93, True), ("mossy_rock_01", 13.9, 41.6, 0.92, False)],
    "forest_edge": [("pond_01", 45.9, 59.3, 1.07, False), ("pond_02", 35.4, 45.9, 0.94, True),
                    ("mossy_rock_01", 8.6, 26.5, 0.95, True), ("mossy_rock_01", 29.4, 17.0, 1.03, False)],
    "deep_woods": [("pond_01", 24.2, 8.7, 1.05, True), ("pond_02", 17.2, 31.5, 0.95, True),
                   ("mossy_rock_01", 32.1, 30.6, 1.02, True), ("mossy_rock_01", 13.1, 12.6, 0.92, False)],
    "shrine_grove": [("pond_01", 27.4, 51.6, 1.0, False), ("pond_02", 8.9, 15.6, 0.98, False),
                     ("mossy_rock_01", 60.1, 8.2, 1.07, True), ("mossy_rock_01", 60.1, 49.0, 1.1, False)],
}
WATER_HERBS = {"Heart Lotus", "Heaven Lotus", "Jade Lily"}      # these sprout on a pool when one is free
ROCK_HERBS = {"Silver Moss"}                                     # ... and this beside a mossy rock
ON_POOL = (0.4, 0.4)                  # where on a pool its herb stands (toward you, so it is in reach from the bank)


def _each(place):
    cat = env.catalog()
    for name, x, y, s, flip in PLACED.get(place, ()):
        if name in cat:
            yield name, x, y, s, flip, env.ASSETS[name], cat[name]


def blocked(place):
    return [(x, y, round(a["block"] * s, 2)) for name, x, y, s, flip, a, c in _each(place) if a.get("block")]


def walkable(place, x, y):
    return all(math.dist((x, y), (cx, cy)) > r for cx, cy, r in blocked(place))


def pools(place):
    return [(x, y) for name, x, y, *_ in PLACED.get(place, ()) if name.startswith("pond")]


def rocks(place):
    return [(x, y) for name, x, y, *_ in PLACED.get(place, ()) if name.startswith("mossy_rock")]


def pieces(place):
    """The pieces for the page (web/static/town.js), as web/quarry.pieces: each picture's rectangle on the ground
    picture, where it stands, its shadow (a pool lies flat: none)."""
    size = land.size(place)
    out = []
    for name, x, y, s, flip, a, c in _each(place):
        k = (a["h"] / c["h"] if "h" in a else a["w"] / c["w"]) * s
        w, h = c["w"] * k, c["h"] * k
        foot = [c["w"] / 2, c["h"] * 0.62] if a.get("flat") else c["foot"]       # a pool is placed by its middle
        fx = (c["w"] - foot[0]) if flip else foot[0]
        sx, sy = size * 64 + (x - y) * 64, (x + y) * 32
        p = {"src": "/" + env.path(name), "env": True, "lit": False, "flip": flip, "at": [x, y],
             "rect": [round(sx - fx * k, 1), round(sy - foot[1] * k, 1), round(w, 1), round(h, 1)]}
        if a.get("flat"):
            p["z"] = x + y - 3                       # it lies on the ground: drawn before whoever stands near it
        else:
            p["shadow"] = {"rx": round(w * 0.4, 1), "ry": round(w * 0.1, 1)}
        out.append(p)
    return out
