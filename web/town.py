"""
The town hub (docs/town.md): a walkable 2.5D isometric town where the cultivator walks up to the townsfolk, and
each one, after a word, sends you on to a page that already exists (the forge, alchemy, the hunting grounds ...).

The town decides nothing: no fights, rewards or costs happen here, so the server doesn't referee where you walk (the
hunting map does, web/hunt_map.py, because walking up to a beast starts a fight). The page (web/static/town.js) gets
everything below as data and does the walking itself.

Coordinates are tiles on a 2:1 isometric diamond SIZE x SIZE, as on the hunting map: x runs from the top corner to
the right one, y from the top corner to the left one; 128 x 64 px a tile (the world's pixels). The town is built from
pieces: the ground (art/maps/town.webp, 4096 x 2048, its diamond's corners on the image's edges: the plaza, paths,
pond and the walls and gate along the south edge, painted in), and on it each building and prop as its own picture
(art/maps/town/, cut by scripts/make_town_kit.py), so each is as sharp as it was drawn. The page draws them in depth
order with you and the townsfolk, so you walk behind a building when you are behind it.

You can walk inside AREA (a polygon: the town inside its walls) except on a building's footprint, a prop or BLOCKED
(circles: the pond). Measured on the ground with the tile grid laid over it (press G on the page).
"""
import json
import math
import os

NAME = "Azure Cloud Town"
SIZE = 32
ART = "/art/maps/town.webp"
KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "maps", "town", "kit.json")
START = (26.0, 16.3)                 # on the road, just inside the gate
REACH = 1.5                          # how close (tiles) you must be to someone to talk to them
SCALE = 1.4                          # the town drawn this much bigger against you than the ground is (town.js K)
INSET = 0.2                          # you can step this far onto a footprint's edge (its paved base)

AREA = [(3.05, 3.05), (28.95, 3.05), (28.95, 28.95), (3.05, 28.95)]   # inside the town walls
BLOCKED = []                         # (x, y, radius) in tiles: anything round that blocks the way


def _b(key, img, x0, y0, a, b=None, mirror=False):
    return {"key": key, "img": img, "x0": x0, "y0": y0, "a": a, "b": a if b is None else b, "mirror": mirror}


def _wall_line(key, start, end, at, along_x):
    """A straight wall from `start` to `end` (tiles) along one side: a one-tile slice per tile (art/maps/town/wall_s,
    a lantern every fourth: wall_l), 0.6 tiles thick, its face on the footprint's far side. The last slice tucks under
    the tower or gate at its end."""
    out = []
    for i in range(math.ceil(end - start - 0.05)):
        img = "wall_l" if i % 4 == 2 else "wall_s"
        p = start + i
        out.append(_b(f"{key}{i}", img, p, at, 1.0, 0.6, mirror=True) if along_x else
                   _b(f"{key}{i}", img, at, p, 0.6, 1.0))
    return out


# Buildings, walls, trees and props: `img` the picture (art/maps/town/<img>.webp, or <img>_m mirrored), its footprint
# x0..x0+a, y0..y0+b in tiles. A picture's door (or face) looks to the bottom-right (+x); `mirror` turns it to the
# bottom-left (+y), swapping which side is long. The picture's base corners are fitted onto the footprint's.
BUILDINGS = [
    # the walls, meeting at the corners; the gate in the south-east wall
    *_wall_line("wall_nw", 2.6, 29.6, 2.4, along_x=False), *_wall_line("wall_ne", 2.6, 29.6, 2.4, along_x=True),
    *_wall_line("wall_sw", 2.6, 29.6, 29.0, along_x=True),
    *_wall_line("wall_se_n", 2.6, 14.3, 29.0, along_x=False), *_wall_line("wall_se_s", 17.6, 29.6, 29.0, along_x=False),
    _b("gatehouse", "gatehouse", 27.6, 14.3, 4.0, mirror=True),
    # the north corner: the pond, the pavilion, rocks and trees
    _b("pond", "pond", 4.6, 4.6, 5.0),
    _b("pavilion", "pavilion", 10.2, 3.4, 3.2),
    # along the north-east wall: the row house and a house; the market stalls face the plaza
    _b("rowhouse", "rowhouse", 16.4, 3.0, 8.0, 3.6, mirror=True),
    _b("house_ne", "house", 24.6, 3.2, 3.4, mirror=True),
    _b("stalls", "stalls", 14.0, 7.2, 4.4, mirror=True),
    # the west: the forge, the herb shop and its drying rack
    _b("forge", "forge", 3.4, 10.4, 4.8),
    _b("herbrack", "herbrack", 8.4, 15.2, 2.2),
    _b("herbshop", "herbshop", 3.6, 16.4, 4.0, mirror=True),
    _b("barrels_w", "barrels", 8.4, 9.8, 1.4),
    # the south-west: a house, trees and bushes
    _b("house_w", "house", 3.4, 22.2, 3.4),
    _b("house_sw", "house", 8.8, 25.0, 3.4, mirror=True),
    _b("boulders_sw", "boulders", 16.0, 26.6, 1.8),
    # the east: the training yard
    _b("rack_1", "rack", 22.4, 8.0, 1.4), _b("rack_2", "rack", 26.2, 7.6, 1.4, mirror=True),
    _b("dummy_1", "dummy", 22.6, 10.4, 0.55), _b("dummy_2", "dummy", 24.4, 9.6, 0.55), _b("dummy_3", "dummy", 25.8, 11.0, 0.55),
    _b("barrels_e", "barrels", 26.8, 12.0, 1.8),
    # the south: the arena, the stele by the plaza
    _b("arena", "arena", 18.4, 19.8, 6.4),
    _b("stele", "stele", 12.0, 17.6, 1.5),
    # lantern posts along the road and at the plaza's corners
    *[_b(f"lantern_{i}", "lantern", x, y, 0.4) for i, (x, y) in enumerate(
        [(21.4, 13.8), (24.8, 13.8), (21.4, 18.0), (24.8, 18.0), (10.4, 10.4), (20.0, 10.2), (10.2, 20.0)])],
]
# Props stand on one point (x, y), the bottom middle of the picture, drawn `h` world px tall; `r` blocks the way.
PROPS = [
    {"img": "well", "x": 15.5, "y": 15.5, "h": 200, "r": 0.8},
    # trees stand by the trunk: a crown is far wider than its roots, so each is where its crown hangs over nothing
    {"img": "blossom", "x": 21.6, "y": 7.0, "h": 380, "r": 0.4},     # by the training yard
    {"img": "blossom", "x": 15.2, "y": 25.6, "h": 380, "r": 0.4},    # in the south-west garden
    {"img": "pine", "x": 4.8, "y": 27.0, "h": 420, "r": 0.35},
    {"img": "pine", "x": 16.6, "y": 23.0, "h": 400, "r": 0.35},
]
# The ground (scripts/make_town_ground.py paints art/maps/town.webp from these): grass inside the walls, forest
# floor outside, the plaza paved and dirt roads, paths and yards; rectangles x0, y0, x1, y1 in tiles.
GROUND = {
    "stone": [(11.4, 11.4, 19.6, 19.6)],
    "dirt": [(19.6, 15.0, 32.0, 17.6),                          # the road from the gate
             (10.2, 10.2, 20.8, 20.8),                          # round the plaza
             (8.2, 10.4, 11.4, 21.0),                           # in front of the forge and the herb shop
             (8.6, 6.8, 12.6, 10.4), (12.6, 10.6, 19.6, 11.4),  # to the pavilion; in front of the stalls
             (20.8, 7.0, 28.6, 14.0),                           # the training yard
             (17.8, 19.2, 28.4, 28.6)],                         # round the arena
    "walls": (2.4, 2.4, 29.6, 29.6),                            # outside this: forest floor
}

# The townsfolk: where each stands (x, y, the feet), who they are, what they say, and where they send you (label,
# page). No `go`: what they look after isn't open on the website yet, and they say so. `src`: their picture
# (art/portraits/town/<key>.webp, see-through, feet at the bottom middle); without one the page draws a lantern
# glow and their name. `h`: how tall it is drawn, in world px (the cultivator is about 120); `flip`: the picture faces
# left (the page turns everyone toward you). scripts/make_town_npcs.py cuts them out.
NPCS = [
    {"key": "gate", "name": "Gate Warden", "title": "The road out", "x": 26.2, "y": 18.8,
     "src": "/art/portraits/town/gate.webp", "h": 135,
     "line": "The wilds are restless tonight. Beasts prowl the forest, and the herbs out there won't pick themselves.",
     "go": [["Hunt beasts", "/explore"], ["Gather herbs", "/gather"]]},
    {"key": "blacksmith", "name": "Blacksmith Tie", "title": "The forge", "x": 8.9, "y": 12.6,
     "src": "/art/portraits/town/blacksmith.webp", "h": 132,
     "line": "Steel listens to fire and patience. Bring me ore and I'll make you something worth swinging.",
     "go": [["Enter the forge", "/forge"]]},
    {"key": "alchemist", "name": "Herbalist Lan", "title": "Pills and herbs", "x": 8.6, "y": 19.6,
     "src": "/art/portraits/town/alchemist.webp", "h": 122,
     "line": "Every pill begins as a weed someone was wise enough to pick. Shall we refine something?",
     "go": [["Enter the alchemy hall", "/alchemy"]]},
    {"key": "merchant", "name": "Silk Merchant", "title": "Robes and looks", "x": 16.2, "y": 12.2,
     "src": "/art/portraits/town/merchant.webp", "h": 132,
     "line": "A cultivator should look the part. New robes, a new face to the world: I have it all.",
     "go": [["Change your look", "/appearance"]]},
    {"key": "elder", "name": "Village Elder", "title": "Your cultivation", "x": 11.6, "y": 7.4,
     "src": "/art/portraits/town/elder.webp", "h": 128,
     "line": "Sit a while, child. Let me see how far your cultivation has come.",
     "go": [["Show my cultivation", "/profile"], ["Check my bag", "/inventory"]]},
    {"key": "master", "name": "Martial Master", "title": "Training", "x": 24.0, "y": 12.2,
     "src": "/art/portraits/town/master.webp", "h": 128,
     "line": "The training yard isn't open to you yet. Train through the bot for now; my doors open soon."},
    {"key": "arena", "name": "Arena Keeper", "title": "Duels", "x": 25.4, "y": 22.4,
     "src": "/art/portraits/town/arena.webp", "h": 134,
     "line": "No duels in the ring tonight. When it opens, cultivators will test each other here."},
    {"key": "stele", "name": "Stone Stele", "title": "The rankings", "x": 14.0, "y": 19.4, "prop": True,
     "line": "The names of the town's strongest are carved here. The carving isn't finished yet."},
]


def inside(x, y, poly=AREA):
    """Point in polygon (even-odd)."""
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def in_footprint(x, y, b, inset=INSET):
    inset = min(inset, b["a"] / 4, b["b"] / 4)       # a small piece (a lantern) keeps most of its foot
    return b["x0"] + inset < x < b["x0"] + b["a"] - inset and b["y0"] + inset < y < b["y0"] + b["b"] - inset


def walkable(x, y):
    return (0 < x < SIZE and 0 < y < SIZE and inside(x, y)
            and all(math.dist((x, y), (cx, cy)) > r for cx, cy, r in BLOCKED)
            and not any(in_footprint(x, y, b) for b in BUILDINGS)
            and all(math.dist((x, y), (p["x"], p["y"])) > p["r"] for p in PROPS))


def screen(x, y):
    """A tile point on the ground picture, in world px."""
    return (SIZE * 64 + (x - y) * 64, (x + y) * 32)


def kit():
    with open(KIT) as f:
        return json.load(f)


def placed():
    """Where each building's and prop's picture is drawn (world px: left, top, width, height), and what it hides
    behind: a building's footprint, a prop's point."""
    k = kit()
    out = []
    for b in BUILDINGS:
        img = b["img"] + ("_m" if b.get("mirror") else "")
        c = k[img]
        s = (b["a"] + b["b"]) * 64 / (c["r"] - c["l"])
        bx, by = screen(b["x0"] + b["a"], b["y0"] + b["b"])
        out.append({"src": f"/art/maps/town/{img}.webp", "rect": [round(bx - c["bx"] * s, 1), round(by - c["by"] * s, 1),
                    round(c["w"] * s, 1), round(c["h"] * s, 1)], "fp": [b["x0"], b["y0"], b["a"], b["b"]]})
    for p in PROPS:
        c = k[p["img"]]
        w = p["h"] * c["w"] / c["h"]
        px, py = screen(p["x"], p["y"])
        out.append({"src": f"/art/maps/town/{p['img']}.webp", "rect": [round(px - w / 2, 1), round(py - p["h"], 1),
                    round(w, 1), p["h"]], "at": [p["x"], p["y"]]})
    return out


def page_data(sheet):
    """The page's data (web/static/town.js): the walking sheet, the map and the townsfolk. You come in at the gate
    (the page puts you back in front of whoever you last left town through)."""
    npcs = [{k: n[k] for k in ("key", "name", "title", "x", "y", "line")} |
            {"go": n.get("go", []), "prop": n.get("prop", False), "src": n.get("src"), "h": n.get("h", 128),
             "flip": n.get("flip", False)} for n in NPCS]
    return {"sheet": sheet, "size": SIZE, "ground": ART, "area": [list(p) for p in AREA], "inset": INSET,
            "blocked": [list(c) for c in BLOCKED] + [[p["x"], p["y"], p["r"]] for p in PROPS], "pieces": placed(),
            "reach": REACH, "scale": SCALE, "hero": {"x": START[0], "y": START[1]},
            "npcs": npcs}


def page_json(data):
    return json.dumps(data).replace("</", "<\\/")
