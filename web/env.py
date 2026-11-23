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


# ── The open lands (web/land.py, docs/world.md): dressed in GROUPS ──────────────────────────────────────────────
# A land is far too big to place piece by piece, and single pieces dotted about look scattered. So a land is dressed
# in small arrangements, each composed once (GROUPS: pieces at offsets, in tiles, round the group's own spot) and
# then set down by hand where it belongs (DRESSED: group, x, y, mirrored, scale). Mirroring a group mirrors it on
# screen (its offsets swap axes and every piece is flipped), so one arrangement gives two looks.
GROUPS = {
    # a mossy boulder with its small stones, a fern in its lee and grass at its foot
    "boulders": [("boulder_01", 0, 0, 1.0, False), ("rock_small_01", 0.9, 0.35, 0.9, True),
                 ("rock_small_01", -0.5, 0.8, 0.75, False), ("fern_01", 0.75, -0.55, 0.9, False),
                 ("grass_01", -0.8, -0.3, 1.0, True), ("grass_01", 0.3, 1.0, 0.85, False)],
    # an old fallen trunk: ferns at both ends, mushrooms along its damp side
    "fallen": [("log_long_01", 0, 0, 1.0, False), ("fern_01", 0.5, -1.9, 1.0, False), ("fern_01", -0.55, 1.8, 0.85, True),
               ("mushroom_01", 0.5, 0.2, 0.9, False), ("mushroom_01", 0.55, 0.8, 0.75, True),
               ("mushroom_01", -0.5, -0.6, 0.8, False), ("grass_01", 0.75, 1.7, 0.9, False)],
    # a broken stump of a log with mushrooms crowding it
    "nook": [("log_broken_01", 0, 0, 1.0, False), ("mushroom_01", 0.55, 0.1, 1.0, False),
             ("mushroom_01", 0.65, -0.45, 0.8, True), ("mushroom_01", -0.5, 0.5, 0.7, False),
             ("fern_01", -0.65, -0.9, 0.95, True)],
    # a drift of flowers in open grass
    "flowers": [("flowers_01", 0, 0, 1.0, False), ("flowers_01", 0.7, 0.3, 0.85, True), ("flowers_01", -0.5, 0.7, 0.9, False),
                ("flowers_01", 0.3, -0.8, 0.8, True), ("flowers_01", -0.9, -0.3, 0.75, False),
                ("flowers_01", 1.2, -0.5, 0.7, False), ("grass_01", 0.5, 1.0, 1.0, False),
                ("grass_01", -0.3, -1.2, 0.9, True), ("grass_01", 1.4, 0.6, 0.85, False)],
    # a ring of spirit mushrooms glowing in deep shade: where something may be hidden
    "spirit": [("spirit_mushroom_01", 0, 0, 1.0, False), ("spirit_mushroom_01", 0.55, 0.35, 0.8, True),
               ("spirit_mushroom_01", -0.4, 0.6, 0.7, False), ("spirit_mushroom_01", 0.25, -0.6, 0.85, True),
               ("spirit_mushroom_01", -0.7, -0.2, 0.65, False), ("fern_01", 0.95, -0.45, 0.9, False)],
    # a heap of stones with strays
    "stones": [("stones_cluster_01", 0, 0, 1.0, False), ("rock_small_01", 1.0, 0.5, 0.8, False),
               ("rock_small_01", -0.45, 1.05, 0.7, True), ("grass_01", 0.95, -0.55, 0.9, False)],
    # tufts of long grass
    "tufts": [("grass_01", 0, 0, 1.0, False), ("grass_01", 0.6, 0.5, 0.85, True), ("grass_01", -0.5, 0.7, 0.9, False),
              ("grass_01", 1.1, -0.2, 0.8, False), ("grass_01", -1.0, -0.4, 0.95, True), ("grass_01", 0.2, 1.3, 0.75, False)],
    # a bank of ferns with a few mushrooms under them
    "ferns": [("fern_01", 0, 0, 1.0, False), ("fern_01", 0.7, 0.4, 0.85, True), ("fern_01", -0.6, 0.5, 0.9, False),
              ("fern_01", 0.2, -0.8, 0.8, True), ("mushroom_01", 0.9, -0.3, 0.8, False), ("mushroom_01", -0.3, 1.0, 0.7, True)],
    # one stone by the wayside
    "pebble": [("rock_small_01", 0, 0, 0.9, False), ("grass_01", 0.5, 0.3, 0.8, True)],
}

# Forest Edge (70 x 70; the road runs from the north gate at (40, 4) winding south to (38, 66), a path east to the far
# clearing at (60, 15) and one west to the hollow at (12, 50)). The meadow's last flowers in the north; ferns and
# fallen trunks as the trees' floor begins; stones and boulders off the road, never on it; spirit mushrooms glowing
# by each hidden spot and in the far corners, for those who leave the path.
DRESSED = {
    "forest_edge": [
        # the northern meadow: flowers and long grass either side of the road, a few stones
        ("flowers", 35.0, 8.0, False, 1.0), ("flowers", 45.5, 9.0, True, 1.0), ("flowers", 29.0, 7.0, False, 0.9),
        ("flowers", 53.0, 10.5, True, 0.95), ("flowers", 24.0, 11.0, True, 0.9),
        ("tufts", 37.0, 12.5, False, 1.0), ("tufts", 47.0, 6.0, True, 1.0), ("tufts", 31.0, 12.0, True, 0.9),
        ("tufts", 50.0, 14.5, False, 1.0), ("pebble", 36.2, 7.6, False, 1.0), ("pebble", 43.6, 7.2, True, 0.9),
        ("stones", 27.0, 4.8, False, 0.9), ("boulders", 56.5, 6.5, True, 1.0),
        # where the trees' floor begins, along the road south-west
        ("ferns", 45.5, 17.0, False, 1.0), ("nook", 34.5, 15.0, True, 1.0), ("boulders", 47.5, 20.5, False, 1.1),
        ("fallen", 28.5, 17.5, False, 1.0), ("ferns", 37.5, 27.0, True, 0.95), ("pebble", 39.6, 19.6, False, 1.0),
        ("tufts", 41.0, 23.5, False, 0.9), ("spirit", 21.5, 13.2, False, 1.0), ("boulders", 21.0, 20.0, True, 1.0),
        # the west path, down to the hollow
        ("ferns", 27.0, 22.0, False, 1.0), ("tufts", 20.0, 24.5, True, 1.0), ("nook", 25.5, 31.5, False, 1.0),
        ("ferns", 18.5, 33.5, True, 1.0), ("stones", 9.5, 40.0, False, 1.0), ("fallen", 17.5, 44.0, True, 1.0),
        ("ferns", 24.0, 38.0, False, 0.9), ("spirit", 8.6, 46.6, True, 1.0), ("flowers", 14.0, 53.5, False, 0.9),
        ("boulders", 7.2, 53.8, False, 1.1), ("nook", 19.0, 49.0, True, 1.0), ("tufts", 15.5, 47.0, False, 0.9),
        # the middle clearing, where the paths part
        ("flowers", 32.6, 36.6, False, 1.0), ("flowers", 39.5, 31.0, True, 0.9), ("tufts", 38.5, 37.5, True, 1.0),
        ("boulders", 30.5, 31.5, False, 1.0), ("pebble", 30.6, 27.4, True, 1.0),
        # the east path, up to the far clearing
        ("fallen", 50.0, 25.6, True, 1.0), ("stones", 54.5, 29.5, False, 1.0), ("ferns", 58.5, 20.5, True, 1.0),
        ("flowers", 61.5, 17.0, False, 0.9), ("spirit", 62.4, 12.2, False, 1.0), ("boulders", 64.0, 17.5, True, 1.0),
        ("tufts", 57.0, 12.5, False, 1.0), ("ferns", 44.0, 27.5, False, 0.9), ("tufts", 47.0, 35.5, False, 1.0),
        # the road south
        ("boulders", 47.5, 41.5, False, 1.0), ("nook", 38.0, 48.5, False, 1.0), ("fallen", 46.5, 52.5, False, 1.0),
        ("flowers", 53.8, 53.4, True, 0.9), ("spirit", 50.4, 50.3, True, 1.0), ("stones", 55.5, 49.5, True, 1.0),
        ("ferns", 49.0, 56.5, False, 1.0), ("ferns", 31.0, 50.0, True, 1.0), ("boulders", 28.0, 44.0, True, 1.1),
        ("fallen", 30.0, 58.5, True, 1.0), ("nook", 24.0, 53.0, False, 1.0), ("tufts", 33.0, 62.0, False, 1.0),
        ("stones", 41.5, 61.0, False, 0.9), ("flowers", 35.0, 63.5, True, 0.85), ("pebble", 42.9, 39.5, False, 1.0),
        ("pebble", 41.8, 53.9, True, 1.0), ("stones", 51.0, 37.0, False, 0.95), ("ferns", 54.0, 42.5, True, 1.0),
        # the far corners, for those who leave the paths
        ("boulders", 9.0, 61.0, False, 1.15), ("ferns", 13.0, 63.0, True, 1.0), ("spirit", 6.8, 58.0, False, 1.0),
        ("stones", 8.0, 17.0, True, 1.0), ("fallen", 12.0, 22.5, False, 1.0), ("ferns", 6.0, 25.0, False, 1.0),
        ("flowers", 9.5, 9.0, False, 0.9), ("boulders", 63.0, 35.0, False, 1.1), ("nook", 60.0, 40.5, True, 1.0),
        ("tufts", 58.0, 45.5, True, 1.0), ("ferns", 64.0, 48.0, False, 1.0), ("fallen", 59.0, 60.0, True, 1.0),
        ("stones", 63.5, 57.0, False, 1.0), ("flowers", 57.0, 63.5, False, 0.9), ("spirit", 62.5, 63.5, True, 1.0),
        ("boulders", 15.0, 9.5, True, 1.0), ("tufts", 12.5, 31.0, False, 1.0), ("stones", 22.0, 60.0, True, 1.0),
        ("ferns", 17.0, 57.0, False, 0.95), ("tufts", 44.0, 63.0, True, 0.9), ("boulders", 53.0, 62.5, False, 1.0),
    ],
}


def dressed(key):
    """A land's groups set out as single pieces: (asset, x, y, scale, flip)."""
    out = []
    for group, gx, gy, mirror, gs in DRESSED.get(key, []):
        for name, dx, dy, s, flip in GROUPS[group]:
            if mirror:
                dx, dy, flip = dy, dx, not flip
            out.append((name, round(gx + dx * gs, 2), round(gy + dy * gs, 2), round(s * gs, 3), flip))
    return out


LAND_PLACED = {key: dressed(key) for key in DRESSED}
LAND_TONE = {"forest_edge": TONE["moon_forest"], "deep_woods": TONE["moon_forest"], "shrine_grove": TONE["moon_forest"]}


def _axis(flip):
    """A log's direction along the ground (tiles): the y axis as drawn, the x axis mirrored."""
    return (1.0, 0.0) if flip else (0.0, 1.0)


def placed(key, k=1.0):
    """This map's or land's pieces, (asset, x, y, scale, flip), each scale times `k`. A land is drawn bigger against
    you than the old painted map was (web/land.py SCALE), so its pieces are made that much smaller (k = 1 / SCALE)
    to stay the same size beside the cultivator."""
    return [(name, x, y, s * k, flip) for name, x, y, s, flip in PLACED.get(key) or LAND_PLACED.get(key, [])]


def blocks(key, k=1.0):
    """Where this map's pieces block the way: circles (x, y, radius) in tiles."""
    out = []
    for name, x, y, s, flip in placed(key, k):
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


def pieces(key, k=1.0):
    """This map's pieces for the page (web/static/huntmap.js): each picture's rectangle in world px (the map's top
    corner at x 0), mirrored or not, what it hides you behind (a point's depth, or a log's footprint), its shadow,
    and its glow."""
    cat = catalog()
    out = []
    for name, x, y, s, flip in placed(key, k):
        a, c = ASSETS[name], cat.get(name)
        if c is None:                              # not cut yet: nothing to draw
            continue
        z = (a["h"] / c["h"] if "h" in a else a["w"] / c["w"]) * s
        w, h = c["w"] * z, c["h"] * z
        fx = (c["w"] - c["foot"][0]) if flip else c["foot"][0]
        sx, sy = (x - y) * 64, (x + y) * 32
        p = {"src": "/" + path(name), "lit": bool(a.get("lit")), "rect": [round(sx - fx * z, 1), round(sy - c["foot"][1] * z, 1), round(w, 1),
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


def lights(key, k=1.0):
    """Glowing pieces (the spirit mushrooms) as lights for the page: (x, y, colour, radius in world px)."""
    out = []
    for name, x, y, s, _ in placed(key, k):
        g = ASSETS[name].get("glow")
        if g:
            out.append((x, y, g, round(46 * s)))
    return out
