"""
Drawn icons for the armor types and artifact families (like the weapon icons in cards/theme.py).

theme.icon(img, "gear:robe", ...) or "gear:fang" draws them. Each function takes
(d, cx, cy, s, color, dark): s is half the icon size, dark a shaded version of color.
Pillow only, no image files.
"""
import math

from .theme import GOLD_HI, P, S, mix

WHITE = (255, 255, 255)


def _w(k=1.0):
    return max(1, round(k * S))


# ── armor ─────────────────────────────────────────────────────────────

def robe(d, cx, cy, s, color, dark):
    """A martial robe: wide sleeves, crossed collar, sash."""
    d.polygon([P(cx - s * 0.3, cy - s * 0.85), P(cx - s, cy - s * 0.45), P(cx - s * 0.8, cy - s * 0.1),
               P(cx - s * 0.5, cy - s * 0.3), P(cx - s * 0.6, cy + s), P(cx + s * 0.6, cy + s),
               P(cx + s * 0.5, cy - s * 0.3), P(cx + s * 0.8, cy - s * 0.1), P(cx + s, cy - s * 0.45),
               P(cx + s * 0.3, cy - s * 0.85)], fill=color)
    d.line(P(cx - s * 0.3, cy - s * 0.85, cx + s * 0.2, cy + s * 0.15), fill=dark, width=_w(1.6))
    d.line(P(cx + s * 0.3, cy - s * 0.85, cx - s * 0.05, cy - s * 0.2), fill=dark, width=_w(1.6))
    d.rectangle(P(cx - s * 0.55, cy + s * 0.1, cx + s * 0.55, cy + s * 0.28), fill=dark)


def plate(d, cx, cy, s, color, dark):
    """Iron plate armour: breastplate with pauldrons and rows of plates."""
    for side in (-1, 1):
        d.chord(P(cx + side * s * 0.65 - s * 0.38, cy - s * 0.9, cx + side * s * 0.65 + s * 0.38, cy - s * 0.15),
                180, 360, fill=dark, outline=color, width=_w())
    d.polygon([P(cx - s * 0.6, cy - s * 0.65), P(cx + s * 0.6, cy - s * 0.65), P(cx + s * 0.55, cy + s * 0.85),
               P(cx, cy + s), P(cx - s * 0.55, cy + s * 0.85)], fill=color)
    for yy in (-0.2, 0.2, 0.55):
        d.line(P(cx - s * 0.52, cy + s * yy, cx + s * 0.52, cy + s * yy), fill=dark, width=_w(1.4))
    d.line(P(cx, cy - s * 0.65, cx, cy + s * 0.95), fill=dark, width=_w())
    d.ellipse(P(cx - s * 0.12, cy - s * 0.5, cx + s * 0.12, cy - s * 0.26), fill=GOLD_HI)


def hide(d, cx, cy, s, color, dark):
    """A stretched beast hide."""
    pts = []
    for i in range(16):
        a = math.radians(i * 22.5)
        r = s * (0.95 if i % 4 == 0 else 0.62 if i % 2 else 0.78)
        pts.append(P(cx + math.cos(a) * r * 0.92, cy + math.sin(a) * r))
    d.polygon(pts, fill=color)
    for (x, y, rr) in ((-0.25, -0.2, 0.14), (0.22, 0.1, 0.12), (-0.05, 0.38, 0.1), (0.15, -0.38, 0.09)):
        d.ellipse(P(cx + s * (x - rr), cy + s * (y - rr), cx + s * (x + rr), cy + s * (y + rr)), fill=dark)


def vest(d, cx, cy, s, color, dark):
    """A sleeveless silk vest with a high collar and frog buttons."""
    d.polygon([P(cx - s * 0.35, cy - s * 0.9), P(cx - s * 0.75, cy - s * 0.55), P(cx - s * 0.6, cy - s * 0.1),
               P(cx - s * 0.65, cy + s * 0.95), P(cx + s * 0.65, cy + s * 0.95), P(cx + s * 0.6, cy - s * 0.1),
               P(cx + s * 0.75, cy - s * 0.55), P(cx + s * 0.35, cy - s * 0.9), P(cx, cy - s * 0.6)], fill=color)
    d.line(P(cx, cy - s * 0.6, cx, cy + s * 0.95), fill=dark, width=_w(1.4))
    for yy in (-0.3, 0.1, 0.5):
        d.line(P(cx - s * 0.2, cy + s * yy, cx + s * 0.2, cy + s * yy), fill=GOLD_HI, width=_w(1.6))


# ── artifacts ─────────────────────────────────────────────────────────

def fang(d, cx, cy, s, color, dark):
    """A curved fang on a cord."""
    d.arc(P(cx - s * 0.8, cy - s * 1.0, cx + s * 0.8, cy + s * 0.1), 200, 340, fill=dark, width=_w(1.6))
    d.polygon([P(cx - s * 0.42, cy - s * 0.55), P(cx + s * 0.42, cy - s * 0.55), P(cx + s * 0.3, cy - s * 0.1),
               P(cx + s * 0.05, cy + s * 0.5), P(cx - s * 0.15, cy + s), P(cx - s * 0.2, cy + s * 0.35),
               P(cx - s * 0.38, cy - s * 0.1)], fill=color)
    d.rectangle(P(cx - s * 0.45, cy - s * 0.62, cx + s * 0.45, cy - s * 0.48), fill=GOLD_HI)


def bell(d, cx, cy, s, color, dark):
    """A temple bell."""
    d.ellipse(P(cx - s * 0.15, cy - s, cx + s * 0.15, cy - s * 0.7), outline=color, width=_w(1.6))
    d.polygon([P(cx - s * 0.4, cy - s * 0.72), P(cx + s * 0.4, cy - s * 0.72), P(cx + s * 0.58, cy + s * 0.55),
               P(cx + s * 0.85, cy + s * 0.75), P(cx - s * 0.85, cy + s * 0.75), P(cx - s * 0.58, cy + s * 0.55)],
              fill=color)
    for yy in (-0.3, 0.2):
        d.line(P(cx - s * 0.5, cy + s * yy, cx + s * 0.5, cy + s * yy), fill=dark, width=_w(1.2))
    d.ellipse(P(cx - s * 0.16, cy + s * 0.68, cx + s * 0.16, cy + s), fill=GOLD_HI)


def mirror(d, cx, cy, s, color, dark):
    """A round bronze mirror on a handle, with a shine."""
    d.rectangle(P(cx - s * 0.12, cy + s * 0.35, cx + s * 0.12, cy + s), fill=dark, outline=color, width=_w())
    d.ellipse(P(cx - s * 0.75, cy - s, cx + s * 0.75, cy + s * 0.5), fill=dark, outline=color, width=_w(2))
    d.ellipse(P(cx - s * 0.58, cy - s * 0.83, cx + s * 0.58, cy + s * 0.33), fill=mix(color, WHITE, 0.25))
    d.line(P(cx - s * 0.35, cy - s * 0.1, cx + s * 0.05, cy - s * 0.55), fill=WHITE, width=_w(2))


def thunder(d, cx, cy, s, color, dark):
    """A storm orb with a lightning bolt."""
    d.ellipse(P(cx - s * 0.9, cy - s * 0.9, cx + s * 0.9, cy + s * 0.9), fill=dark, outline=color, width=_w(1.6))
    d.polygon([P(cx + s * 0.15, cy - s * 0.75), P(cx - s * 0.4, cy + s * 0.1), P(cx - s * 0.02, cy + s * 0.1),
               P(cx - s * 0.18, cy + s * 0.75), P(cx + s * 0.42, cy - s * 0.12), P(cx + s * 0.05, cy - s * 0.12)],
              fill=mix(color, WHITE, 0.35))


def feather(d, cx, cy, s, color, dark):
    """A long feather, slanted."""
    ang = math.radians(35)
    ux, uy = math.sin(ang), -math.cos(ang)
    px, py = -uy, ux
    pts = []
    for i in range(13):
        t = i / 12
        w = math.sin(math.pi * t ** 0.8) * s * 0.36
        pts.append((cx + ux * s * (t * 1.9 - 0.95) + px * w, cy + uy * s * (t * 1.9 - 0.95) + py * w))
    for i in range(12, -1, -1):
        t = i / 12
        w = math.sin(math.pi * t ** 0.8) * s * 0.36
        pts.append((cx + ux * s * (t * 1.9 - 0.95) - px * w, cy + uy * s * (t * 1.9 - 0.95) - py * w))
    d.polygon([P(x, y) for x, y in pts], fill=color)
    d.line(P(cx - ux * s * 1.0, cy - uy * s * 1.0, cx + ux * s * 0.9, cy + uy * s * 0.9), fill=dark, width=_w(1.4))


def focus(d, cx, cy, s, color, dark):
    """A string of prayer beads with a tassel."""
    n = 12
    for i in range(n):
        a = math.radians(i * 360 / n - 90)
        x, y = cx + math.cos(a) * s * 0.68, cy - s * 0.12 + math.sin(a) * s * 0.68
        r = s * 0.17
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=GOLD_HI if i == 3 else color, outline=dark, width=_w(0.6))
    d.polygon([P(cx, cy + s * 0.55), P(cx + s * 0.22, cy + s), P(cx - s * 0.22, cy + s)], fill=dark)


def qi(d, cx, cy, s, color, dark):
    """A glowing pearl with a swirl of Qi around it."""
    d.arc(P(cx - s, cy - s * 0.95, cx + s, cy + s * 0.95), 200, 470, fill=dark, width=_w(2))
    d.ellipse(P(cx - s * 0.55, cy - s * 0.55, cx + s * 0.55, cy + s * 0.55), fill=color)
    d.ellipse(P(cx - s * 0.32, cy - s * 0.35, cx - s * 0.05, cy - s * 0.08), fill=mix(color, WHITE, 0.6))
    d.ellipse(P(cx + s * 0.75, cy - s * 0.15, cx + s, cy + s * 0.1), fill=color)


def purity(d, cx, cy, s, color, dark):
    """A jade bi disc with a hole and a rim pattern."""
    d.ellipse(P(cx - s * 0.95, cy - s * 0.95, cx + s * 0.95, cy + s * 0.95), fill=color)
    d.ellipse(P(cx - s * 0.75, cy - s * 0.75, cx + s * 0.75, cy + s * 0.75), outline=dark, width=_w(1.2))
    for i in range(8):
        a = math.radians(i * 45)
        d.ellipse(P(cx + math.cos(a) * s * 0.55 - s * 0.07, cy + math.sin(a) * s * 0.55 - s * 0.07,
                    cx + math.cos(a) * s * 0.55 + s * 0.07, cy + math.sin(a) * s * 0.55 + s * 0.07), fill=dark)
    d.ellipse(P(cx - s * 0.3, cy - s * 0.3, cx + s * 0.3, cy + s * 0.3), fill=(10, 6, 7))


def furnace(d, cx, cy, s, color, dark):
    """A three-legged cauldron (ding) with a flame inside."""
    d.polygon([P(cx, cy - s), P(cx + s * 0.3, cy - s * 0.55), P(cx + s * 0.2, cy - s * 0.25),
               P(cx - s * 0.2, cy - s * 0.25), P(cx - s * 0.3, cy - s * 0.55)], fill=(255, 196, 96))
    for side in (-1, 1):
        d.line(P(cx + side * s * 0.55, cy - s * 0.45, cx + side * s * 0.55, cy - s * 0.2), fill=color, width=_w(1.8))
        d.line(P(cx + side * s * 0.45, cy + s * 0.5, cx + side * s * 0.65, cy + s), fill=color, width=_w(2))
    d.line(P(cx, cy + s * 0.5, cx, cy + s), fill=color, width=_w(2))
    d.chord(P(cx - s * 0.85, cy - s * 0.65, cx + s * 0.85, cy + s * 0.65), 0, 180, fill=color)
    d.rectangle(P(cx - s * 0.9, cy - s * 0.2, cx + s * 0.9, cy - s * 0.02), fill=dark, outline=color, width=_w())


def gourd(d, cx, cy, s, color, dark):
    """A calabash gourd with a stopper and a cord."""
    d.ellipse(P(cx - s * 0.68, cy - s * 0.05, cx + s * 0.68, cy + s), fill=color)
    d.ellipse(P(cx - s * 0.42, cy - s * 0.7, cx + s * 0.42, cy + s * 0.1), fill=color)
    d.rectangle(P(cx - s * 0.12, cy - s, cx + s * 0.12, cy - s * 0.68), fill=dark)
    d.line(P(cx - s * 0.38, cy - s * 0.02, cx + s * 0.38, cy - s * 0.02), fill=dark, width=_w(2))
    d.ellipse(P(cx - s * 0.4, cy + s * 0.25, cx - s * 0.12, cy + s * 0.5), fill=mix(color, WHITE, 0.35))


def insight(d, cx, cy, s, color, dark):
    """An open book."""
    for side in (-1, 1):
        d.polygon([P(cx, cy - s * 0.55), P(cx + side * s * 0.95, cy - s * 0.75), P(cx + side * s * 0.95, cy + s * 0.65),
                   P(cx, cy + s * 0.85)], fill=color)
        for yy in (-0.35, -0.05, 0.25):
            d.line(P(cx + side * s * 0.18, cy + s * yy, cx + side * s * 0.75, cy + s * (yy - 0.12)), fill=dark,
                   width=_w())
    d.line(P(cx, cy - s * 0.55, cx, cy + s * 0.85), fill=dark, width=_w(1.4))


def compass(d, cx, cy, s, color, dark):
    """A luopan: rings with a needle."""
    d.ellipse(P(cx - s * 0.95, cy - s * 0.95, cx + s * 0.95, cy + s * 0.95), fill=dark, outline=color, width=_w(2))
    d.ellipse(P(cx - s * 0.62, cy - s * 0.62, cx + s * 0.62, cy + s * 0.62), outline=color, width=_w())
    for i in range(8):
        a = math.radians(i * 45)
        d.line(P(cx + math.cos(a) * s * 0.66, cy + math.sin(a) * s * 0.66, cx + math.cos(a) * s * 0.9,
                 cy + math.sin(a) * s * 0.9), fill=color, width=_w())
    d.polygon([P(cx, cy - s * 0.58), P(cx + s * 0.14, cy), P(cx - s * 0.14, cy)], fill=(236, 72, 52))
    d.polygon([P(cx, cy + s * 0.58), P(cx + s * 0.14, cy), P(cx - s * 0.14, cy)], fill=mix(color, WHITE, 0.3))


def fortune(d, cx, cy, s, color, dark):
    """A round coin with a square hole."""
    d.ellipse(P(cx - s * 0.95, cy - s * 0.95, cx + s * 0.95, cy + s * 0.95), fill=color)
    d.ellipse(P(cx - s * 0.75, cy - s * 0.75, cx + s * 0.75, cy + s * 0.75), outline=dark, width=_w(1.4))
    d.rectangle(P(cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25), fill=(10, 6, 7), outline=dark,
                width=_w())
    for a in (0, 90, 180, 270):
        r = math.radians(a)
        x, y = cx + math.cos(r) * s * 0.5, cy + math.sin(r) * s * 0.5
        d.rectangle(P(x - s * 0.06, y - s * 0.06, x + s * 0.06, y + s * 0.06), fill=dark)


def hunter(d, cx, cy, s, color, dark):
    """A beast paw print."""
    d.ellipse(P(cx - s * 0.5, cy - s * 0.05, cx + s * 0.5, cy + s * 0.85), fill=color)
    for x, y in ((-0.72, -0.25), (-0.27, -0.72), (0.27, -0.72), (0.72, -0.25)):
        d.ellipse(P(cx + s * (x - 0.2), cy + s * (y - 0.25), cx + s * (x + 0.2), cy + s * (y + 0.25)), fill=color)
    d.ellipse(P(cx - s * 0.2, cy + s * 0.25, cx + s * 0.2, cy + s * 0.55), fill=dark)


def lotus(d, cx, cy, s, color, dark):
    """A lotus flower (artifact version, drawn here so it shares the family dict)."""
    from .theme import petal
    base = (cx, cy + s * 0.55)
    for ang, ln, col in ((-62, 0.8, dark), (62, 0.8, dark), (-30, 1.15, color), (30, 1.15, color),
                         (0, 1.45, mix(color, WHITE, 0.2))):
        petal(d, base, ang, s * ln, s * 0.42, col)
    d.chord(P(cx - s * 0.9, cy + s * 0.3, cx + s * 0.9, cy + s * 0.95), 0, 180, fill=dark)


GEAR_ICON = {
    "robe": robe, "plate": plate, "hide": hide, "vest": vest,
    "fang": fang, "bell": bell, "mirror": mirror, "thunder": thunder, "lotus": lotus, "feather": feather,
    "focus": focus, "qi": qi, "purity": purity, "furnace": furnace, "gourd": gourd, "insight": insight,
    "compass": compass, "fortune": fortune, "hunter": hunter,
}
