"""
The walkable hunting-ground map (docs/hunting.md "The map"): its shape, where a beast stands, and the checks on
where a player says they are.

The map only decides WHEN a fight starts: walk up to the beast and it begins. WHICH beast it is, how strong and
what it pays stay exactly as before (web/hunt_play.py rolls it the same way, from the same random numbers).

Coordinates are tiles on a 2:1 isometric diamond SIZE x SIZE; the outer EDGE tiles are forest (not walkable).
The page (web/static/huntmap.js) uses the same numbers.
"""
import math

SIZE = 24
EDGE = 2.2
START = (SIZE / 2, SIZE - EDGE - 2.2)       # where you come in: the south edge, middle
SPEED = 3.4                                 # the page's fastest walk, in tiles a second (150 screen px/s, straight up)
SLACK = 1.6                                 # leeway for network jitter on that speed ...
JUMP = 1.0                                  # ... plus this many tiles
REACH = 1.6                                 # how close (tiles) you must be to the beast to start the fight
SPAWN_GAP = 7.0                             # a new beast appears at least this far from you


def walkable(x, y):
    return EDGE < x < SIZE - EDGE and EDGE < y < SIZE - EDGE


def clamp(v):
    return max(EDGE + 0.01, min(SIZE - EDGE - 0.01, v))


def spot(rng, near):
    """Somewhere for the next beast to stand: inside the forest, not on top of you."""
    for _ in range(60):
        x = EDGE + 2 + rng.random() * (SIZE - 2 * EDGE - 4)
        y = EDGE + 2 + rng.random() * (SIZE - 2 * EDGE - 4)
        if math.dist((x, y), near) >= SPAWN_GAP:
            return round(x, 2), round(y, 2)
    return round(SIZE / 2, 2), round(EDGE + 3, 2)


def moved(prev, x, y, now):
    """The position a player reports, if it could be true (on the map, and no faster than walking since the last
    one); else None. `prev` is (x, y, time)."""
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)) or not walkable(x, y):
        return None
    px, py, pt = prev
    if math.dist((x, y), (px, py)) > SPEED * SLACK * max(0.0, now - pt) + JUMP:
        return None
    return (round(x, 3), round(y, 3), now)


def close_enough(pos, beast):
    return math.dist(pos[:2], (beast["x"], beast["y"])) <= REACH
