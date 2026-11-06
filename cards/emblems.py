"""
Drawn emblems for tiers, beasts, elements and pills (instead of seal characters like 凡 黄 虎 霜).

    emblem(img, kind, key, center, size)

kind   key
grade       Mortal · Yellow · Mystic · Earth · Heaven                 manual grades: scrolls and tablets
rarity      ordinary · refined · spirit · treasure · divine            gear rarities: forged crests
realm       Mortal … Martial Saint                                     the realm's signature beast
beast_tier  normal · elite · beast_king                               paw, claw marks, fanged crown
element     Blood · Frost · Flame · Shadow · Thunder · Venom · Earth · Jade
pill        qi · burst · mending · cleansing · breakthrough            pass grade= (and patterns=, corner=)
beast       (realm, element)                                           realm emblem + element badge in the corner
book        any                                                        an open book (the Compendium)

Within each set, every step looks clearly more precious or dangerous than the one before: the frame
shape, the material and the glow all step up. `size` is the full width in card pixels; fine details
(sparks, rays, studs, patterns) are only drawn when the emblem is large, so small ones stay bold.
Pillow only, no image files.
"""
import math

from PIL import ImageDraw

from . import theme as T
from .drawkit import Pen, glow, tint

WHITE = (255, 255, 255)
VOIDC = (10, 6, 7)

# ── materials: (dark, base, light) ────────────────────────────────────
MAT = {
    "iron":     ((44, 44, 50), (112, 112, 120), (176, 176, 186)),
    "wood":     ((58, 34, 16), (128, 82, 42), (184, 136, 84)),
    "bronze":   ((74, 44, 20), (168, 110, 54), (232, 176, 104)),
    "yellow":   ((88, 66, 18), (196, 160, 62), (250, 222, 130)),
    "jadeblue": ((16, 44, 74), (66, 138, 200), (164, 214, 250)),
    "jade":     ((14, 60, 48), (60, 160, 124), (156, 232, 198)),
    "gold":     ((96, 62, 16), (210, 166, 80), (255, 230, 160)),
    "radiant":  ((128, 84, 20), (244, 200, 100), (255, 248, 214)),
}

GRADES = ["Mortal", "Yellow", "Mystic", "Earth", "Heaven"]
RARITIES = ["ordinary", "refined", "spirit", "treasure", "divine"]
REALMS = ["Mortal", "Martial Apprentice", "Martial Warrior", "Martial Expert", "Martial Master",
          "Grand Martial Master", "Martial Grandmaster", "Martial King", "Martial Emperor", "Martial Ancestor",
          "Martial Saint"]
BEAST_TIERS = ["normal", "elite", "beast_king"]
ELEMENTS = ["Blood", "Frost", "Flame", "Shadow", "Thunder", "Venom", "Earth", "Jade"]
PILLS = ["qi", "burst", "mending", "cleansing", "breakthrough"]
PILL_ALIASES = {"qi_burst": "burst", "healing": "mending", "heal": "mending", "purity": "cleansing"}

REALM_COLOR = dict(zip(REALMS, [
    (170, 160, 150), (150, 190, 120), (96, 196, 110), (82, 186, 170), (90, 160, 240), (120, 130, 240),
    (178, 110, 228), (232, 196, 80), (246, 150, 50), (236, 90, 60), (250, 226, 180)]))
TIER_COLOR = {"normal": T.ASH, "elite": (226, 64, 52), "beast_king": (246, 196, 70)}


def element_color(name):
    a = T.ELEMENT_ACCENTS.get(name)
    return a.rim if a else T.GOLD


# ── frames ────────────────────────────────────────────────────────────

def _shape_pts(shape, cx, cy, r):
    """Outline of a frame shape in card pixels."""
    if shape == "circle":
        n, turn, star = 48, 0, None
    elif shape == "hex":
        n, turn, star = 6, -90, None
    elif shape == "oct":
        n, turn, star = 8, -22.5, None
    elif shape.startswith("star"):
        n, turn, star = int(shape[4:] or 8), -90, 0.72
    else:
        n, turn, star = 48, 0, None
    pts = []
    if star:
        for i in range(2 * n):
            rr = r if i % 2 == 0 else r * star
            a = math.radians(turn + i * 180 / n)
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    else:
        for i in range(n):
            a = math.radians(turn + i * 360 / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def _poly(d, pts, fill=None, outline=None, width=1.0):
    q = [T.P(x, y) for x, y in pts]
    if fill is not None:
        d.polygon(q, fill=fill)
    if outline is not None:
        d.line(q + [q[0]], fill=outline, width=max(1, round(width * T.S)), joint="curve")


def frame(img, center, size, shape, mat, field, glow_color=None, glow_strength=0, studs=0, double=False,
          rays=0, spikes=0, notch=False, halo=False):
    """Draw an emblem frame and return the radius left for the symbol inside."""
    cx, cy = center
    r = size / 2
    big = size >= 48
    dk, base, li = MAT[mat]
    if glow_color and glow_strength:
        glow(img, center, r * (1.05 + glow_strength / 400), glow_color, glow_strength)
    d = ImageDraw.Draw(img)
    if halo:
        for k in range(2 if big else 1):
            rr = r * (0.98 - k * 0.05)
            d.ellipse(T.P(cx - rr, cy - rr, cx + rr, cy + rr), outline=tint(li, 0.3),
                      width=max(1, round(size * 0.03 * T.S)))
        r *= 0.86
    if rays:
        for i in range(rays):
            a = math.radians(-90 + i * 360 / rays)
            long = 1.0 if i % 2 == 0 else 0.88
            w = math.radians(7 if i % 2 == 0 else 5)
            _poly(d, [(cx + math.cos(a - w) * r * 0.7, cy + math.sin(a - w) * r * 0.7),
                      (cx + math.cos(a) * r * long, cy + math.sin(a) * r * long),
                      (cx + math.cos(a + w) * r * 0.7, cy + math.sin(a + w) * r * 0.7)], fill=li)
        r *= 0.8
    if spikes:
        for i in range(spikes):
            a = math.radians(-90 + 180 / spikes + i * 360 / spikes)
            w = math.radians(180 / spikes * 0.55)
            _poly(d, [(cx + math.cos(a - w) * r * 0.8, cy + math.sin(a - w) * r * 0.8),
                      (cx + math.cos(a) * r, cy + math.sin(a) * r),
                      (cx + math.cos(a + w) * r * 0.8, cy + math.sin(a + w) * r * 0.8)], fill=base, outline=dk,
                  width=0.8)
        r *= 0.86
    outer = _shape_pts(shape, cx, cy, r)
    _poly(d, _shape_pts(shape, cx + size * 0.012, cy + size * 0.03, r), fill=(0, 0, 0, 255))   # drop shadow
    _poly(d, outer, fill=base, outline=dk, width=max(1.0, size * 0.025))
    rim = 0.18 if double else 0.14
    _poly(d, _shape_pts(shape, cx, cy, r * (1 - rim * 0.45)), outline=li, width=max(0.8, size * 0.012))
    inner_r = r * (1 - rim)
    if double:
        _poly(d, _shape_pts(shape, cx, cy, inner_r), fill=dk)
        inner_r *= 0.9
    _poly(d, _shape_pts(shape if not shape.startswith("star") else "circle", cx, cy,
                        inner_r * (0.9 if shape.startswith("star") else 1)), fill=field, outline=dk,
          width=max(0.8, size * 0.015))
    if shape.startswith("star"):
        inner_r *= 0.9
    if notch:
        d.rectangle(T.P(cx - size * 0.05, cy - r - 1, cx + size * 0.05, cy - r + size * 0.1), fill=dk)
    if studs and size >= 22:
        sr = max(1.2, size * 0.035)
        for i in range(studs):
            a = math.radians(-90 + i * 360 / studs + (180 / studs if shape == "hex" else 0))
            sx, sy = cx + math.cos(a) * r * (1 - rim * 0.5), cy + math.sin(a) * r * (1 - rim * 0.5)
            d.ellipse(T.P(sx - sr, sy - sr, sx + sr, sy + sr), fill=li, outline=dk)
    return inner_r


def _pen(img, center, r):
    return Pen(ImageDraw.Draw(img), center[0], center[1], r)


# ── 1. manual grades: scrolls and tablets ─────────────────────────────

def _grade(img, key, center, size):
    c = T.RARITY.get(key, T.GOLD)
    big = size >= 48
    cfg = {
        "Mortal": dict(shape="circle", mat="iron", glow_strength=0),
        "Yellow": dict(shape="hex", mat="yellow", glow_strength=70),
        "Mystic": dict(shape="oct", mat="jadeblue", glow_strength=120),
        "Earth":  dict(shape="oct", mat="bronze", glow_strength=150, studs=8, double=True),
        "Heaven": dict(shape="star8", mat="radiant", glow_strength=210, rays=16 if big else 8),
    }[key]
    field = tint(c, -0.72)
    r = frame(img, center, size, field=field, glow_color=c, **cfg)
    p = _pen(img, center, r * 0.95)
    if key == "Mortal":
        bamboo = (196, 176, 128)
        for i, x in enumerate((-0.48, -0.24, 0.0, 0.24, 0.48)):
            p.rrect(x - 0.1, -0.72, x + 0.1, 0.72, 0.06, tint(bamboo, -0.08 * (i % 2)))
            if big:
                p.line([(x, -0.45), (x, 0.4)], tint(bamboo, -0.35), 0.03)
        p.line([(-0.68, -0.25), (0.68, -0.25)], (120, 92, 60), 0.09)
        p.line([(-0.68, 0.3), (0.68, 0.3)], (120, 92, 60), 0.09)
        p.line([(0.6, 0.3), (0.82, 0.62)], (120, 92, 60), 0.06)
    elif key == "Yellow":
        paper = (244, 210, 92)
        p.poly([(-0.36, -0.68), (0.36, -0.68), (0.36, 0.72), (0.0, 0.88), (-0.36, 0.72)], paper)
        red = (214, 40, 36)
        p.line([(0.0, -0.95), (0.0, -0.68)], red, 0.08)
        p.circle(0.0, -0.98, 0.09, red)
        p.line([(-0.18, -0.42), (0.18, -0.42)], red, 0.09)
        p.line([(0.0, -0.42), (0.0, 0.35), (-0.15, 0.55)], red, 0.08)
        if big:
            p.line([(-0.2, -0.05), (0.2, -0.15)], red, 0.06)
            p.line([(-0.2, 0.15), (0.2, 0.05)], red, 0.06)
            p.circle(0.0, 0.62, 0.07, red)
    elif key == "Mystic":
        paper = (200, 220, 246)
        roll = (54, 92, 170)
        p.poly([(-0.62, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.62, 0.5)], paper)
        p.rrect(0.42, -0.66, 0.72, 0.66, 0.15, roll)
        p.rrect(-0.78, -0.62, -0.56, 0.62, 0.11, roll)
        # taiji
        tx, ty, tr = -0.06, 0.0, 0.3
        p.circle(tx, ty, tr, (24, 36, 70))
        p.poly([(tx + math.cos(math.radians(a)) * tr, ty + math.sin(math.radians(a)) * tr) for a in range(-90, 91, 10)]
               + [(tx + math.cos(math.radians(a)) * tr / 2, ty + tr / 2 + math.sin(math.radians(a)) * tr / 2)
                  for a in range(90, -91, -15)]
               + [(tx + math.cos(math.radians(a)) * tr / 2, ty - tr / 2 + math.sin(math.radians(a)) * tr / 2)
                  for a in range(90, 271, 15)], WHITE)
        if big:
            p.circle(tx, ty - tr / 2, 0.05, (24, 36, 70))
            p.circle(tx, ty + tr / 2, 0.05, WHITE)
        mist = tint(c, 0.4)
        p.wave(-0.95, 0.2, 0.78, 0.05, mist, 0.08, waves=1.5)
        if big:
            p.wave(-0.5, 0.9, -0.8, 0.05, mist, 0.06, waves=1.5, phase=1)
    elif key == "Earth":
        stone = (150, 140, 128)
        p.poly([(-0.52, 0.82), (-0.52, -0.42), (-0.3, -0.75), (0.3, -0.75), (0.52, -0.42), (0.52, 0.82)], stone)
        p.rrect(-0.68, 0.7, 0.68, 0.9, 0.05, tint(stone, -0.3))
        carve = (82, 70, 60)
        p.poly([(-0.36, 0.42), (-0.12, -0.05), (0.0, 0.1), (0.12, -0.32), (0.38, 0.42)], carve)
        p.poly([(0.06, -0.22), (0.12, -0.32), (0.19, -0.2)], (236, 228, 214))
        if big:
            p.line([(-0.36, -0.52), (0.36, -0.52)], carve, 0.04)
            p.line([(0.3, 0.5), (0.4, 0.62)], tint(stone, -0.25), 0.03)
    else:   # Heaven
        sun = (255, 214, 110)
        if big:
            for i in range(12):
                a = math.radians(i * 30)
                p.line([(math.cos(a) * 0.35, -0.2 + math.sin(a) * 0.35), (math.cos(a) * 0.62, -0.2 + math.sin(a) * 0.62)],
                       tint(sun, 0.3), 0.05)
        p.circle(0.0, -0.2, 0.32, sun)
        gold = (246, 200, 90)
        p.rrect(-0.62, -0.08, 0.62, 0.32, 0.06, tint(gold, 0.35))
        p.rrect(-0.78, -0.16, -0.56, 0.4, 0.1, gold)
        p.rrect(0.56, -0.16, 0.78, 0.4, 0.1, gold)
        p.cloud(-0.42, 0.62, 0.38, (250, 246, 236))
        p.cloud(0.45, 0.6, 0.32, (236, 232, 222))


# ── 2. gear rarities: forged crests ───────────────────────────────────

def _rarity(img, key, center, size):
    c = T.RARITY.get(key, T.GOLD)
    big = size >= 48
    cx, cy = center
    if key == "divine":
        p = _pen(img, center, size / 2)
        glow(img, center, size * 0.6, c, 230)
        p = _pen(img, center, size / 2)
        wing = (255, 236, 196)
        for sd in (-1, 1):
            for i in range(4 if big else 3):
                y = -0.32 + i * 0.2
                p.poly([(sd * 0.35, y + 0.1), (sd * (1.0 - i * 0.12), y - 0.22 + i * 0.05),
                        (sd * (0.92 - i * 0.12), y + 0.08), (sd * 0.4, y + 0.28)], tint(wing, -0.08 * i))
        r = frame(img, center, size * 0.74, "star8", "radiant", tint(c, -0.68), c, 0, halo=True)
    else:
        cfg = {
            "ordinary": dict(shape="circle", mat="iron", glow_strength=0, notch=True),
            "refined":  dict(shape="hex", mat="bronze", glow_strength=40, studs=6),
            "spirit":   dict(shape="oct", mat="jadeblue", glow_strength=120),
            "treasure": dict(shape="star8", mat="gold", glow_strength=160),
        }[key]
        r = frame(img, center, size, field=tint(c, -0.74) if key != "ordinary" else (26, 26, 30), glow_color=c,
                  **cfg)
    p = _pen(img, center, r * 0.95)
    if key == "ordinary":
        p.ring(0, 0, 0.5, (96, 96, 104), 0.16)
        if big:
            p.circle(0, 0, 0.12, (96, 96, 104))
    elif key == "refined":
        # an anvil with one forge spark
        p.poly([(-0.7, -0.22), (0.5, -0.22), (0.72, -0.05), (0.3, 0.05), (0.2, 0.3), (0.4, 0.55), (-0.45, 0.55),
                (-0.25, 0.3), (-0.35, 0.05), (-0.62, 0.0)], (150, 118, 82))
        p.sparkle(0.25, -0.58, 0.32, tint(c, 0.4))
        if big:
            p.sparkle(-0.3, -0.62, 0.14, tint(c, 0.6))
    elif key == "spirit":
        wisp = tint(c, 0.25)
        p.poly([(0.0, -0.9), (0.22, -0.45), (0.5, -0.2), (0.48, 0.3), (0.0, 0.62), (-0.48, 0.3), (-0.42, -0.15),
                (-0.2, 0.05), (-0.18, -0.4)], wisp)
        p.poly([(0.02, -0.3), (0.2, 0.05), (0.18, 0.32), (0.0, 0.45), (-0.2, 0.3), (-0.12, 0.0)], tint(c, 0.7))
        if big:
            for x, y in ((-0.6, -0.55), (0.62, -0.62), (0.68, 0.45)):
                p.circle(x, y, 0.06, tint(c, 0.6))
    elif key == "treasure":
        gem = c
        p.poly([(-0.55, -0.15), (-0.28, -0.5), (0.28, -0.5), (0.55, -0.15), (0.0, 0.62)], gem)
        p.poly([(-0.55, -0.15), (0.55, -0.15), (0.0, 0.62)], tint(gem, -0.25))
        p.poly([(-0.28, -0.5), (0.0, -0.15), (0.28, -0.5)], tint(gem, 0.35))
        if big:
            p.line([(-0.28, -0.15), (0.0, 0.62), (0.28, -0.15)], tint(gem, 0.2), 0.03)
            p.sparkle(0.42, -0.5, 0.2, WHITE)
    else:   # divine: a flame crowned sun crest
        fl = (255, 200, 90)
        p.poly([(0.0, -0.95), (0.25, -0.45), (0.5, -0.65), (0.55, -0.1), (0.3, 0.45), (-0.3, 0.45), (-0.55, -0.1),
                (-0.5, -0.65), (-0.25, -0.45)], c)
        p.poly([(0.0, -0.45), (0.22, 0.0), (0.12, 0.38), (-0.12, 0.38), (-0.22, 0.0)], fl)
        p.circle(0.0, 0.15, 0.16, WHITE)
        if big:
            for x, y in ((-0.75, -0.75), (0.78, -0.7), (0.0, 0.8)):
                p.sparkle(x, y, 0.16, (255, 246, 214))


# ── 3a. realm emblems: the realm's signature beast ────────────────────

REALM_FRAME = [
    dict(shape="circle", mat="wood"),
    dict(shape="circle", mat="wood", studs=4),
    dict(shape="hex", mat="wood", studs=6),
    dict(shape="oct", mat="wood", studs=8, double=True),
    dict(shape="circle", mat="jade", studs=4, glow_strength=60),
    dict(shape="hex", mat="jade", studs=6, glow_strength=80),
    dict(shape="oct", mat="jade", studs=8, double=True, glow_strength=100),
    dict(shape="oct", mat="jade", studs=8, double=True, spikes=8, glow_strength=120),
    dict(shape="oct", mat="gold", studs=8, double=True, spikes=8, glow_strength=150),
    dict(shape="circle", mat="gold", studs=12, double=True, spikes=12, glow_strength=180),
    dict(shape="star8", mat="radiant", double=True, rays=16, halo=True, glow_strength=220),
]


def _boar(p, c, dk, big):
    p.ellipse(0, 0.0, 0.62, 0.55, c)
    for sd in (-1, 1):
        p.poly([(sd * 0.4, -0.4), (sd * 0.72, -0.85), (sd * 0.62, -0.3)], c)
    p.ellipse(0, 0.32, 0.34, 0.24, tint(c, 0.2))
    p.circle(-0.12, 0.32, 0.06, dk)
    p.circle(0.12, 0.32, 0.06, dk)
    for sd in (-1, 1):
        p.poly([(sd * 0.3, 0.42), (sd * 0.58, 0.3), (sd * 0.72, -0.05), (sd * 0.62, 0.32), (sd * 0.38, 0.55)], WHITE)
        p.circle(sd * 0.26, -0.12, 0.07, dk)


def _wolf(p, c, dk, big):
    p.poly([(-0.62, -0.25), (-0.58, -0.9), (-0.22, -0.48), (0.22, -0.48), (0.58, -0.9), (0.62, -0.25), (0.55, 0.15),
            (0.22, 0.42), (0.12, 0.85), (-0.12, 0.85), (-0.22, 0.42), (-0.55, 0.15)], c)
    p.poly([(-0.45, -0.38), (-0.44, -0.7), (-0.28, -0.46)], dk)
    p.poly([(0.45, -0.38), (0.44, -0.7), (0.28, -0.46)], dk)
    for sd in (-1, 1):
        p.poly([(sd * 0.36, -0.12), (sd * 0.14, -0.05), (sd * 0.3, 0.02)], (255, 220, 120))
    p.ellipse(0, 0.78, 0.12, 0.08, dk)
    if big:
        p.line([(0, 0.2), (0, 0.65)], tint(c, -0.3), 0.04)


def _claws(p, c, dk, big, n=3, red=None):
    for i in range(n):
        x = -0.48 + i * (0.96 / max(1, n - 1)) if n > 1 else 0
        pts = [(x - 0.3, -0.85), (x - 0.18, -0.85), (x + 0.32, 0.85), (x + 0.22, 0.85)]
        pts = [(x - 0.32, -0.82), (x - 0.18, -0.86), (x + 0.3, 0.86), (x + 0.24, 0.88)]
        if red:
            p.poly([(a + 0.05, b + 0.02) for a, b in pts], red)
        p.poly(pts, c)


def _scorpion(p, c, dk, big):
    segs = [(-0.45, 0.7), (-0.6, 0.3), (-0.6, -0.12), (-0.42, -0.5), (-0.08, -0.72), (0.3, -0.66), (0.52, -0.38)]
    for i, (x, y) in enumerate(segs):
        p.circle(x, y, 0.2 - i * 0.012, c)
        if big and i:
            p.circle(x, y, 0.05, tint(c, -0.4))
    p.poly([(0.5, -0.4), (0.8, -0.2), (0.62, 0.0), (0.55, 0.3), (0.45, 0.0)], tint(c, 0.3))
    p.poly([(0.55, 0.28), (0.66, 0.1), (0.48, 0.55)], (226, 70, 60))


def _lion(p, c, dk, big):
    n = 16
    for i in range(n):
        a = math.radians(i * 360 / n)
        p.poly([(math.cos(a - 0.25) * 0.5, math.sin(a - 0.25) * 0.5), (math.cos(a) * 0.95, math.sin(a) * 0.95),
                (math.cos(a + 0.25) * 0.5, math.sin(a + 0.25) * 0.5)], tint(c, -0.15))
    p.circle(0, 0, 0.6, tint(c, -0.15))
    p.ellipse(0, 0.05, 0.42, 0.48, c)
    for sd in (-1, 1):
        p.poly([(sd * 0.28, -0.12), (sd * 0.1, -0.06), (sd * 0.24, 0.0)], dk)
    p.poly([(-0.12, 0.2), (0.12, 0.2), (0.0, 0.32)], dk)
    p.arc(0, 0.32, 0.15, 20, 160, dk, 0.05)


def _serpent(p, c, dk, big):
    p.spiral(0.05, 0.12, 0.72, c, 0.22, turns=1.7)
    p.ellipse(0.1, -0.02, 0.2, 0.15, c)
    p.circle(0.15, -0.06, 0.05, (255, 220, 100))
    p.line([(-0.08, 0.02), (-0.24, 0.0), (-0.3, -0.06)], (226, 70, 60), 0.04)


def _jiao(p, c, dk, big):
    pts = [(-0.75, 0.8), (-0.35, 0.55), (-0.5, 0.15), (-0.1, -0.05), (0.0, -0.35), (0.25, -0.5)]
    for i in range(len(pts) - 1):
        p.capsule(pts[i], pts[i + 1], 0.3 - i * 0.03, c)
        if big:
            p.circle((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2, 0.05, tint(c, 0.4))
    p.poly([(0.08, -0.62), (0.45, -0.72), (0.85, -0.5), (0.72, -0.32), (0.4, -0.3), (0.12, -0.32)], c)
    p.circle(0.42, -0.55, 0.06, (255, 220, 100))
    p.line([(0.78, -0.4), (0.92, -0.05)], tint(c, 0.4), 0.04)
    for x, y in ((-0.5, 0.15), (-0.1, -0.05)):
        p.poly([(x - 0.06, y - 0.12), (x + 0.04, y - 0.38), (x + 0.12, y - 0.1)], tint(c, 0.3))


def _qilin(p, c, dk, big):
    # a head in profile with one tall spiralled horn and flame curls
    p.poly([(-0.6, 0.85), (-0.5, 0.1), (-0.2, -0.25), (0.25, -0.25), (0.65, 0.05), (0.7, 0.3), (0.3, 0.35),
            (0.0, 0.5), (-0.1, 0.85)], c)
    p.poly([(-0.08, -0.22), (0.05, -0.98), (0.18, -0.22)], tint(c, 0.4))
    for y in (-0.4, -0.6, -0.78):
        p.line([(0.0 + (y + 1) * 0.05, y), (0.12 - (y + 1) * 0.04, y - 0.07)], tint(c, -0.3), 0.04)
    p.circle(0.22, -0.05, 0.06, (255, 220, 100))
    for x, y in ((-0.72, -0.1), (-0.78, 0.35)):
        p.arc(x, y, 0.16, 90, 360, (255, 160, 70), 0.07)


def _taotie(p, c, dk, big):
    p.poly([(-0.9, -0.3), (-0.5, -0.6), (0.0, -0.4), (0.5, -0.6), (0.9, -0.3), (0.7, 0.4), (0.3, 0.75), (-0.3, 0.75),
            (-0.7, 0.4)], c)
    for sd in (-1, 1):
        p.arc(sd * 0.68, -0.68, 0.22, 90 if sd > 0 else 180, 360 if sd > 0 else 450, c, 0.12)
        p.ellipse(sd * 0.36, -0.12, 0.2, 0.14, VOIDC)
        p.circle(sd * 0.36, -0.12, 0.07, (255, 90, 60))
    p.poly([(-0.12, -0.3), (0.12, -0.3), (0.06, 0.2), (-0.06, 0.2)], dk)
    p.rrect(-0.42, 0.32, 0.42, 0.55, 0.08, VOIDC)
    for x in (-0.28, -0.1, 0.1, 0.28):
        p.poly([(x - 0.06, 0.32), (x + 0.06, 0.32), (x, 0.46)], WHITE)
    if big:
        p.line([(-0.6, 0.1), (-0.3, 0.2)], dk, 0.04)
        p.line([(0.6, 0.1), (0.3, 0.2)], dk, 0.04)


def _tortoise(p, c, dk, big):
    shell = tint(c, -0.45)
    for x, y in ((-0.6, -0.55), (0.6, -0.55), (-0.6, 0.55), (0.6, 0.55)):
        p.circle(x, y, 0.16, shell)
    p.circle(0, -0.86, 0.15, shell)
    p.ellipse(0, 0.0, 0.7, 0.8, shell)
    p.ellipse(0, 0.0, 0.58, 0.68, c)
    p.ngon(0, 0, 6, 0.24, tint(c, -0.2), dk, 0.05, turn=0)
    for i in range(6):
        a = math.radians(i * 60)
        p.line([(math.cos(a) * 0.24, math.sin(a) * 0.24), (math.cos(a) * 0.56, math.sin(a) * 0.66)], dk, 0.05)


def _kunpeng(p, c, dk, big):
    for sd in (-1, 1):
        for i in range(5):
            a = math.radians(-160 + i * 22) if sd < 0 else math.radians(-20 - i * 22)
            p.capsule((sd * 0.1, 0.05), (math.cos(a) * 0.95, 0.05 + math.sin(a) * 0.8 * 0.95 + i * 0.12),
                      0.2 - i * 0.015, tint(c, -0.05 * i))
    p.ellipse(0, 0.1, 0.16, 0.42, tint(c, 0.25))
    p.circle(0, -0.35, 0.13, tint(c, 0.25))
    p.poly([(-0.18, 0.45), (0.0, 0.85), (0.18, 0.45)], tint(c, 0.1))


REALM_BEAST = [_boar, _wolf, lambda p, c, dk, big: _claws(p, c, dk, big), _scorpion, _lion, _serpent, _jiao, _qilin,
               _taotie, _tortoise, _kunpeng]
REALM_BEAST_NAME = ["Boar tusks", "Wolf head", "Tiger claw slashes", "Scorpion tail", "Lion mane", "Coiled serpent",
                    "Flood dragon", "Qilin horn", "Taotie mask", "Black tortoise shell", "Kun-Peng wings"]


def _realm(img, key, center, size):
    i = REALMS.index(key) if key in REALMS else 0
    cfg = dict(REALM_FRAME[i])
    c = REALM_COLOR.get(key, T.GOLD)
    if size < 48:
        cfg.pop("rays", None)
        cfg["spikes"] = min(cfg.get("spikes", 0), 8)
    gs = cfg.pop("glow_strength", 0)
    r = frame(img, center, size, field=tint(c, -0.75), glow_color=c, glow_strength=gs, **cfg)
    p = _pen(img, center, r * 0.92)
    REALM_BEAST[i](p, tint(c, 0.15), tint(c, -0.6), size >= 48)


# ── 3b. beast tiers ───────────────────────────────────────────────────

def _beast_tier(img, key, center, size):
    c = TIER_COLOR.get(key, T.ASH)
    big = size >= 48
    if key == "normal":
        r = frame(img, center, size, "circle", "iron", (30, 28, 30))
        p = _pen(img, center, r * 0.9)
        p.ellipse(0, 0.32, 0.45, 0.38, c)
        for x, y in ((-0.6, -0.12), (-0.24, -0.55), (0.24, -0.55), (0.6, -0.12)):
            p.ellipse(x, y, 0.18, 0.22, c)
    elif key == "elite":
        r = frame(img, center, size, "hex", "bronze", (40, 12, 12), c, 90, studs=6)
        p = _pen(img, center, r * 0.9)
        for sd in (-1, 1):
            for i in range(3):
                off = (i - 1) * 0.28
                pts = [(sd * -0.6 + off, -0.7), (sd * -0.5 + off, -0.74), (sd * 0.6 + off, 0.72), (sd * 0.52 + off, 0.76)]
                p.poly([(a + 0.05, b + 0.03) for a, b in pts], c)
                p.poly(pts, (236, 226, 214))
    else:   # beast king: fanged crown with glowing eyes
        r = frame(img, center, size, "star8", "gold", (40, 20, 8), c, 200, rays=16 if big else 0)
        p = _pen(img, center, r * 0.95)
        p.poly([(-0.72, 0.1), (-0.72, -0.62), (-0.36, -0.25), (0.0, -0.75), (0.36, -0.25), (0.72, -0.62), (0.72, 0.1)],
               c)
        for x in (-0.72, 0.0, 0.72):
            p.circle(x, -0.68 if x else -0.8, 0.1, (255, 240, 180))
        p.rrect(-0.72, 0.0, 0.72, 0.3, 0.04, tint(c, -0.3))
        for x in (-0.42, 0.42):
            p.poly([(x - 0.13, 0.28), (x + 0.13, 0.28), (x, 0.8)], WHITE)
        for x in (-0.3, 0.3):
            p.ellipse(x, -0.12, 0.13, 0.07, (255, 70, 50))
        if big:
            glow(img, center, r * 0.22, (255, 80, 60), 160)


# ── 3c. element badges ────────────────────────────────────────────────

def _element(img, key, center, size):
    c = element_color(key)
    big = size >= 48
    r = frame(img, center, size, "circle", "iron" if size < 48 else "bronze", tint(c, -0.78), c,
              90 if big else 0)
    p = _pen(img, center, r * 0.9)
    li = tint(c, 0.35)
    if key == "Blood":
        p.poly([(0, -0.85)] + [(math.cos(math.radians(a)) * 0.5, 0.25 + math.sin(math.radians(a)) * 0.5)
                               for a in range(-30, 211, 10)], c)
        if big:
            p.ellipse(-0.2, 0.25, 0.08, 0.16, li)
    elif key == "Frost":
        for i in range(3):
            a = math.radians(90 + i * 60)
            ux, uy = math.cos(a) * 0.85, math.sin(a) * 0.85
            p.line([(-ux, -uy), (ux, uy)], li, 0.12)
            for sgn in (-1, 1):
                bx, by = ux * 0.55 * sgn, uy * 0.55 * sgn
                for t in (-1, 1):
                    b = a + (math.pi if sgn < 0 else 0) + t * math.radians(40)
                    p.line([(bx, by), (bx + math.cos(b) * -0.25, by + math.sin(b) * -0.25)], li, 0.08)
    elif key == "Flame":
        p.poly([(0, -0.9), (0.35, -0.3), (0.55, -0.45), (0.6, 0.2), (0.35, 0.7), (-0.35, 0.7), (-0.6, 0.2),
                (-0.45, -0.25), (-0.2, -0.1)], c)
        p.poly([(0.0, -0.2), (0.25, 0.25), (0.15, 0.6), (-0.15, 0.6), (-0.25, 0.25)], (255, 230, 150))
    elif key == "Shadow":
        p.poly([(-0.85, 0.0)] + [(math.cos(math.radians(a)) * 0.85, math.sin(math.radians(a)) * 0.55 + 0.0)
                                 for a in range(-180, 1, 10)] + [(0.85, 0.0)], c)
        p.poly([(-0.85, 0.0)] + [(math.cos(math.radians(a)) * 0.85, math.sin(math.radians(a)) * 0.55)
                                 for a in range(180, -1, -10)], tint(c, -0.6))
        p.circle(0, -0.05, 0.28, VOIDC)
        p.circle(0, -0.05, 0.12, li)
        p.line([(-0.9, 0.05), (0.9, 0.05)], tint(c, -0.4), 0.1)
    elif key == "Thunder":
        p.bolt(0, 0, 0.9, c)
        if big:
            p.bolt(0, 0, 0.55, WHITE)
    elif key == "Venom":
        p.poly([(-0.42, -0.8), (0.42, -0.8), (0.3, -0.2), (0.0, 0.42), (-0.08, -0.1), (-0.3, -0.35)], (236, 232, 214))
        p.poly([(0.0, 0.48)] + [(math.cos(math.radians(a)) * 0.18, 0.72 + math.sin(math.radians(a)) * 0.18)
                                for a in range(-30, 211, 15)], c)
        if big:
            p.circle(0.3, 0.55, 0.07, c)
    elif key == "Earth":
        p.poly([(-0.8, 0.6), (-0.65, -0.2), (-0.25, -0.65), (0.4, -0.55), (0.8, -0.05), (0.7, 0.6)], c)
        p.line([(-0.05, -0.62), (0.08, -0.2), (-0.12, 0.1), (0.05, 0.6)], VOIDC, 0.09)
        p.line([(0.08, -0.2), (0.45, -0.05)], VOIDC, 0.06)
    else:   # Jade: a water wave
        p.poly([(-0.9, 0.65), (-0.9, 0.1), (-0.5, -0.45), (0.0, -0.7), (0.45, -0.55), (0.5, -0.2), (0.2, -0.3),
                (0.0, -0.1), (0.2, 0.15), (0.6, 0.1), (0.9, 0.3), (0.9, 0.65)], c)
        p.arc(0.15, -0.28, 0.2, 180, 360, li, 0.07)
        if big:
            p.wave(-0.8, 0.8, 0.45, 0.05, li, 0.05)


# ── 4. pills ──────────────────────────────────────────────────────────

GRADE_GLOW = {"Mortal": 0, "Yellow": 60, "Mystic": 110, "Earth": 160, "Heaven": 220}


def pill_rings(img, center, r0, step, earned, total=9, color=T.GOLD_HI):
    """Pill patterns (丹纹): one bright ring per earned pattern, as on the /craft card."""
    cx, cy = center
    d = ImageDraw.Draw(img)
    for i in range(min(earned, total)):
        r = r0 + step * (i + 1)
        d.ellipse(T.P(cx - r, cy - r, cx + r, cy + r), outline=T.alpha(color, 235),
                  width=max(1, round(max(1.0, step * 0.32) * T.S)))


def _pill(img, key, center, size, grade="Mortal", patterns=0, corner=True):
    key = PILL_ALIASES.get(key, key)
    c = T.RARITY.get(grade, T.GOLD)
    big = size >= 48
    cx, cy = center
    rr = size / 2
    if patterns:
        pill_rings(img, center, rr * 0.5, rr * 0.5 / 9, patterns, color=tint(c, 0.45))
    rp = rr * (0.5 if patterns else 0.78)
    g = GRADE_GLOW.get(grade, 0)
    if g:
        glow(img, center, rp * 1.45, c, g)
    p = _pen(img, center, rp)
    if key == "burst":
        n = 12 if big else 8
        for i in range(n):
            a = math.radians(i * 360 / n)
            p.poly([(math.cos(a - 0.12) * 0.8, math.sin(a - 0.12) * 0.8), (math.cos(a) * 1.28, math.sin(a) * 1.28),
                    (math.cos(a + 0.12) * 0.8, math.sin(a + 0.12) * 0.8)], tint(c, 0.4))
    p.circle(0, 0, 0.92, tint(c, -0.45))
    p.circle(-0.04, -0.04, 0.84, c)
    p.ellipse(-0.3, -0.36, 0.28, 0.18, tint(c, 0.6))
    mark = tint(c, -0.62)
    if key == "qi":
        p.spiral(0.05, 0.08, 0.5, mark, 0.13, turns=1.3)
    elif key == "burst":
        p.bolt(0.05, 0.1, 0.55, mark)
    elif key == "mending":
        p.circle(0.05, 0.12, 0.4, tint((236, 92, 100), 0.1))
        p.leaf(0.05, 0.12, 0.62, 0.2, -60, (70, 170, 90), (30, 90, 40) if big else None)
    elif key == "cleansing":
        p.poly([(0.05, -0.5)] + [(0.05 + math.cos(math.radians(a)) * 0.32, 0.2 + math.sin(math.radians(a)) * 0.32)
                                 for a in range(-30, 211, 15)], (90, 170, 236))
        p.ellipse(-0.05, 0.18, 0.06, 0.12, WHITE)
    else:   # breakthrough: a gate split by a crack
        p.rrect(-0.45, -0.38, 0.45, 0.55, 0.04, mark)
        p.poly([(-0.3, 0.55), (-0.3, -0.05), (-0.15, -0.2), (0.0, -0.05), (0.0, 0.55)], tint(c, 0.2))
        p.line([(0.08, -0.6), (0.18, -0.2), (0.05, 0.1), (0.22, 0.6)], (255, 246, 214), 0.1)
        p.line([(0.2, 0.0), (0.4, -0.15)], (255, 246, 214), 0.05)
    if corner and grade in GRADES:
        es = max(14.0, size * 0.36)
        _grade(img, grade, (cx + rr - es * 0.42, cy + rr - es * 0.42), es)


# ── combined: beast tile (realm emblem + element corner) ──────────────

def _beast(img, key, center, size):
    realm, element = key
    _realm(img, realm, center, size)
    es = max(14.0, size * 0.42)
    _element(img, element, (center[0] + size / 2 - es * 0.4, center[1] + size / 2 - es * 0.4), es)


def _book(img, key, center, size):
    """An open book (the Compendium), in a gold round frame."""
    r = frame(img, center, size, "circle", "gold", (40, 14, 14), T.GOLD, 80, studs=4)
    from .gear_icons import insight
    d = ImageDraw.Draw(img)
    insight(d, center[0], center[1], r * 0.82, (240, 226, 196), (120, 84, 50))


def emblem(img, kind, key, center, size, **kw):
    """Draw one emblem. Unknown keys fall back to the first step of the set."""
    fn = {"grade": _grade, "rarity": _rarity, "realm": _realm, "beast_tier": _beast_tier, "element": _element,
          "pill": _pill, "beast": _beast, "book": _book}[kind]
    if kind == "rarity" and isinstance(key, str):
        key = key.lower()
    return fn(img, key, center, size, **kw)


def has_emblem(kind, key):
    """True when `key` is one of the drawn steps of `kind` (used by the tests)."""
    sets = {"grade": GRADES, "rarity": RARITIES, "realm": REALMS, "beast_tier": BEAST_TIERS, "element": ELEMENTS,
            "pill": PILLS}
    if kind == "pill":
        key = PILL_ALIASES.get(key, key)
    if kind == "rarity" and isinstance(key, str):
        key = key.lower()
    return key in sets[kind]


# ── empty slots ───────────────────────────────────────────────────────

def empty_slot(img, kind, center, size, color=T.ASH_DK):
    """A faint outline: 'armor' = robe, 'artifact' = pearl, 'school:<name>' = that school's base shape."""
    from .drawkit import outline_of
    from .gear_icons import robe

    def pearl(d, cx, cy, s, fill, dark):
        d.ellipse(T.P(cx - s * 0.82, cy - s * 0.82, cx + s * 0.82, cy + s * 0.82), fill=fill)

    if kind == "armor":
        fn = robe
    elif kind == "artifact":
        fn = pearl
    else:
        from .technique_icons import SCHOOL_ICON
        fn = SCHOOL_ICON[kind.split(":", 1)[1]]
    outline_of(img, fn, center, size, color, thickness=max(1.2, size * 0.035))
