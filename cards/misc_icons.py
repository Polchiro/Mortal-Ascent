"""
Drawn icons for the remaining places that showed seal characters: the Qi sources on /internal qi, herb types,
the /craft stages and the /craft buttons.

theme.icon(img, "misc:blessing", ...) draws one. Each function takes (d, cx, cy, s, color, dark) like
cards/gear_icons.py: s is half the icon size, dark a shaded version of color. Pillow only, no image files.
"""
import math

from .drawkit import Pen, tint

WHITE = (255, 255, 255)
VOIDC = (10, 6, 7)


def _p(d, cx, cy, s):
    return Pen(d, cx, cy, s)


# ── Qi sources ────────────────────────────────────────────────────────

def blessing(d, cx, cy, s, c, dk):
    """Heavenly Blessing: an auspicious cloud under a rayed sun."""
    p = _p(d, cx, cy, s)
    for i in range(7):
        a = math.radians(-180 + i * 30)
        p.line([(math.cos(a) * 0.5, -0.1 + math.sin(a) * 0.5), (math.cos(a) * 0.88, -0.1 + math.sin(a) * 0.88)],
               tint(c, 0.3), 0.09)
    p.circle(0, -0.1, 0.38, tint(c, 0.15))
    p.cloud(0.0, 0.42, 0.62, tint(c, 0.55), c if p.big else None)
    if p.big:
        p.spiral(-0.3, 0.42, 0.14, c, 0.05, turns=1.2)


def land(d, cx, cy, s, c, dk):
    """Blessed Land: twin peaks with a spring falling between them."""
    p = _p(d, cx, cy, s)
    p.poly([(-1.0, 0.85), (-0.45, -0.75), (-0.05, 0.1), (0.35, -0.5), (1.0, 0.85)], c)
    p.poly([(-0.6, -0.4), (-0.45, -0.75), (-0.3, -0.4), (-0.42, -0.48)], tint(c, 0.6))
    water = (140, 210, 250)
    p.poly([(-0.12, 0.05), (0.04, 0.05), (0.12, 0.85), (-0.2, 0.85)], water)
    p.ellipse(-0.04, 0.85, 0.42, 0.1, tint(water, 0.3))
    if p.big:
        p.sparkle(0.62, -0.75, 0.18, WHITE)


def seclusion(d, cx, cy, s, c, dk):
    """Seclusion: a cave mouth in the rock with a cultivator sitting inside."""
    from .technique_icons import figure
    p = _p(d, cx, cy, s)
    p.poly([(-1.0, 0.95), (-0.9, -0.2), (-0.55, -0.75), (0.0, -0.95), (0.55, -0.75), (0.9, -0.2), (1.0, 0.95)], c)
    p.poly([(-0.55, 0.95), (-0.55, -0.05)] + [(math.cos(math.radians(a)) * 0.55, -0.05 + math.sin(math.radians(a)) * 0.6)
                                              for a in range(180, 361, 15)] + [(0.55, 0.95)], VOIDC)
    figure(p.sub(0, 0.35, 0.5), tint(c, 0.45), dk, "seated")
    if p.big:
        p.line([(-0.82, 0.3), (-0.66, 0.15)], dk, 0.05)
        p.line([(0.7, -0.35), (0.82, -0.1)], dk, 0.05)


def toxicity(d, cx, cy, s, c, dk):
    """Pill toxicity: a stoppered flask with bubbles."""
    p = _p(d, cx, cy, s)
    p.rrect(-0.2, -0.95, 0.2, -0.72, 0.05, tint(c, -0.3))
    p.rrect(-0.16, -0.75, 0.16, -0.3, 0.03, tint(c, 0.3))
    p.circle(0, 0.28, 0.66, tint(c, 0.3))
    p.poly([(-0.6, 0.12), (0.6, 0.12)] + [(math.cos(math.radians(a)) * 0.6, 0.28 + math.sin(math.radians(a)) * 0.6)
                                          for a in range(0, 181, 15)], c)
    for x, y, r in ((-0.2, 0.45, 0.1), (0.18, 0.3, 0.07), (0.05, 0.62, 0.06)):
        p.circle(x, y, r, tint(c, 0.6))


# ── herbs ─────────────────────────────────────────────────────────────

def herb_qi(d, cx, cy, s, c, dk):
    """Qi herb: spirit grass blades with a swirl of Qi."""
    p = _p(d, cx, cy, s)
    for a, ln in ((-30, 0.95), (-10, 1.25), (12, 1.1), (32, 0.85)):
        r = math.radians(a - 90)
        p.leaf(math.cos(r) * ln * 0.45, 0.85 + math.sin(r) * ln * 0.45 - 0.05, ln, 0.13, a - 90, c)
    p.spiral(0.35, -0.45, 0.32, tint(c, 0.55), 0.08, turns=1.3)


def herb_healing(d, cx, cy, s, c, dk):
    """Healing herb: a leafy sprig with red berries."""
    p = _p(d, cx, cy, s)
    green = (90, 170, 100)
    p.line([(0, 0.95), (0, -0.2), (-0.3, -0.55)], tint(green, -0.3), 0.08)
    p.leaf(0.32, 0.3, 0.7, 0.2, -30, green)
    p.leaf(-0.32, 0.05, 0.7, 0.2, -150, green)
    for x, y in ((-0.35, -0.65), (-0.05, -0.62), (-0.2, -0.38)):
        p.circle(x, y, 0.2, c)
        if p.big:
            p.circle(x - 0.06, y - 0.06, 0.05, tint(c, 0.6))


def herb_purity(d, cx, cy, s, c, dk):
    """Purity herb: a broad dew leaf with a drop of water."""
    p = _p(d, cx, cy, s)
    p.leaf(-0.1, 0.15, 1.5, 0.48, -60, tint(c, -0.15), tint(c, -0.5))
    p.poly([(0.5, -0.92)] + [(0.5 + math.cos(math.radians(a)) * 0.26, -0.4 + math.sin(math.radians(a)) * 0.26)
                             for a in range(-30, 211, 15)], tint(c, 0.5))
    p.ellipse(0.42, -0.42, 0.05, 0.1, WHITE)


def herb_breakthrough(d, cx, cy, s, c, dk):
    """Breakthrough herb: a ginseng root with a flame of leaves."""
    p = _p(d, cx, cy, s)
    p.poly([(-0.22, -0.2), (0.22, -0.2), (0.3, 0.3), (0.12, 0.6), (0.4, 0.95), (0.05, 0.75), (-0.1, 0.98),
            (-0.12, 0.62), (-0.45, 0.85), (-0.28, 0.35)], c)
    p.line([(-0.15, 0.1), (0.12, 0.05)], dk, 0.05)
    p.line([(-0.12, 0.35), (0.14, 0.3)], dk, 0.05)
    fl = (240, 120, 60)
    p.poly([(0, -1.0), (0.3, -0.55), (0.18, -0.2), (-0.18, -0.2), (-0.3, -0.55)], fl)
    p.leaf(-0.4, -0.4, 0.5, 0.14, -130, (90, 170, 100))
    p.leaf(0.4, -0.4, 0.5, 0.14, -50, (90, 170, 100))


def core(d, cx, cy, s, c, dk):
    """Beast core: a glowing orb with a slit pupil."""
    p = _p(d, cx, cy, s)
    p.circle(0, 0, 0.9, tint(c, -0.4))
    p.circle(-0.04, -0.04, 0.8, c)
    p.ellipse(0, 0, 0.14, 0.55, VOIDC)
    p.ellipse(-0.35, -0.38, 0.16, 0.1, tint(c, 0.6))


# ── /craft stages and buttons ─────────────────────────────────────────

def fuse(d, cx, cy, s, c, dk):
    """Fuse: two essences flowing together, bright where they meet."""
    p = _p(d, cx, cy, s)
    p.circle(-0.3, 0.0, 0.62, tint(c, -0.2))
    p.circle(0.3, 0.0, 0.62, tint(c, 0.25))
    p.ellipse(0.0, 0.0, 0.3, 0.5, tint(c, 0.7))
    if p.big:
        p.sparkle(0.0, 0.0, 0.25, WHITE)


def seal(d, cx, cy, s, c, dk):
    """Seal the core: a talisman strip pressed over an orb."""
    p = _p(d, cx, cy, s)
    p.circle(0, 0.1, 0.72, tint(c, -0.35))
    p.poly([(-0.3, -0.95), (0.3, -0.95), (0.3, 0.95), (-0.3, 0.95)], (240, 214, 120))
    red = (210, 40, 36)
    p.line([(-0.15, -0.65), (0.15, -0.65)], red, 0.08)
    p.line([(0, -0.65), (0, 0.4), (-0.12, 0.6)], red, 0.07)
    p.line([(-0.15, -0.15), (0.15, -0.25)], red, 0.06)


def tribulation(d, cx, cy, s, c, dk):
    """Pill Tribulation: a storm cloud with a bolt."""
    p = _p(d, cx, cy, s)
    p.cloud(0, -0.35, 0.78, tint(c, -0.2), tint(c, -0.5))
    p.bolt(0.05, 0.42, 0.55, (255, 240, 150))


def wind(d, cx, cy, s, c, dk):
    """Fan: three gusts of wind."""
    p = _p(d, cx, cy, s)
    for y, x1, r in ((-0.45, 0.45, 0.25), (0.05, 0.7, 0.22), (0.52, 0.3, 0.2)):
        p.line([(-0.9, y), (x1, y)], c, 0.12)
        p.arc(x1, y - r, r, 90, 340, c, 0.12)


def snowflake(d, cx, cy, s, c, dk):
    """Cool: a snowflake."""
    p = _p(d, cx, cy, s)
    for i in range(3):
        a = math.radians(90 + i * 60)
        ux, uy = math.cos(a) * 0.9, math.sin(a) * 0.9
        p.line([(-ux, -uy), (ux, uy)], c, 0.13)
        for sgn in (-1, 1):
            bx, by = ux * 0.55 * sgn, uy * 0.55 * sgn
            for t in (-1, 1):
                b = a + (math.pi if sgn < 0 else 0) + t * math.radians(40)
                p.line([(bx, by), (bx - math.cos(b) * 0.28, by - math.sin(b) * 0.28)], c, 0.09)


def circulate(d, cx, cy, s, c, dk):
    """Circulate: two arrows chasing each other round a circle."""
    p = _p(d, cx, cy, s)
    for start in (200, 20):
        p.arc(0, 0, 0.7, start, start + 130, c, 0.16)
        a = math.radians(start + 140)
        tx, ty = math.cos(a) * 0.7, math.sin(a) * 0.7
        ux, uy = -math.sin(a), math.cos(a)
        nx, ny = math.cos(a), math.sin(a)
        p.poly([(tx + ux * 0.28, ty + uy * 0.28), (tx + nx * 0.22, ty + ny * 0.22), (tx - nx * 0.22, ty - ny * 0.22)], c)


def compress(d, cx, cy, s, c, dk):
    """Compress: two arrows pressing down onto a bar."""
    p = _p(d, cx, cy, s)
    for x in (-0.45, 0.45):
        p.rrect(x - 0.1, -0.95, x + 0.1, -0.15, 0.04, c)
        p.poly([(x - 0.3, -0.25), (x + 0.3, -0.25), (x, 0.2)], c)
    p.rrect(-0.9, 0.38, 0.9, 0.62, 0.06, tint(c, 0.3))
    p.rrect(-0.75, 0.7, 0.75, 0.9, 0.06, tint(c, -0.2))


def hold(d, cx, cy, s, c, dk):
    """Hold steady: a raised open palm."""
    from .technique_icons import palm
    palm(_p(d, cx, cy, s), c, dk)


def _arrow(angle):
    def draw(d, cx, cy, s, c, dk):
        p = _p(d, cx, cy, s)
        a = math.radians(angle)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        p.capsule((-ux * 0.8, -uy * 0.8), (ux * 0.2, uy * 0.2), 0.3, c)
        p.poly([(ux * 0.95, uy * 0.95), (ux * 0.1 + nx * 0.55, uy * 0.1 + ny * 0.55),
                (ux * 0.1 - nx * 0.55, uy * 0.1 - ny * 0.55)], c)
    return draw


MISC_ICON = {
    "blessing": blessing, "land": land, "seclusion": seclusion, "toxicity": toxicity,
    "herb_qi": herb_qi, "herb_healing": herb_healing, "herb_purity": herb_purity,
    "herb_breakthrough": herb_breakthrough, "core": core,
    "fuse": fuse, "seal": seal, "tribulation": tribulation,
    "wind": wind, "snowflake": snowflake, "circulate": circulate, "compress": compress, "hold": hold,
    "arrow_left": _arrow(180), "arrow_up": _arrow(-90), "arrow_right": _arrow(0),
}

# herb type → icon kind (alchemy.HERB_TYPE_CHANCE keys, plus beast cores)
HERB_ICON = {"qi": "misc:herb_qi", "healing": "misc:herb_healing", "purity": "misc:herb_purity",
             "breakthrough": "misc:herb_breakthrough", "core": "misc:core"}
# /craft stage number → icon kind (bot/craft_card.py stages)
STAGE_ICON = {1: "flame", 2: "herb", 3: "misc:fuse", 4: "pill", 5: "misc:seal", 6: "misc:tribulation"}
