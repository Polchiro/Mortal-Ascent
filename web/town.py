"""
The town hub (docs/town.md): a walkable 2.5D isometric town where the cultivator walks up to the townsfolk, and
each one, after a word, sends you on to a page that already exists (the forge, alchemy, the hunting grounds ...).

The town decides nothing: no fights, rewards or costs happen here, so the server doesn't referee where you walk (the
hunting map does, web/hunt_map.py, because walking up to a beast starts a fight). The page (web/static/town.js) gets
everything below as data and does the walking itself.

Coordinates are tiles on a 2:1 isometric diamond SIZE x SIZE, as on the hunting map: x runs from the top corner to
the right one, y from the top corner to the left one; 128 x 64 px a tile, so the painting (art/maps/town.webp,
4096 x 2048, its diamond's corners on the image's edges) is drawn at full size. You can walk inside AREA (the
courtyard, streets and yards between the buildings, a polygon) except where something stands (BLOCKED circles).
Measured on the painting with the tile grid laid over it (press G on the page).
"""
import json
import math

NAME = "Azure Cloud Town"
SIZE = 32
ART = "/art/maps/town.webp"
START = (21.3, 21.3)                 # just inside the gate, facing in
REACH = 1.5                          # how close (tiles) you must be to someone to talk to them
SCALE = 1.4                          # the town drawn this much bigger against you than the painting is (town.js K)

AREA = [                             # walkable ground, clockwise from the lane to the pond (north)
    (9.0, 8.6), (10.9, 10.6), (17.4, 11.0), (17.6, 6.4), (26.4, 5.6), (27.0, 11.5), (27.2, 16.5),
    (26.6, 21.2), (24.0, 22.4), (23.0, 23.0), (22.0, 23.0), (21.2, 22.4), (20.5, 21.1), (14.3, 20.4),
    (13.4, 23.4), (13.2, 27.8), (11.2, 28.4), (10.2, 25.6), (10.4, 21.6), (11.0, 18.8), (10.4, 13.6),
]
BLOCKED = [                          # (x, y, radius) in tiles
    (16.4, 16.3, 1.0),               # the well
    (23.5, 19.1, 0.9),               # the stone stele
    (25.2, 14.0, 2.2),               # the arena's stone ring
    (19.2, 9.0, 0.45), (20.3, 10.2, 0.45), (23.3, 9.8, 0.45), (24.3, 8.4, 0.45),   # training dummies
    (19.4, 6.6, 0.8), (21.6, 6.0, 0.8),                                              # weapon racks
]

# The townsfolk: where each stands (x, y, the feet), who they are, what they say, and where they send you (label,
# page). No `go`: what they look after isn't open on the website yet, and they say so. `src`: their picture
# (art/portraits/town/<key>.webp, see-through, feet at the bottom middle); without one the page draws a lantern
# glow and their name. `h`: how tall it is drawn, in world px (the cultivator is about 120); `flip`: the picture faces
# left (the page turns everyone toward you). scripts/make_town_npcs.py cuts them out.
NPCS = [
    {"key": "gate", "name": "Gate Warden", "title": "The road out", "x": 23.8, "y": 21.5,
     "src": "/art/portraits/town/gate.webp", "h": 135, "flip": True,
     "line": "The wilds are restless tonight. Beasts prowl the forest, and the herbs out there won't pick themselves.",
     "go": [["Hunt beasts", "/explore"], ["Gather herbs", "/gather"]]},
    {"key": "blacksmith", "name": "Blacksmith Tie", "title": "The forge", "x": 11.9, "y": 17.2,
     "src": "/art/portraits/town/blacksmith.webp", "h": 132,
     "line": "Steel listens to fire and patience. Bring me ore and I'll make you something worth swinging.",
     "go": [["Enter the forge", "/forge"]]},
    {"key": "alchemist", "name": "Herbalist Lan", "title": "Pills and herbs", "x": 11.6, "y": 25.4,
     "src": "/art/portraits/town/alchemist.webp", "h": 122,
     "line": "Every pill begins as a weed someone was wise enough to pick. Shall we refine something?",
     "go": [["Enter the alchemy hall", "/alchemy"]]},
    {"key": "merchant", "name": "Silk Merchant", "title": "Robes and looks", "x": 15.6, "y": 12.0,
     "line": "A cultivator should look the part. New robes, a new face to the world: I have it all.",
     "go": [["Change your look", "/appearance"]]},
    {"key": "elder", "name": "Village Elder", "title": "Your cultivation", "x": 10.2, "y": 9.8,
     "line": "Sit a while, child. Let me see how far your cultivation has come.",
     "go": [["Show my cultivation", "/profile"], ["Check my bag", "/inventory"]]},
    {"key": "master", "name": "Martial Master", "title": "Training", "x": 21.6, "y": 8.0,
     "src": "/art/portraits/town/master.webp", "h": 128,
     "line": "The training yard isn't open to you yet. Train through the bot for now; my doors open soon."},
    {"key": "arena", "name": "Arena Keeper", "title": "Duels", "x": 22.6, "y": 12.6,
     "src": "/art/portraits/town/arena.webp", "h": 134, "flip": True,
     "line": "No duels in the ring tonight. When it opens, cultivators will test each other here."},
    {"key": "stele", "name": "Stone Stele", "title": "The rankings", "x": 22.2, "y": 18.4, "prop": True,
     "line": "The names of the town's strongest are carved here. The carving isn't finished yet."},
]


def inside(x, y, poly=AREA):
    """Point in polygon (even-odd)."""
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def walkable(x, y):
    return 0 < x < SIZE and 0 < y < SIZE and inside(x, y) and \
        all(math.dist((x, y), (cx, cy)) > r for cx, cy, r in BLOCKED)


def page_data(sheet):
    """The page's data (web/static/town.js): the walking sheet, the map and the townsfolk. You come in at the gate
    (the page puts you back in front of whoever you last left town through)."""
    npcs = [{k: n[k] for k in ("key", "name", "title", "x", "y", "line")} |
            {"go": n.get("go", []), "prop": n.get("prop", False), "src": n.get("src"), "h": n.get("h", 128),
             "flip": n.get("flip", False)} for n in NPCS]
    return {"sheet": sheet, "size": SIZE, "ground": ART, "area": [list(p) for p in AREA],
            "blocked": [list(c) for c in BLOCKED], "reach": REACH, "scale": SCALE, "hero": {"x": START[0], "y": START[1]},
            "npcs": npcs}


def page_json(data):
    return json.dumps(data).replace("</", "<\\/")
