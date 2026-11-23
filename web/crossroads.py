"""
The Crossroads (docs/world.md): the open land just outside the town gate, where the roads to the hunting grounds
begin. You walk out of Azure Cloud Town's gate onto it, and down a road to a hunting ground.

It is one of the open lands (web/land.py LANDS["crossroads"]: a wide meadow, six roads winding out from a paved
junction), walked by the same page as the town (web/static/town.js). For now it is bare ground: the only things
standing on it are the town's own wall and gate along the x0 edge, seen from outside. Trees, rocks and the rest are
placed later, piece by piece.

The ways out (EXITS): the gate back into town and the Moon Forest road are walked through (web/overworld.py
ENTRANCES). A road whose land isn't built yet is
  closed   "not open yet": nothing starts there (the old menu hunt no longer does),
  locked   your realm is too low: a seal of runes across the road, and the realm it needs.
"""
import math

import hunting

from . import land, town

NAME = "The Crossroads"
KEY = "crossroads"
SIZE = land.size(KEY)
ART = land.preview(KEY)
SCALE = town.SCALE                    # the town's wall and gate stand here: drawn the same size against you
REACH = town.REACH
INSET = town.INSET
CENTER = (30.0, 30.0)                 # where the roads meet
START = land.LANDS[KEY]["start"]      # on the road, a few steps out of the gate

AREA = land.area(KEY)
BLOCKED = []

# The town wall along the x0 edge, its outer face toward you; the gate's doors at y DOOR.
WALL_X = 2.1
DOOR = 37.0
GATE_Y0 = DOOR + 3.84 - town.GATE_LEN          # the doors are 3.84 tiles from the gate's south end (as in town)
WALL_FROM, WALL_TO = 22.0, 52.0

# The ways out: the gate into town, and the road to each hunting ground (hunting.LOCATIONS), at the edge of the land
# in its direction on the World Map (north is the top corner). Each is the end of its road in land.LANDS.
GATE = {"key": "town_gate", "kind": "door", "name": "Azure Cloud Town", "title": "The town gate",
        "x": 3.6, "y": 38.0, "glow": (3.6, 38.0),
        "line": "Lanterns burn on the gatehouse. Through the doors lie the forge, the alchemy hall and a safe bed.",
        "go": [["Enter the town", "/town"]]}
ROADS = {
    "celestial_forbidden_lands": (5.2, 5.2),
    "frostpeak_mountains": (3.4, 17.0),
    "thunderfall_valley": (28.0, 3.4),
    "crimson_gorge": (54.8, 5.2),
    "ancient_battlefield": (56.6, 29.0),
    "moon_forest": (40.0, 56.6),
}
ROAD_W = land.ROAD_W
OPEN = {"moon_forest"}                # the roads whose land is built: walked through (web/overworld.py ENTRANCES)


def road_dist(p):
    """How far p is from the middle of the nearest road (tiles)."""
    best = 1e9
    for (ax, ay), (bx, by), _w in land.segments(KEY):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ((dx * dx + dy * dy) or 1)))
        best = min(best, math.dist(p, (ax + t * dx, ay + t * dy)))
    return best


BUILDINGS = [
    *town._wall_line("wall_n", WALL_FROM, GATE_Y0, WALL_X, along_x=False),
    town._b("gate", "gate", WALL_X, GATE_Y0, town.WALL_T, town.GATE_LEN),
    *town._wall_line("wall_s", GATE_Y0 + town.GATE_LEN, WALL_TO, WALL_X, along_x=False),
]
PROPS = []


def walkable(x, y):
    return (land.walkable(KEY, x, y)
            and not any(town.in_footprint(x, y, b) for b in BUILDINGS if not b.get("pass")))


ZOOM = land.ZOOM


# ── the page ────────────────────────────────────────────────────────────────────────────────────────────────────

def road_exit(loc, player, blocked=None):
    """A hunting ground's road as a way out, for this player: open, waiting (injured or resting) or locked."""
    x, y = ROADS[loc["key"]]
    why = hunting.eligible(player, loc)
    state = "locked" if why else "open" if loc["key"] in OPEN else "closed"
    need = hunting.requirement(loc)
    go = []
    if state == "locked":
        line = f"A seal of golden runes bars the road. {loc['name']} needs {need} or higher."
    elif state == "closed":
        line = (f"Mist lies thick over the road to {loc['name']}. The way is not open yet: "
                "its land is still being charted.")
    else:
        line = loc["text"]
    return {"key": f"road_{loc['key']}", "kind": "road", "state": state, "name": loc["name"],
            "title": "Sealed: needs " + need if state == "locked" else "Not open yet" if state == "closed" else
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
    return {"sheet": sheet, "size": SIZE, "ground": land.ground(KEY), "zoom": ZOOM, "area": [list(p) for p in AREA], "inset": INSET,
            "blocked": [list(c) for c in BLOCKED], "pieces": town.placed(BUILDINGS, PROPS, SIZE),
            "reach": REACH, "scale": SCALE, "hero": {"x": START[0], "y": START[1]},
            "near": near if any(e["key"] == near for e in ex) else None, "npcs": [], "exits": ex}
