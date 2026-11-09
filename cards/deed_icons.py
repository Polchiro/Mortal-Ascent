"""
Drawn icons for the Profile's Deeds of the Jianghu rail (beasts, herbs, breakthroughs, duels, rank) and the two
currencies (Lotus Coins, Moon Pearls), in the same style as cards/misc_icons.py and cards/technique_icons.py.

theme.icon(img, "deed:beasts", ...) draws one. Each function takes (d, cx, cy, s, color, dark): s is half the icon
size, dark a shaded version of color. Pillow only, no image files.
"""
import math

from .drawkit import Pen, tint

WHITE = (255, 255, 255)
VOIDC = (10, 6, 7)
BLOOD = (200, 52, 40)
LEAF = (96, 178, 104)


def _p(d, cx, cy, s):
    return Pen(d, cx, cy, s)


def beasts(d, cx, cy, s, c, dk):
    """Beasts slain: a snarling wolf head over three bloody claw slashes."""
    from .emblems import _claws, _wolf
    p = _p(d, cx, cy, s)
    _claws(p.sub(0.05, 0.0, 1.0, rot=-18), BLOOD, dk, p.big)
    _wolf(p.sub(0, 0.08, 0.86), tint(c, 0.2), tint(c, -0.55), p.big)
    if p.big:   # bared fangs
        for sd in (-1, 1):
            p.poly([(sd * 0.1, 0.36), (sd * 0.2, 0.36), (sd * 0.14, 0.56)], WHITE)


def herbs(d, cx, cy, s, c, dk):
    """Herbs gathered: a lingzhi mushroom with spirit leaves and a wisp of Qi."""
    p = _p(d, cx, cy, s)
    p.leaf(-0.5, 0.55, 0.85, 0.2, -140, LEAF)
    p.leaf(0.52, 0.6, 0.8, 0.18, -40, tint(LEAF, -0.15))
    # stem
    p.poly([(-0.1, -0.05), (0.1, -0.05), (0.16, 0.9), (-0.14, 0.9)], tint(c, -0.35))
    # cap: a fan with growth rings
    cap = [(math.cos(math.radians(a)) * 0.85, -0.05 + math.sin(math.radians(a)) * 0.62) for a in range(180, 361, 10)]
    p.poly(cap + [(0.7, 0.05), (-0.7, 0.05)], c)
    for r, t in ((0.62, 0.35), (0.38, 0.6)):
        p.arc(0, -0.05, r, 195, 345, tint(c, t), 0.06, ry=r * 0.72)
    p.line([(-0.72, 0.03), (0.72, 0.03)], tint(c, -0.4), 0.07)
    if p.big:
        p.spiral(0.55, -0.72, 0.2, tint(c, 0.6), 0.05, turns=1.2)
        p.sparkle(-0.62, -0.75, 0.14, WHITE)


def breakthroughs(d, cx, cy, s, c, dk):
    """Breakthroughs: a seated cultivator inside a shattering ring, Qi bursting upward."""
    from .technique_icons import figure
    p = _p(d, cx, cy, s)
    for i in range(5):     # rays of Qi
        a = math.radians(-90 + (i - 2) * 22)
        p.line([(math.cos(a) * 0.62, 0.05 + math.sin(a) * 0.62), (math.cos(a) * 0.98, 0.05 + math.sin(a) * 0.98)],
               tint(c, 0.45), 0.07)
    for a0, a1 in ((-60, 30), (55, 125), (150, 230)):     # the broken bottleneck ring
        p.arc(0, 0.05, 0.78, a0, a1, tint(c, -0.2), 0.11)
    for x, y, rot in ((0.78, -0.42, 30), (-0.82, -0.32, -20)):
        p.poly([(x - 0.07, y - 0.05), (x + 0.07, y - 0.08), (x + 0.03, y + 0.07)], tint(c, -0.2))
    p.circle(0, 0.08, 0.5, tint(c, -0.55))
    figure(p.sub(0, 0.18, 0.55), tint(c, 0.55), dk, "seated")
    p.circle(0, -0.2, 0.07, WHITE)


def _jian(p, c, dk):
    """A straight sword pointing up, in icon units of p (the middle of the blade sits at the centre)."""
    p = p.sub(0, 0.3, 0.85)
    p.poly([(-0.08, 0.35), (-0.08, -0.82), (0, -1.0), (0.08, -0.82), (0.08, 0.35)], tint(c, 0.45))
    p.line([(0, -0.8), (0, 0.3)], tint(c, -0.15), 0.025)
    p.rrect(-0.32, 0.35, 0.32, 0.46, 0.05, tint(c, -0.1), dk, 0.03)
    p.rrect(-0.06, 0.46, 0.06, 0.82, 0.03, dk)
    p.circle(0, 0.88, 0.09, c)


def duels(d, cx, cy, s, c, dk):
    """Duels: two crossed jian swords with a spark where the blades meet."""
    p = _p(d, cx, cy, s)
    _jian(p.sub(0, -0.05, 1.0, rot=-40), c, dk)
    _jian(p.sub(0, -0.05, 1.0, rot=40), c, dk)
    if p.big:
        p.sparkle(0, -0.3, 0.26, WHITE)


def rank(d, cx, cy, s, c, dk):
    """Rank: a hanging jade tablet with a gold star, tied with a red tassel."""
    p = _p(d, cx, cy, s)
    p.line([(0, -0.98), (0, -0.66)], BLOOD, 0.07)
    p.circle(0, -0.98, 0.08, BLOOD)
    p.rrect(-0.52, -0.68, 0.52, 0.55, 0.14, tint(c, -0.35))
    p.rrect(-0.42, -0.58, 0.42, 0.45, 0.1, tint(c, -0.6), tint(c, 0.1), 0.04)
    p.star(0, -0.08, 5, 0.34, 0.15, tint(c, 0.4))
    for sd in (-1, 0, 1):    # tassel
        p.line([(0, 0.55), (sd * 0.12, 0.95)], BLOOD, 0.06)
    p.circle(0, 0.6, 0.08, (232, 190, 80))


def lotus_coin(d, cx, cy, s, c, dk):
    """Lotus Coins: a round cash coin with a square hole and a lotus stamped on it."""
    p = _p(d, cx, cy, s)
    p.circle(0, 0.04, 0.95, tint(c, -0.5))
    p.circle(0, 0, 0.92, c)
    p.ring(0, 0, 0.78, tint(c, -0.35), 0.05)
    for a in (-90, -50, -130, -15, -165):     # petals fanning above the hole
        r = math.radians(a)
        p.leaf(math.cos(r) * 0.42, 0.05 + math.sin(r) * 0.42, 0.5, 0.15, a, tint(c, 0.45))
    p.rrect(-0.2, -0.05, 0.2, 0.35, 0.03, VOIDC, tint(c, -0.4), 0.04)
    p.arc(0, 0.12, 0.6, 30, 150, tint(c, -0.3), 0.05)
    if p.big:
        p.arc(0, 0, 0.88, 200, 250, tint(c, 0.7), 0.06)


def moon_pearl(d, cx, cy, s, c, dk):
    """Moon Pearls: a glowing pearl cradled by a crescent moon."""
    p = _p(d, cx, cy, s)
    p.crescent(0, 0, 0.98, tint(c, -0.15), cut=0.6, shift=0.42, angle=-45)
    p.circle(0.16, -0.12, 0.56, tint(c, -0.35))
    p.circle(0.14, -0.14, 0.52, tint(c, 0.45))
    p.circle(0.2, -0.08, 0.36, tint(c, 0.7))
    p.ellipse(-0.04, -0.34, 0.14, 0.09, WHITE)
    if p.big:
        p.sparkle(0.72, 0.62, 0.18, WHITE)
        p.sparkle(0.82, -0.78, 0.12, tint(c, 0.6))


DEED_ICON = {
    "beasts": beasts, "herbs": herbs, "breakthroughs": breakthroughs, "duels": duels, "rank": rank,
    "lotus_coin": lotus_coin, "moon_pearl": moon_pearl,
}
