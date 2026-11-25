"""
Environment pieces (docs/environment.md): rocks, logs, plants and mushrooms that stand on a map, each one picture
reused wherever it is placed.

ASSETS says what each picture is: where it lives (art/env/<region>/<category>/<name>.webp), how big it is drawn
(`h`: its height in world px at scale 1, or `w`: its width, for a long thing), whether and how much it blocks the way
(`block`: a radius in tiles; a log blocks a row of circles along its length, `length` tiles), and whether it glows
(`glow`: a colour; the page lights it like the map's painted lamps). scripts/make_env_assets.py cuts SHOAIB's Gemini
pictures into those files and measures each one into art/env/catalog.json: its size and its foot (the pixel where it
touches the ground).

PLACED gives each map's pieces: (asset, x, y, scale, flip), x and y in tiles where its foot stands (for a log: the
middle of its length). A flat picture can't turn round, so variety comes from `flip` (mirrored left to right), `scale`
and the asset's variants. A log as drawn lies along the map's y axis (on screen: lower-left to upper-right); flipped,
along the x axis (upper-left to lower-right).

The pieces are only a look and a few obstacles: the server's walkable test gets their blocks (web/hunt_map.py), so it
and the page agree on where you can stand; nothing else in the game changes.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "art", "env", "catalog.json")

ASSETS = {
    # rocks
    "rock_small_01": {"region": "common", "cat": "rocks", "h": 56, "block": 0.36},
    "boulder_01": {"region": "common", "cat": "rocks", "h": 124, "block": 0.75},
    "stones_cluster_01": {"region": "common", "cat": "rocks", "h": 104, "block": 0.8},
    # logs: as drawn they lie along the y axis
    "log_long_01": {"region": "common", "cat": "logs", "w": 380, "block": 0.36, "length": 4.4},
    "log_broken_01": {"region": "common", "cat": "logs", "w": 200, "block": 0.36, "length": 2.2},
    # plants: nothing blocks
    "grass_01": {"region": "common", "cat": "plants", "h": 44},
    "fern_01": {"region": "common", "cat": "plants", "h": 70},
    "flowers_01": {"region": "common", "cat": "plants", "h": 40},
    # mushrooms
    "mushroom_01": {"region": "common", "cat": "mushrooms", "h": 40},
    "spirit_mushroom_01": {"region": "moon_forest", "cat": "mushrooms", "h": 44, "glow": "#5FC8FF", "lit": True},
    # herb habitats (Nov 25 2026): still pools for lotuses and lilies, a mossy rock for moss
    "pond_01": {"region": "common", "cat": "water", "w": 300, "block": 1.3, "flat": True},
    "pond_02": {"region": "common", "cat": "water", "w": 270, "block": 1.2, "flat": True},
    "mossy_rock_01": {"region": "common", "cat": "rocks", "h": 84, "block": 0.7},
    # the Ironvein Quarry (docs/world.md "The Ironvein Quarry"): rock walls, the three seams, the keeper's hut
    "cliff_01": {"region": "quarry", "cat": "rocks", "h": 330, "block": 1.7},
    "cliff_02": {"region": "quarry", "cat": "rocks", "h": 270, "block": 1.7},
    "seam_iron_01": {"region": "quarry", "cat": "seams", "h": 150, "block": 0.85},
    "seam_coal_01": {"region": "quarry", "cat": "seams", "h": 120, "block": 0.85},
    "seam_jade_01": {"region": "quarry", "cat": "seams", "h": 140, "block": 0.85},
    "quarry_hut_01": {"region": "quarry", "cat": "buildings", "h": 300, "block": 1.9},
}


# Each map's light (red, green, blue: how much of each the pieces keep), so pictures painted in daylight sit in its
# night. The page tints each picture once when it loads. `lit` pieces (glowing ones) keep more of their colour.
TONE = {"moon_forest": [0.56, 0.64, 0.80]}


def path(name):
    a = ASSETS[name]
    return f"art/env/{a['region']}/{a['cat']}/{name}.webp"


def catalog():
    try:
        with open(CATALOG) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ── Moon Forest (web/hunt_map.py MAPS["moon_forest"]) ─────────────────────────────────────────────────────────────
# Placed by hand on the painting (press G on the map for the grid): rocks along the stream and under the bamboo,
# logs in the clearings off the paths, ferns and mushrooms in the shade of the old tree, the stump and the shrine,
# spirit mushrooms where the light is cold (by the shrine's blue lanterns and the pond), grass and flowers in the open.
PLACED = {
    "moon_forest": [
        # rocks
        ("boulder_01", 19.9, 6.6, 1.0, False),
        ("boulder_01", 6.0, 7.4, 0.85, True),
        ("stones_cluster_01", 8.7, 20.8, 1.0, False),
        ("stones_cluster_01", 20.3, 16.6, 0.9, True),
        ("rock_small_01", 6.3, 13.3, 1.0, False),
        ("rock_small_01", 17.6, 9.2, 0.85, True),
        ("rock_small_01", 15.9, 17.5, 0.9, False),
        ("rock_small_01", 10.6, 5.6, 1.1, True),
        ("rock_small_01", 4.4, 20.6, 0.8, False),
        # logs
        ("log_long_01", 19.7, 10.4, 1.0, False),
        ("log_broken_01", 8.9, 12.9, 1.0, False),
        ("log_broken_01", 12.6, 8.2, 0.9, False),
        # ferns
        ("fern_01", 4.7, 12.2, 1.0, False),
        ("fern_01", 4.1, 15.4, 0.9, True),
        ("fern_01", 12.4, 5.0, 0.95, True),
        ("fern_01", 20.7, 8.3, 0.85, False),
        ("fern_01", 9.6, 21.9, 1.0, True),
        ("fern_01", 18.6, 4.2, 0.9, False),
        # mushrooms
        ("mushroom_01", 5.0, 9.4, 1.0, False),
        ("mushroom_01", 9.8, 14.2, 0.9, True),
        ("mushroom_01", 13.1, 4.9, 0.85, False),
        ("mushroom_01", 20.5, 12.4, 1.0, True),
        ("spirit_mushroom_01", 4.0, 19.1, 1.0, False),
        ("spirit_mushroom_01", 12.4, 13.4, 0.9, True),
        ("spirit_mushroom_01", 15.8, 16.2, 0.85, False),
        ("spirit_mushroom_01", 4.3, 11.4, 0.9, True),
        # flowers
        ("flowers_01", 9.4, 10.6, 1.0, False),
        ("flowers_01", 15.6, 7.9, 0.9, True),
        ("flowers_01", 7.6, 9.2, 0.85, True),
        ("flowers_01", 17.2, 13.6, 1.0, False),
        ("flowers_01", 11.2, 17.3, 0.9, False),
        # grass
        ("grass_01", 6.8, 12.4, 1.0, False),
        ("grass_01", 9.0, 7.0, 0.9, True),
        ("grass_01", 14.6, 6.4, 1.1, False),
        ("grass_01", 18.4, 7.5, 0.9, True),
        ("grass_01", 21.0, 14.9, 1.0, False),
        ("grass_01", 10.3, 19.6, 1.0, True),
        ("grass_01", 7.3, 15.4, 0.85, False),
        ("grass_01", 16.7, 18.8, 1.0, True),
        ("grass_01", 13.1, 10.8, 0.8, False),
        ("grass_01", 5.6, 18.0, 1.0, True),
    ],
}


def _axis(flip):
    """A log's direction along the ground (tiles): the y axis as drawn, the x axis mirrored."""
    return (1.0, 0.0) if flip else (0.0, 1.0)


def blocks(key):
    """Where this map's pieces block the way: circles (x, y, radius) in tiles."""
    out = []
    for name, x, y, s, flip in PLACED.get(key, []):
        a = ASSETS[name]
        if not a.get("block"):
            continue
        r = a["block"] * s
        if a.get("length"):
            half = a["length"] * s / 2
            n = max(2, math.ceil(a["length"] * s / (r * 1.4)))
            dx, dy = _axis(flip)
            for i in range(n):
                t = -half + r + (2 * half - 2 * r) * i / (n - 1)
                out.append((round(x + dx * t, 3), round(y + dy * t, 3), round(r, 3)))
        else:
            out.append((x, y, round(r, 3)))
    return out


def pieces(key):
    """This map's pieces for the page (web/static/huntmap.js): each picture's rectangle in world px (the map's top
    corner at x 0), mirrored or not, what it hides you behind (a point's depth, or a log's footprint), its shadow,
    and its glow."""
    cat = catalog()
    out = []
    for name, x, y, s, flip in PLACED.get(key, []):
        a, c = ASSETS[name], cat.get(name)
        if c is None:                              # not cut yet: nothing to draw
            continue
        k = (a["h"] / c["h"] if "h" in a else a["w"] / c["w"]) * s
        w, h = c["w"] * k, c["h"] * k
        fx = (c["w"] - c["foot"][0]) if flip else c["foot"][0]
        sx, sy = (x - y) * 64, (x + y) * 32
        p = {"src": "/" + path(name), "lit": bool(a.get("lit")), "rect": [round(sx - fx * k, 1), round(sy - c["foot"][1] * k, 1), round(w, 1),
             round(h, 1)], "flip": flip, "at": [x, y]}
        if a.get("length"):
            half = a["length"] * s / 2
            dx, dy = _axis(flip)
            r = a["block"] * s
            x0, y0 = min(x - dx * half, x + dx * half) - r, min(y - dy * half, y + dy * half) - r
            p["fp"] = [round(x0, 3), round(y0, 3), round(2 * (half * dx + r), 3), round(2 * (half * dy + r), 3)]
            p["shadow"] = {"len": round(a["length"] * s * 71.6 / 2, 1), "wide": round(12 * s, 1), "axis": "x" if flip else "y"}
        else:
            p["shadow"] = {"rx": round(w * 0.36, 1), "ry": round(w * 0.12, 1)}
        out.append(p)
    return out


def lights(key):
    """Glowing pieces (the spirit mushrooms) as lights for the page: (x, y, colour, radius in world px)."""
    out = []
    for name, x, y, s, _ in PLACED.get(key, []):
        g = ASSETS[name].get("glow")
        if g:
            out.append((x, y, g, round(46 * s)))
    return out
