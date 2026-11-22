"""
The Crossroads (docs/world.md): the walkable land just outside the town gate, where the roads to the hunting grounds
begin. You walk out of Azure Cloud Town's gate onto it, and down a road to a hunting ground; the World Map scroll is
only a map now, not a way to travel.

It is built like the town (web/town.py) and walked by the same page (web/static/town.js): the ground painted in code
from the town's textures (scripts/make_town_ground.py `crossroads`), and on it the town's own pieces: the town wall and
gate along the top-left edge (seen from outside), pines, bushes, boulders and blossom trees around the rim, lanterns
by the junction. Coordinates are tiles on the same 2:1 diamond, SIZE x SIZE.

The ways out (EXITS, talked to like the townsfolk: walk up, press E): the gate back into town, and a road for each
hunting ground at the edge of the map in its direction on the World Map. A road is
  open     you may set out: "Enter …" starts the Solo Hunt there (/crossroads/go/<key>, web/hunt_routes.py),
  waiting  your realm is right, but you are injured or resting: mist over the road, and how long is left,
  locked   your realm is too low: a seal of runes across the road, and the realm it needs.
The server checks the realm, the injury and the rest again when you set out, whatever the page showed. Walking about
changes nothing in the game, so (like the town) the server doesn't follow where you walk.
"""
import math
import random

import hunting

from . import town

NAME = "The Crossroads"
SIZE = 32
ART = "/art/maps/crossroads.webp"
SCALE = town.SCALE                    # the same pieces as the town, drawn the same size against you
REACH = town.REACH
INSET = town.INSET
CENTER = (16.0, 16.0)                 # where the roads meet
START = (6.4, 19.9)                   # on the road, a few steps out of the gate

AREA = [(2.6, 2.8), (29.2, 2.8), (29.2, 29.2), (2.6, 29.2)]
BLOCKED = []

# The town wall along the top-left edge, its outer face toward you; the gate's doors at y DOOR.
WALL_X = 2.1
DOOR = 20.0
GATE_Y0 = DOOR + 3.84 - town.GATE_LEN          # the doors are 3.84 tiles from the gate's south end (as in town)
WALL_FROM, WALL_TO = 11.5, 28.6

# The ways out: the gate into town, and the road to each hunting ground (hunting.LOCATIONS), at the edge of the map in
# its direction on the World Map (north is the top corner): Celestial Forbidden Lands up the top corner, Frostpeak
# north-west, Thunderfall north-east, Crimson Gorge east, the Ancient Battlefield south-east, Moon Forest south.
GATE = {"key": "town_gate", "kind": "door", "name": "Azure Cloud Town", "title": "The town gate",
        "x": 3.6, "y": 21.0, "glow": (3.6, 21.0),
        "line": "Lanterns burn on the gatehouse. Through the doors lie the forge, the alchemy hall and a safe bed.",
        "go": [["Enter the town", "/town"]]}
ROADS = {
    "celestial_forbidden_lands": (3.8, 3.8),
    "frostpeak_mountains": (3.4, 8.4),
    "thunderfall_valley": (15.5, 3.4),
    "crimson_gorge": (28.4, 3.8),
    "ancient_battlefield": (28.6, 15.5),
    "moon_forest": (21.5, 28.6),
}
ROAD_W = 2.2                          # a road's width (tiles)


ROAD_ON = 7.0                         # a road carries on this far past its end, off the walkable ground and the map


def beyond(end):
    """Where a road ending at `end` leads on to: straight on from the junction, past the map's edge."""
    dx, dy = end[0] - CENTER[0], end[1] - CENTER[1]
    m = math.hypot(dx, dy)
    return (end[0] + dx / m * ROAD_ON, end[1] + dy / m * ROAD_ON)


def roads():
    """The dirt roads: from the junction to the gate, and on past each road's end off the map (segments, tiles)."""
    out = [(CENTER, (GATE["x"], GATE["y"]))]
    out += [(CENTER, beyond(end)) for end in ROADS.values()]
    return out


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def road_dist(p):
    return min(seg_dist(p, a, b) for a, b in roads())


def nearest_on_road(p):
    """The nearest point on any road to p."""
    best, at = 1e9, None
    for (ax, ay), (bx, by) in roads():
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
        q = (ax + t * dx, ay + t * dy)
        if math.dist(p, q) < best:
            best, at = math.dist(p, q), q
    return best, at


IN_FRONT = 2.8                        # a tree between the camera and a road stands this much further off (its crown)


# ── the pieces ──────────────────────────────────────────────────────────────────────────────────────────────────

TREES = [("pine", 1.1, 3), ("pine", 1.3, 3), ("bush", 1.0, 2), ("blossom", 1.3, 1), ("boulders", 1.4, 1)]


def _forest():
    """The trees, bushes and rocks: a thick ring round the rim (beyond the walkable ground and just inside it) and a
    few about the fields, never on a road, by a road's end or the wall. Placed once, the same every time."""
    rng = random.Random(11)
    pool = [kind for kind in TREES for _ in range(kind[2])]
    out, taken = [], []
    for gy in range(0, SIZE * 2):
        for gx in range(0, SIZE * 2):
            x, y = gx / 2 + rng.uniform(-0.2, 0.2), gy / 2 + rng.uniform(-0.2, 0.2)
            rim = min(x, y, SIZE - x, SIZE - y)
            if rim < 0.6:
                continue
            want = 0.9 if rim < 2.6 else 0.22 if rim < 4.2 else 0.012
            if rng.random() > want:
                continue
            d, q = nearest_on_road((x, y))
            if d < ROAD_W / 2 + (IN_FRONT if x + y > q[0] + q[1] else 1.1):   # nearer the camera: it would hide you
                continue
            if any(math.dist((x, y), e) < 2.6 for e in ROADS.values()):
                continue
            if any(seg_dist((x, y), e, beyond(e)) < ROAD_W / 2 + 1.8 for e in ROADS.values()):
                continue                                                # a clear view down the road off the map
            if x < 4.2 and WALL_FROM - 1.4 < y < WALL_TO + 0.6:            # the wall and the ground before it
                continue
            if math.dist((x, y), START) < 2.5 or math.dist((x, y), (GATE["x"], GATE["y"])) < 3:
                continue
            img, a, _ = rng.choice(pool)
            if any(math.dist((x, y), t) < (a + ta) * 0.62 for t, ta in taken):
                continue
            taken.append(((x, y), a))
            out.append(town._b(f"{img}_{len(out)}", img, round(x - a / 2, 2), round(y - a / 2, 2), a,
                               mirror=rng.random() < 0.5))
    return out


def _lanterns():
    """Lantern posts by the junction, at the roadside."""
    out = []
    for i, (dx, dy) in enumerate(((-1.9, -1.9), (1.9, -1.9), (-1.9, 1.9), (1.9, 1.9), (0, -2.6), (0, 2.6), (-2.6, 0),
                                  (2.6, 0))):
        x, y = CENTER[0] + dx, CENTER[1] + dy
        if ROAD_W / 2 + 0.25 < road_dist((x, y)) < ROAD_W / 2 + 1.0:
            out.append(town._b(f"lantern_{i}", "lantern", x - 0.2, y - 0.2, 0.4))
    return out


BUILDINGS = [
    *town._wall_line("wall_n", WALL_FROM, GATE_Y0, WALL_X, along_x=False),
    town._b("gate", "gate", WALL_X, GATE_Y0, town.WALL_T, town.GATE_LEN),
    *town._wall_line("wall_s", GATE_Y0 + town.GATE_LEN, WALL_TO, WALL_X, along_x=False),
    *_lanterns(),
    *_forest(),
]
PROPS = []

# The ground (scripts/make_town_ground.py `crossroads` paints art/maps/crossroads.webp from these): grass, the forest
# floor beyond the rim, the dirt roads (segments, ROAD_W wide).
GROUND = {"stone": [], "dirt": [], "roads": [(a, b, ROAD_W) for a, b in roads()], "walls": (2.4, 2.4, 29.6, 29.6)}


def walkable(x, y):
    return (0 < x < SIZE and 0 < y < SIZE and town.inside(x, y, AREA)
            and all(math.dist((x, y), (cx, cy)) > r for cx, cy, r in BLOCKED)
            and not any(town.in_footprint(x, y, b) for b in BUILDINGS if not b.get("pass")))


# ── the page ────────────────────────────────────────────────────────────────────────────────────────────────────

def road_exit(loc, player, blocked=None):
    """A hunting ground's road as a way out, for this player: open, waiting (injured or resting) or locked."""
    x, y = ROADS[loc["key"]]
    why = hunting.eligible(player, loc)
    state = "locked" if why else "waiting" if blocked else "open"
    need = hunting.requirement(loc)
    if state == "locked":
        line = f"A seal of golden runes bars the road. {loc['name']} needs {need} or higher."
        go = []
    elif state == "waiting":
        line = f"Mist hangs over the road to {loc['name']}. You can't set out yet: {blocked}."
        go = []
    else:
        line = (f"{loc['text']} Entering starts the hunt, and the 30-minute explore rest.")
        go = [[f"Enter {loc['name']}", f"/crossroads/go/{loc['key']}", "post"]]
    return {"key": f"road_{loc['key']}", "kind": "road", "state": state, "name": loc["name"],
            "title": "Sealed: needs " + need if state == "locked" else
                     ("Resting" if not blocked.startswith("injured") else "Injured") if state == "waiting" else
                     "Beasts of " + hunting.home_realms(loc),
            "x": x, "y": y, "glow": (x, y), "line": line, "go": go, "place": loc["key"]}


def exits(player, blocked=None):
    return [GATE] + [road_exit(loc, player, blocked) for loc in hunting.LOCATIONS]


def page_data(sheet, player, blocked=None, near=None):
    """The page's data, in the town page's shape (web/static/town.js walks both). You come in by the gate, or at the
    end of the road you came back along (`near`: an exit's key)."""
    ex = [{k: e[k] for k in ("key", "name", "title", "x", "y", "line", "go")} |
          {"exit": True, "kind": e["kind"], "state": e.get("state", "open"), "glow": list(e["glow"])}
          for e in exits(player, blocked)]
    return {"sheet": sheet, "size": SIZE, "ground": ART, "area": [list(p) for p in AREA], "inset": INSET,
            "blocked": [list(c) for c in BLOCKED], "pieces": town.placed(BUILDINGS, PROPS, SIZE),
            "reach": REACH, "scale": SCALE, "hero": {"x": START[0], "y": START[1]},
            "near": near if any(e["key"] == near for e in ex) else None, "npcs": [], "exits": ex}
