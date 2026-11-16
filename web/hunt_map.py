"""
The walkable hunting-ground map (docs/hunting.md "The map"): its shape, where a beast stands, and the checks on
where a player says they are.

The map only decides WHEN a fight starts: walk up to the beast and it begins. WHICH beast it is, how strong and
what it pays stay exactly as before (web/hunt_play.py rolls it the same way, from the same random numbers).

Coordinates are tiles on a 2:1 isometric diamond SIZE x SIZE: x runs from the top corner to the right one, y from
the top corner to the left one. The outer EDGE tiles are forest (not walkable), and each location's map can block
more (its painted rocks, trees, water). The page (web/static/huntmap.js) gets the same numbers (`page_data`), so
it stops where the server would.
"""
import math

SIZE = 24
EDGE = 2.2
START = (SIZE / 2, SIZE - EDGE - 2.2)       # where you come in when the map has no START of its own

# Painted maps (art/maps/<key>.webp, 3072 x 1536: the diamond's corners on the image's edges). `blocked`: circles
# (x, y, radius) in tiles where something stands that you can't walk through; `edge` replaces EDGE; `start` where
# you come in. Measured on the painting with the tile grid laid over it.
MAPS = {
    "moon_forest": {
        "art": "/art/maps/moon_forest.webp", "edge": 2.4, "start": (19.4, 19.4),
        "blocked": [
            (2.3, 17.6, 2.0),       # the shrine and its lanterns (west)
            (3.4, 10.4, 1.3),       # the old tree (north-west)
            (4.3, 4.6, 0.9),        # mossy rocks (north)
            (8.6, 3.0, 1.2),        # boulders (north-east)
            (13.6, 3.6, 0.9),       # the twisted stump
            (16.3, 4.3, 1.2),       # boulders (east)
            (21.6, 13.0, 1.2),      # the big rock (south-east)
            (4.6, 22.4, 1.4),       # rocks by the stream (south-west)
            (14.2, 14.8, 1.5),      # the pond (the stream below it is shallow: stepping stones)
        ],
    },
}


def plan(key):
    """The map of this location, or None (a plain ground drawn by the page)."""
    return MAPS.get(key)


def page_data(key):
    m = MAPS.get(key) or {}
    return {"ground": m.get("art"), "edge": m.get("edge", EDGE), "blocked": [list(c) for c in m.get("blocked", [])]}
SPEED = 3.4                                 # the page's fastest walk, in tiles a second (150 screen px/s, straight up)
SLACK = 1.6                                 # leeway for network jitter on that speed ...
JUMP = 1.0                                  # ... plus this many tiles
REACH = 1.6                                 # how close (tiles) you must be to the beast to start the fight
SPAWN_GAP = 7.0                             # a new beast appears at least this far from you


def walkable(x, y, m=None):
    """Whether you can stand here on map `m` (a MAPS entry; None: the plain map)."""
    edge = (m or {}).get("edge", EDGE)
    if not (edge < x < SIZE - edge and edge < y < SIZE - edge):
        return False
    return all(math.dist((x, y), (cx, cy)) > r for cx, cy, r in (m or {}).get("blocked", ()))


def start(m=None):
    return tuple((m or {}).get("start", START))


def spot(rng, near, m=None):
    """Somewhere for the next beast to stand: walkable, with room around it, not on top of you."""
    edge = (m or {}).get("edge", EDGE)
    for _ in range(80):
        x = edge + 2 + rng.random() * (SIZE - 2 * edge - 4)
        y = edge + 2 + rng.random() * (SIZE - 2 * edge - 4)
        room = all(walkable(x + dx, y + dy, m) for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)))
        if room and math.dist((x, y), near) >= SPAWN_GAP:
            return round(x, 2), round(y, 2)
    return round(SIZE / 2, 2), round(edge + 3, 2)


def moved(prev, x, y, now, m=None):
    """The position a player reports, if it could be true (on the map, and no faster than walking since the last
    one); else None. `prev` is (x, y, time)."""
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)) or not walkable(x, y, m):
        return None
    px, py, pt = prev
    if math.dist((x, y), (px, py)) > SPEED * SLACK * max(0.0, now - pt) + JUMP:
        return None
    return (round(x, 3), round(y, 3), now)


def close_enough(pos, beast):
    return math.dist(pos[:2], (beast["x"], beast["y"])) <= REACH
