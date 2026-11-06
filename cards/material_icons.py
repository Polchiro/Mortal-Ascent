"""
Drawn icons for the forging materials (forge.py, docs/forge.md) and the passive rarity emblems.

    draw(img, key, center, size)          theme.icon(img, "mat:<key>", ...) calls this
    passive_emblem(img, rarity, center, size)

key is a forge material key: base:<weapon|armor|artifact>:<1-5> · binding:<1-5> · fuel:<1-5> · liquid:<1-5>
· essence:<family>:<shard|crystal|heart> · seal.

Every material type has its own drawn shape (ore chunk, folded hide, silk roll, jade disc, bone, flask ...).
The tier shows through the colour and the frame, like the gear rarity emblems: tier 1 sits in a plain iron ring,
tier 5 in a radiant star with a glow. Essences are coloured by their family and framed by their grade.
Pillow only, no image files.
"""
from PIL import ImageDraw

import forge

from . import theme as T
from .drawkit import Pen, glow, tint
from .emblems import frame

WHITE = (255, 255, 255)
VOIDC = (10, 6, 7)

# ── frames: tier 1 → 5 (same steps as the gear rarity emblems) ────────
TIER_FRAME = [
    dict(shape="circle", mat="iron", glow_strength=0),
    dict(shape="hex", mat="bronze", glow_strength=40, studs=6),
    dict(shape="oct", mat="jadeblue", glow_strength=100),
    dict(shape="oct", mat="gold", glow_strength=150, double=True, studs=8),
    dict(shape="circle", mat="radiant", glow_strength=180, halo=True, rays=16),
]
GRADE_FRAME = {
    "shard":   dict(shape="circle", mat="iron", glow_strength=30),
    "crystal": dict(shape="oct", mat="jadeblue", glow_strength=110),
    "heart":   dict(shape="circle", mat="radiant", glow_strength=170, halo=True, rays=16),
}
SEAL_FRAME = dict(shape="hex", mat="gold", glow_strength=60, studs=6)

# ── colours ───────────────────────────────────────────────────────────
# Essence family colours: the beast element colours, gold for Metal, four new ones for the artifact families
FAMILY_COLOR = {
    "metal":        (232, 192, 96),
    "spirit_dew":   (196, 236, 255),     # pale dew blue-white
    "fortune":      (246, 108, 160),     # lucky rose
    "cauldron_ash": (176, 160, 150),     # ash grey with embers
    "insight":      (108, 112, 240),     # indigo ink
}
for _fam, _spec in forge.FAMILIES.items():
    if _spec["element"]:
        FAMILY_COLOR[_fam] = T.ELEMENT_ACCENTS[_spec["element"]].rim

METAL_COLORS = [(150, 120, 104), (78, 80, 92), (196, 212, 232), (96, 120, 200), (246, 200, 92)]
ARMOR_COLORS = [(164, 112, 66), (124, 132, 144), (220, 228, 244), (72, 176, 140), (240, 172, 68)]
JADE_COLORS = [(92, 172, 110), (226, 232, 220), (110, 214, 204), (124, 146, 236), (206, 156, 246)]
BINDING_COLORS = [(226, 214, 190), (196, 96, 84), (238, 232, 214), (184, 40, 52), (176, 92, 226)]
FUEL_COLORS = [(66, 60, 58), (36, 36, 42), (70, 96, 150), (232, 112, 40), (255, 196, 70)]
LIQUID_COLORS = [(120, 184, 236), (206, 162, 60), (120, 236, 214), (206, 28, 40), (236, 240, 255)]


def tier_color(tier):
    return T.RARITY[forge.TIERS[tier - 1]]


# ── shapes (Pen units: -1 … 1, y down) ────────────────────────────────

def _ore(p, c, tier):
    dk, li = tint(c, -0.45), tint(c, 0.35)
    p.poly([(-0.8, 0.2), (-0.55, -0.45), (-0.05, -0.75), (0.5, -0.5), (0.82, 0.05), (0.6, 0.6), (0.0, 0.78),
            (-0.6, 0.6)], c, dk, 0.06)
    p.poly([(-0.55, -0.45), (-0.05, -0.75), (0.5, -0.5), (0.05, -0.15)], li)
    p.poly([(0.05, -0.15), (0.5, -0.5), (0.82, 0.05), (0.6, 0.6)], tint(c, -0.2))
    p.line([(-0.5, 0.3), (-0.1, 0.05), (0.25, 0.4)], tint(c, 0.55), 0.06)
    if tier >= 4:
        for x, y, r in ((-0.35, 0.25, 0.16), (0.3, 0.2, 0.12), (-0.05, -0.4, 0.13)):
            p.sparkle(x, y, r, WHITE if tier == 5 else (210, 226, 255))


def _folded_hide(p, c, tier):
    dk = tint(c, -0.45)
    p.poly([(-0.85, -0.55), (0.75, -0.7), (0.85, 0.5), (0.2, 0.72), (-0.8, 0.6)], c, dk, 0.06)
    p.poly([(-0.85, -0.55), (0.75, -0.7), (0.0, 0.05)], tint(c, 0.25), dk, 0.04)     # folded-over flap
    for x, y in ((-0.45, 0.35), (0.35, 0.3), (0.0, 0.5)):
        p.circle(x, y, 0.08, dk)


def _shell_plate(p, c, tier):
    dk, li = tint(c, -0.5), tint(c, 0.35)
    p.poly([(-0.8, -0.6), (0.8, -0.6), (0.68, 0.45), (0.0, 0.85), (-0.68, 0.45)], c, dk, 0.07)
    for y in (-0.25, 0.1, 0.42):
        p.arc(0, y - 0.35, 0.72, 35, 145, dk, 0.06)
    p.line([(-0.62, -0.48), (0.62, -0.48)], li, 0.06)
    for x in (-0.6, 0.6):
        p.circle(x, -0.42, 0.07, T.GOLD_HI)


def _silk_roll(p, c, tier):
    dk, li = tint(c, -0.4), tint(c, 0.3)
    p.rrect(-0.75, -0.42, 0.45, 0.42, 0.1, c, dk, 0.05)
    p.ellipse(0.45, 0.0, 0.25, 0.42, li, dk, 0.05)
    p.spiral(0.45, 0.0, 0.22, dk, 0.04, 2.2)
    p.poly([(-0.65, 0.42), (-0.3, 0.42), (-0.1, 0.9), (-0.55, 0.78)], li, dk, 0.04)        # loose ribbon end
    for x in (-0.45, -0.15, 0.15):
        p.line([(x, -0.38), (x, 0.38)], tint(c, -0.15), 0.03)


def _scale(p, c, tier):
    dk, li = tint(c, -0.45), tint(c, 0.4)
    for x, y, k in ((-0.42, -0.25, 0.55), (0.42, -0.25, 0.55), (0.0, 0.2, 0.75)):
        q = p.sub(x, y, k)
        q.poly([(0.0, -0.9), (0.62, -0.5), (0.7, 0.2), (0.0, 0.95), (-0.7, 0.2), (-0.62, -0.5)],
               c if k > 0.6 else tint(c, -0.2), dk, 0.08)
        q.line([(0.0, -0.75), (0.0, 0.75)], li, 0.07)
        q.arc(0, 0.25, 0.5, 200, 340, dk, 0.06)


def _qilin_hide(p, c, tier):
    dk = tint(c, -0.45)
    pts = [(-0.85, -0.5), (-0.5, -0.75), (0.0, -0.62), (0.5, -0.78), (0.85, -0.45), (0.75, 0.2), (0.88, 0.62),
           (0.35, 0.82), (-0.2, 0.7), (-0.8, 0.8), (-0.7, 0.2)]
    p.poly(pts, c, dk, 0.06)
    for x, y in ((-0.35, -0.15), (0.3, 0.25)):              # cloud-flame markings
        p.spiral(x, y, 0.22, (255, 236, 170), 0.05, 1.4)
    for i in range(5):                                     # mane fringe on top
        x = -0.6 + i * 0.3
        p.poly([(x - 0.1, -0.6), (x + 0.1, -0.6), (x, -0.92)], (236, 96, 52))


def _jade_disc(p, c, tier):
    dk, li = tint(c, -0.45), tint(c, 0.4)
    p.circle(0, 0, 0.85, c, dk, 0.06)
    p.ring(0, 0, 0.66, dk, 0.05)
    n = 6 + tier * 2
    import math
    for i in range(n):
        a = math.radians(i * 360 / n)
        p.circle(math.cos(a) * 0.5, math.sin(a) * 0.5, 0.06, dk)
    p.circle(0, 0, 0.26, VOIDC, dk, 0.05)
    p.arc(0, 0, 0.75, 200, 250, li, 0.07)
    if tier >= 4:
        p.sparkle(0.45, -0.55, 0.2, WHITE)
    if tier == 5:
        p.spiral(0, 0, 0.62, tint(c, 0.6), 0.04, 1.2)


def _bone(p, c, tier):
    dk = tint(c, -0.45)
    q = p.sub(rot=-40)
    q.capsule((-0.55, 0.0), (0.55, 0.0), 0.22, c, dk, 0.05)
    for x in (-0.62, 0.62):
        for y in (-0.17, 0.17):
            q.circle(x, y, 0.22, c, dk, 0.05)
    q.capsule((-0.45, 0.0), (0.45, 0.0), 0.18, c)


def _sinew(p, c, tier):
    dk = tint(c, -0.45)
    import math
    for ph, col in ((0.0, c), (math.pi, tint(c, 0.25))):
        p.line([(-0.8 + 1.6 * i / 24, math.sin(ph + i / 24 * 4 * math.pi) * 0.3) for i in range(25)], col, 0.16)
    p.line([(-0.85, 0.0), (0.85, 0.0)], dk, 0.04)


def _fang(p, c, tier):
    dk = tint(c, -0.4)
    p.poly([(-0.5, -0.8), (0.45, -0.8), (0.4, -0.3), (0.15, 0.35), (-0.15, 0.95), (-0.25, 0.3), (-0.45, -0.3)],
           c, dk, 0.06)
    p.rrect(-0.6, -0.92, 0.55, -0.7, 0.06, (150, 104, 66), dk, 0.04)
    p.line([(-0.2, -0.55), (-0.15, 0.4)], tint(c, 0.4), 0.05)


def _tendon(p, c, tier):
    dk, li = tint(c, -0.4), tint(c, 0.35)
    p.ring(0, 0.05, 0.62, c, 0.24)
    p.ring(0, 0.05, 0.62, dk, 0.04)
    for a in range(0, 360, 45):
        import math
        x, y = math.cos(math.radians(a)) * 0.62, 0.05 + math.sin(math.radians(a)) * 0.62
        p.line([(x - 0.08, y - 0.1), (x + 0.08, y + 0.1)], li, 0.05)
    p.capsule((0.45, -0.45), (0.85, -0.85), 0.12, c, dk, 0.04)


def _chaos_crystal(p, c, tier):
    cols = [c, (90, 200, 236), (236, 90, 150)]
    for (x, y, k, rot), col in zip(((-0.42, 0.2, 0.65, -25), (0.4, 0.25, 0.6, 25), (0.0, -0.1, 0.95, 0)), cols):
        q = p.sub(x, y, k, rot)
        q.poly([(0.0, -0.95), (0.32, -0.5), (0.32, 0.6), (0.0, 0.85), (-0.32, 0.6), (-0.32, -0.5)], col,
               tint(col, -0.5), 0.07)
        q.poly([(0.0, -0.95), (0.32, -0.5), (0.0, -0.3), (-0.32, -0.5)], tint(col, 0.45))
    p.sparkle(0.55, -0.6, 0.2, WHITE)


def _shard(p, c):
    dk, li = tint(c, -0.5), tint(c, 0.45)
    p.poly([(0.15, -0.92), (0.42, -0.2), (0.2, 0.3), (0.05, 0.9), (-0.25, 0.2), (-0.38, -0.35)], c, dk, 0.07)
    p.poly([(0.15, -0.92), (0.42, -0.2), (0.05, -0.05), (-0.38, -0.35)], li)
    p.sparkle(-0.45, -0.6, 0.16, tint(c, 0.7))


def _crystal(p, c):
    dk, li = tint(c, -0.5), tint(c, 0.45)
    p.poly([(-0.42, -0.45), (0.0, -0.9), (0.42, -0.45), (0.42, 0.5), (0.0, 0.92), (-0.42, 0.5)], c, dk, 0.07)
    p.poly([(-0.42, -0.45), (0.0, -0.9), (0.0, 0.92), (-0.42, 0.5)], tint(c, -0.15))
    p.poly([(0.0, -0.9), (0.42, -0.45), (0.0, -0.2), (-0.42, -0.45)], li)
    p.line([(0.0, -0.2), (0.0, 0.92)], li, 0.04)
    for x, y, r in ((0.62, -0.62, 0.18), (-0.66, 0.45, 0.13)):
        p.sparkle(x, y, r, tint(c, 0.7))


def _heart(p, c):
    dk, li = tint(c, -0.5), tint(c, 0.5)
    import math
    pts = []
    for i in range(48):
        t = 2 * math.pi * i / 48
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x / 19, y / 19 + 0.05))
    p.poly(pts, c, dk, 0.07)
    p.poly([(x * 0.55, y * 0.55 - 0.05) for x, y in pts], li)
    p.circle(0.0, -0.05, 0.14, WHITE)
    for x, y in ((-0.72, -0.72), (0.75, -0.7), (0.0, 0.92)):
        p.sparkle(x, y, 0.15, WHITE)


def _coal(p, c, tier):
    dk, li = tint(c, -0.5), tint(c, 0.4)
    p.poly([(-0.78, 0.1), (-0.5, -0.5), (0.1, -0.7), (0.7, -0.35), (0.8, 0.3), (0.35, 0.72), (-0.45, 0.65)], c,
           dk, 0.06)
    p.poly([(-0.5, -0.5), (0.1, -0.7), (0.7, -0.35), (0.05, -0.15)], li)
    crack = {1: (255, 132, 40), 2: (200, 200, 220), 3: (120, 200, 255)}[tier]
    p.line([(-0.45, 0.1), (-0.1, 0.25), (0.15, 0.05), (0.45, 0.35)], crack, 0.07)
    p.line([(-0.1, 0.25), (-0.05, 0.55)], crack, 0.05)
    if tier == 3:
        p.poly([(0.0, -0.95), (0.18, -0.65), (0.0, -0.55), (-0.18, -0.65)], crack)


def _beast_core(p, c, tier):
    dk = tint(c, -0.45)
    p.circle(0, 0.05, 0.72, c, dk, 0.07)
    p.poly([(0.0, -0.55), (0.3, -0.05), (0.18, 0.45), (-0.18, 0.45), (-0.3, -0.05)], (255, 220, 110))
    p.poly([(0.0, -0.15), (0.14, 0.15), (0.0, 0.4), (-0.14, 0.15)], WHITE)
    p.arc(0, 0.05, 0.6, 200, 250, tint(c, 0.5), 0.06)


def _sun_stone(p, c, tier):
    import math
    for i in range(12):
        a = math.radians(i * 30)
        p.poly([(math.cos(a - 0.12) * 0.55, math.sin(a - 0.12) * 0.55), (math.cos(a) * 0.95, math.sin(a) * 0.95),
                (math.cos(a + 0.12) * 0.55, math.sin(a + 0.12) * 0.55)], (255, 150, 60))
    p.circle(0, 0, 0.58, c, tint(c, -0.4), 0.06)
    p.circle(0, 0, 0.36, (255, 244, 200))


def _flask(p, c, tier):
    glass = (210, 226, 236)
    p.circle(0, 0.3, 0.6, (24, 28, 34), glass, 0.06)
    p.rrect(-0.18, -0.6, 0.18, -0.2, 0.04, (24, 28, 34), glass, 0.06)
    p.poly([(-0.55, 0.3), (0.55, 0.3), (0.5, 0.55), (0.25, 0.82), (-0.25, 0.82), (-0.5, 0.55)], c)   # liquid
    p.ellipse(0, 0.3, 0.55, 0.08, tint(c, 0.4))
    p.rrect(-0.22, -0.88, 0.22, -0.6, 0.05, (150, 104, 66), (90, 60, 34), 0.04)      # cork
    p.arc(0, 0.3, 0.45, 200, 250, WHITE, 0.06)
    if tier >= 4:
        p.sparkle(0.25, 0.55, 0.15, WHITE)


def _seal(p, c):
    red = (206, 44, 40)
    p.rrect(-0.6, -0.15, 0.6, 0.62, 0.06, (196, 178, 150), (98, 84, 70), 0.06)       # stone block
    p.poly([(-0.6, -0.15), (-0.4, -0.35), (0.8, -0.35), (0.6, -0.15)], (222, 206, 180), (98, 84, 70), 0.05)
    p.poly([(0.6, -0.15), (0.8, -0.35), (0.8, 0.42), (0.6, 0.62)], (150, 134, 112), (98, 84, 70), 0.05)
    p.circle(0.1, -0.55, 0.28, (176, 156, 128), (98, 84, 70), 0.05)                     # carved knob
    p.rrect(-0.6, 0.62, 0.6, 0.86, 0.04, red)                                         # cinnabar face
    p.rrect(-0.38, 0.05, 0.38, 0.45, 0.03, None, red, 0.07)                           # seal square
    p.line([(-0.2, 0.15), (0.2, 0.15)], red, 0.06)
    p.line([(0.0, 0.15), (0.0, 0.38)], red, 0.06)
    p.line([(-0.2, 0.38), (0.2, 0.38)], red, 0.06)


ARMOR_SHAPES = [_folded_hide, _shell_plate, _silk_roll, _scale, _qilin_hide]
BINDING_SHAPES = [_bone, _sinew, _fang, _tendon, _chaos_crystal]
FUEL_SHAPES = [_coal, _coal, _coal, _beast_core, _sun_stone]
GRADE_SHAPES = {"shard": _shard, "crystal": _crystal, "heart": _heart}


def shape_name(key):
    """What a material's icon shows (for the preview sheet and tests)."""
    parts = key.split(":")
    if parts[0] == "base":
        t = int(parts[2])
        return {"weapon": "ore chunk", "artifact": "carved jade disc"}.get(
            parts[1], ["folded hide", "shell plate", "silk roll", "scale", "qilin hide"][t - 1])
    if parts[0] == "binding":
        return ["bone", "sinew", "fang", "tendon", "chaos crystal"][int(parts[1]) - 1]
    if parts[0] == "fuel":
        return ["coal lump", "coal lump", "coal lump", "glowing core", "sun stone"][int(parts[1]) - 1]
    if parts[0] == "liquid":
        return "flask"
    if parts[0] == "essence":
        return {"shard": "shard", "crystal": "faceted crystal", "heart": "glowing heart"}[parts[2]]
    return "square seal"


def _frame_for(img, center, size, cfg, color):
    field = tint(color, -0.78)
    return frame(img, center, size, field=field, glow_color=color, **cfg)


def draw(img, key, center, size):
    """Draw one material icon (frame + shape). Unknown keys draw a Seal Stone frame with a question-free blank."""
    parts = key.split(":")
    kind = parts[0]
    if kind == "essence":
        fam, grade = parts[1], parts[2]
        c = FAMILY_COLOR.get(fam, T.GOLD)
        r = _frame_for(img, center, size, GRADE_FRAME[grade], c)
        if grade == "heart":
            glow(img, center, r * 0.8, c, 90)
        p = Pen(ImageDraw.Draw(img), center[0], center[1], r * 0.9)
        GRADE_SHAPES[grade](p, c)
        if fam == "metal":                                 # a steel edge tells Metal from Thunder and Earth
            p.line([(-0.05, -0.7), (0.3, 0.0), (0.05, 0.6)], (236, 242, 250), 0.08)
        elif fam == "thunder":                             # a small bolt on Thunder essences
            p.bolt(0.0, 0.05, 0.42, (255, 255, 236))
        if fam == "cauldron_ash":                          # embers in the ash
            p = Pen(ImageDraw.Draw(img), center[0], center[1], r * 0.9)
            for x, y in ((-0.1, 0.35), (0.12, 0.1)):
                p.circle(x, y, 0.07, (255, 132, 40))
        return
    if kind == "seal":
        r = _frame_for(img, center, size, SEAL_FRAME, T.GOLD)
        _seal(Pen(ImageDraw.Draw(img), center[0], center[1], r * 0.9), T.GOLD)
        return
    tier = int(parts[-1])
    r = _frame_for(img, center, size, TIER_FRAME[tier - 1], tier_color(tier))
    p = Pen(ImageDraw.Draw(img), center[0], center[1], r * 0.88)
    if kind == "base":
        gear = parts[1]
        if gear == "weapon":
            _ore(p, METAL_COLORS[tier - 1], tier)
        elif gear == "armor":
            ARMOR_SHAPES[tier - 1](p, ARMOR_COLORS[tier - 1], tier)
        else:
            _jade_disc(p, JADE_COLORS[tier - 1], tier)
    elif kind == "binding":
        BINDING_SHAPES[tier - 1](p, BINDING_COLORS[tier - 1], tier)
    elif kind == "fuel":
        if tier >= 4:
            glow(img, center, r * 0.7, FUEL_COLORS[tier - 1], 140)
        FUEL_SHAPES[tier - 1](p, FUEL_COLORS[tier - 1], tier)
    elif kind == "liquid":
        _flask(p, LIQUID_COLORS[tier - 1], tier)


# ── passive rarity emblems ────────────────────────────────────────────

RARITY_FRAME = {
    "Common":    dict(shape="circle", mat="iron", glow_strength=0),
    "Uncommon":  dict(shape="hex", mat="bronze", glow_strength=50, studs=6),
    "Rare":      dict(shape="oct", mat="jadeblue", glow_strength=110),
    "Epic":      dict(shape="star8", mat="gold", glow_strength=150),
    "Legendary": dict(shape="star8", mat="gold", glow_strength=190, rays=16),
    "Mythical":  dict(shape="star8", mat="radiant", glow_strength=240, halo=True, rays=16),
}


def passive_emblem(img, rarity, center, size):
    """A forged rune crest in the rarity's colour; each rarity has a richer frame and more sparks."""
    c = forge.RARITY_COLORS[rarity]
    step = forge.RARITIES.index(rarity)
    r = _frame_for(img, center, size, RARITY_FRAME[rarity], c)
    p = Pen(ImageDraw.Draw(img), center[0], center[1], r * 0.9)
    li = tint(c, 0.45)
    # the rune: a diamond with a crossbar and a hammered stroke, the mark a forge inscription leaves
    p.poly([(0.0, -0.75), (0.42, 0.0), (0.0, 0.75), (-0.42, 0.0)], tint(c, -0.2), li, 0.08)
    p.line([(-0.6, 0.0), (0.6, 0.0)], li, 0.1)
    p.line([(0.0, -0.45), (0.0, 0.45)], WHITE if step >= 4 else li, 0.08)
    for x, y in [(-0.62, -0.6), (0.62, -0.6), (0.62, 0.6), (-0.62, 0.6)][:max(0, step - 1)]:
        p.sparkle(x, y, 0.18, WHITE if step >= 4 else li)
