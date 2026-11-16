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
START = (21.3, 21.3)                 # just inside the gate, facing in
REACH = 1.5                          # how close (tiles) you must be to someone to talk to them
SCALE = 1.4                          # the town drawn this much bigger against you than the painting is (town.js K)
INSET = 0.2                          # you can step this far onto a footprint's edge (its paved base)

AREA = [                             # the town inside its walls, clockwise from the top corner
    (1.0, 1.0), (28.6, 1.0), (28.6, 5.0), (27.6, 14.0), (26.6, 21.0), (24.4, 22.8), (23.2, 23.4), (22.0, 23.4),
    (21.0, 22.6), (20.4, 21.8), (14.2, 21.4), (13.6, 23.0), (13.0, 26.0), (5.0, 26.0), (1.0, 24.0),
]
BLOCKED = [                          # (x, y, radius) in tiles
    (4.7, 6.2, 1.4), (9.4, 5.9, 1.9),   # the pond's two pools
]

# Buildings: `img` the picture (art/maps/town/<img>.webp, or <img>_m mirrored), its footprint x0..x0+a, y0..y0+b in
# tiles. A picture's door faces the bottom-right (+x); `mirror` turns it to the bottom-left (+y), swapping which side
# is long. The picture's base corners are fitted onto the footprint's left, right and bottom corners.
BUILDINGS = [
    {"key": "pavilion", "img": "pavilion", "x0": 3.0, "y0": 3.4, "a": 3.6, "b": 3.6},
    {"key": "rowhouse", "img": "rowhouse", "x0": 11.4, "y0": 1.2, "a": 8.6, "b": 3.8, "mirror": True},
    {"key": "house_ne", "img": "house", "x0": 21.0, "y0": 1.4, "a": 3.6, "b": 3.6, "mirror": True},
    {"key": "house_nw", "img": "house", "x0": 0.8, "y0": 7.2, "a": 3.6, "b": 3.6},
    {"key": "house_w", "img": "house", "x0": 1.4, "y0": 20.2, "a": 3.6, "b": 3.6},
    {"key": "forge", "img": "forge", "x0": 6.0, "y0": 10.8, "a": 4.8, "b": 4.8},
    {"key": "herbshop", "img": "herbshop", "x0": 5.8, "y0": 16.8, "a": 4.0, "b": 4.0, "mirror": True},
    {"key": "stalls", "img": "stalls", "x0": 11.4, "y0": 6.6, "a": 8.0, "b": 3.4, "mirror": True},
    {"key": "arena", "img": "arena", "x0": 19.8, "y0": 10.2, "a": 7.2, "b": 7.2},
    {"key": "stele", "img": "stele", "x0": 20.0, "y0": 18.4, "a": 1.5, "b": 1.5},
]
# Props stand on one point (x, y), the bottom middle of the picture, drawn `h` world px tall; `r` blocks the way.
PROPS = [
    {"img": "well", "x": 16.2, "y": 16.2, "h": 190, "r": 0.8},
    {"img": "dummy1", "x": 21.6, "y": 7.4, "h": 120, "r": 0.3},
    {"img": "dummy2", "x": 23.2, "y": 8.2, "h": 120, "r": 0.3},
    {"img": "dummy1", "x": 24.6, "y": 6.8, "h": 120, "r": 0.3},
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
    {"key": "blacksmith", "name": "Blacksmith Tie", "title": "The forge", "x": 11.6, "y": 13.6,
     "src": "/art/portraits/town/blacksmith.webp", "h": 132,
     "line": "Steel listens to fire and patience. Bring me ore and I'll make you something worth swinging.",
     "go": [["Enter the forge", "/forge"]]},
    {"key": "alchemist", "name": "Herbalist Lan", "title": "Pills and herbs", "x": 10.6, "y": 19.4,
     "src": "/art/portraits/town/alchemist.webp", "h": 122,
     "line": "Every pill begins as a weed someone was wise enough to pick. Shall we refine something?",
     "go": [["Enter the alchemy hall", "/alchemy"]]},
    {"key": "merchant", "name": "Silk Merchant", "title": "Robes and looks", "x": 15.4, "y": 10.8,
     "line": "A cultivator should look the part. New robes, a new face to the world: I have it all.",
     "go": [["Change your look", "/appearance"]]},
    {"key": "elder", "name": "Village Elder", "title": "Your cultivation", "x": 7.2, "y": 7.8,
     "line": "Sit a while, child. Let me see how far your cultivation has come.",
     "go": [["Show my cultivation", "/profile"], ["Check my bag", "/inventory"]]},
    {"key": "master", "name": "Martial Master", "title": "Training", "x": 22.2, "y": 9.4,
     "src": "/art/portraits/town/master.webp", "h": 128,
     "line": "The training yard isn't open to you yet. Train through the bot for now; my doors open soon."},
    {"key": "arena", "name": "Arena Keeper", "title": "Duels", "x": 23.4, "y": 18.3,
     "src": "/art/portraits/town/arena.webp", "h": 134, "flip": True,
     "line": "No duels in the ring tonight. When it opens, cultivators will test each other here."},
    {"key": "stele", "name": "Stone Stele", "title": "The rankings", "x": 20.7, "y": 20.4, "prop": True,
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
