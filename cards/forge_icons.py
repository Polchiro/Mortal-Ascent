"""
Drawn icons for /forge (docs/forge.md): the five stages, the stage buttons and the six chisel strokes.

theme.icon(img, "forge:anvil", ...) draws one. Each function takes (d, cx, cy, s, color, dark) like
cards/misc_icons.py: s is half the icon size, dark a shaded version of color. Pillow only, no image files.

The same drawings become round medallion buttons (ICONS below), uploaded at startup by bot/emojis.py as
application emojis named ma_forge_<key>.
"""
import io
import math

from PIL import Image

from . import theme as T
from .drawkit import Pen, tint

WHITE = (255, 255, 255)
STEEL = (176, 186, 200)


def _p(d, cx, cy, s):
    return Pen(d, cx, cy, s)


# ── tools and stages ──────────────────────────────────────────────────

def anvil(d, cx, cy, s, c, dk):
    """An anvil: horn to the left, flat face, waist and a wide foot."""
    p = _p(d, cx, cy, s)
    p.poly([(-1.0, -0.35), (-0.45, -0.5), (0.85, -0.5), (0.85, -0.1), (0.35, -0.05), (0.25, 0.3), (0.55, 0.55),
            (0.6, 0.8), (-0.6, 0.8), (-0.55, 0.55), (-0.25, 0.3), (-0.35, -0.05), (-0.55, -0.12)], c)
    p.poly([(-0.45, -0.5), (0.85, -0.5), (0.85, -0.38), (-0.45, -0.38)], tint(c, 0.35))
    p.poly([(-0.6, 0.62), (0.6, 0.62), (0.6, 0.8), (-0.6, 0.8)], dk)


def hammer(d, cx, cy, s, c, dk):
    """Strike Hard: a heavy smith's hammer, head up and tilted."""
    p = _p(d, cx, cy, s).sub(0, 0, 1, rot=-35)
    p.capsule((0, -0.25), (0, 1.0), 0.2, dk)
    p.rrect(-0.62, -0.78, 0.62, -0.22, 0.08, c)
    p.rrect(-0.62, -0.78, -0.42, -0.22, 0.05, tint(c, 0.35))


def tap(d, cx, cy, s, c, dk):
    """Strike Light: a small hammer with a feather of motion lines."""
    q = _p(d, cx, cy, s)
    p = q.sub(0.15, 0.1, 0.8, rot=-25)
    p.capsule((0, -0.2), (0, 1.0), 0.16, dk)
    p.rrect(-0.45, -0.66, 0.45, -0.22, 0.08, c)
    for i, yy in enumerate((-0.55, -0.25, 0.05)):
        q.line([(-0.95, yy), (-0.6 + i * 0.05, yy - 0.08)], tint(c, 0.3), 0.07)


def bellows(d, cx, cy, s, c, dk):
    """Pump: a pair of bellows with a nozzle and a gust."""
    p = _p(d, cx, cy, s)
    p.poly([(-0.95, -0.6), (0.25, -0.2), (0.25, 0.2), (-0.95, 0.6), (-0.8, 0.0)], c)
    for yy in (-0.25, 0.0, 0.25):
        p.line([(-0.75, yy * 1.6), (0.1, yy * 0.6)], dk, 0.05)
    p.poly([(0.25, -0.12), (0.62, -0.06), (0.62, 0.06), (0.25, 0.12)], tint(c, -0.3))
    p.wave(0.62, 1.0, -0.25, 0.06, tint(c, 0.4), 0.06, 1.0)
    p.wave(0.62, 1.0, 0.25, 0.06, tint(c, 0.4), 0.06, 1.0, math.pi)


def tongs(d, cx, cy, s, c, dk):
    """Pull it out: blacksmith tongs holding a glowing bar."""
    p = _p(d, cx, cy, s)
    p.line([(-0.95, 0.75), (0.1, -0.1), (0.55, -0.35)], c, 0.13)
    p.line([(-0.75, 0.95), (0.2, 0.05), (0.62, -0.18)], tint(c, -0.25), 0.13)
    p.circle(0.12, -0.02, 0.1, tint(c, 0.3))
    p.rrect(0.35, -0.65, 1.0, -0.25, 0.08, (255, 170, 70))
    p.rrect(0.42, -0.58, 0.9, -0.42, 0.05, (255, 232, 170))


def ingot(d, cx, cy, s, c, dk):
    """Heat the metal: a glowing bar with heat shimmer above it."""
    p = _p(d, cx, cy, s)
    p.poly([(-0.85, 0.2), (0.85, 0.2), (0.65, 0.65), (-0.65, 0.65)], c)
    p.poly([(-0.85, 0.2), (0.85, 0.2), (0.75, 0.32), (-0.75, 0.32)], tint(c, 0.45))
    for x in (-0.45, 0.0, 0.45):
        p.line([(x, 0.05), (x + 0.1, -0.2), (x - 0.05, -0.45), (x + 0.08, -0.75)], tint(c, 0.3), 0.07)


def quench(d, cx, cy, s, c, dk):
    """Quench: a blade dipped into a trough, steam rising."""
    p = _p(d, cx, cy, s)
    p.poly([(-1.0, 0.25), (1.0, 0.25), (0.8, 0.9), (-0.8, 0.9)], dk)
    p.poly([(-0.92, 0.32), (0.92, 0.32), (0.88, 0.45), (-0.88, 0.45)], c)
    blade = p.sub(0.05, -0.2, 0.9, rot=15)
    blade.poly([(-0.08, -0.9), (0.08, -0.9), (0.1, 0.5), (0, 0.7), (-0.1, 0.5)], STEEL)
    blade.rrect(-0.3, -1.05, 0.3, -0.92, 0.04, tint(STEEL, -0.4))
    for x in (-0.55, 0.55):
        p.line([(x, 0.15), (x + 0.1, -0.15), (x - 0.05, -0.45)], tint(c, 0.5), 0.07)


def water(d, cx, cy, s, c, dk):
    """Water: a drop over ripples."""
    p = _p(d, cx, cy, s)
    p.poly([(0, -1.0), (0.45, -0.25)] + [(math.cos(math.radians(a)) * 0.48, 0.05 + math.sin(math.radians(a)) * 0.48)
                                         for a in range(-20, 201, 15)] + [(-0.45, -0.25)], c)
    p.circle(-0.15, 0.0, 0.12, tint(c, 0.6))
    p.arc(0, 0.75, 0.85, 200, 340, tint(c, 0.2), 0.07, ry=0.22)


def oil(d, cx, cy, s, c, dk):
    """Oil: a round clay jar with a dark slick drop."""
    p = _p(d, cx, cy, s)
    p.ellipse(0, 0.25, 0.75, 0.68, c)
    p.rrect(-0.32, -0.75, 0.32, -0.35, 0.06, tint(c, -0.25))
    p.rrect(-0.45, -0.85, 0.45, -0.7, 0.06, tint(c, 0.2))
    p.poly([(0, -0.15), (0.25, 0.25)] + [(math.cos(math.radians(a)) * 0.26, 0.38 + math.sin(math.radians(a)) * 0.26)
                                        for a in range(-20, 201, 20)] + [(-0.25, 0.25)], (60, 38, 18))
    p.circle(-0.08, 0.32, 0.07, tint(c, 0.5))


def plunge(d, cx, cy, s, c, dk):
    """Plunge: a blade driven down into water, with a splash."""
    p = _p(d, cx, cy, s)
    p.poly([(-0.1, -1.0), (0.1, -1.0), (0.12, 0.25), (0, 0.45), (-0.12, 0.25)], STEEL)
    p.rrect(-0.38, -0.82, 0.38, -0.68, 0.04, tint(STEEL, -0.4))
    p.ellipse(0, 0.55, 0.9, 0.22, c)
    for a in (-60, -30, 30, 60):
        r = math.radians(a - 90)
        p.line([(math.cos(r) * 0.25, 0.45 + math.sin(r) * 0.1), (math.cos(r) * 0.75, 0.45 + math.sin(r) * 0.55)],
               tint(c, 0.45), 0.08)


def bubbles(d, cx, cy, s, c, dk):
    """Wait a breath: three rising bubbles."""
    p = _p(d, cx, cy, s)
    for x, y, r in ((-0.35, 0.45, 0.38), (0.4, -0.05, 0.3), (-0.1, -0.6, 0.22)):
        p.circle(x, y, r, None, c, 0.1)
        p.circle(x - r * 0.35, y - r * 0.35, r * 0.22, tint(c, 0.6))


def chisel(d, cx, cy, s, c, dk):
    """Inscribe: a chisel cutting a glowing rune line."""
    p = _p(d, cx, cy, s)
    p.line([(-0.9, 0.75), (-0.2, 0.75), (0.1, 0.45)], (255, 214, 120), 0.1)
    t = p.sub(0.3, -0.2, 1.0, rot=40)
    t.rrect(-0.14, -0.95, 0.14, -0.15, 0.06, tint(c, -0.35))
    t.poly([(-0.1, -0.15), (0.1, -0.15), (0.08, 0.55), (0, 0.7), (-0.08, 0.55)], STEEL)


def scroll_again(d, cx, cy, s, c, dk):
    """Forge again: the anvil under a hammer."""
    anvil(d, cx, cy + s * 0.3, s * 0.7, c, dk)
    hammer(d, cx + s * 0.25, cy - s * 0.45, s * 0.55, tint(c, 0.2), dk)


# ── chisel strokes (bot/forging.STROKE_LABEL) ─────────────────────────

def _stroke(points, width=0.32):
    def draw(d, cx, cy, s, c, dk):
        p = _p(d, cx, cy, s)
        p.line(points, c, width)
        p.circle(points[0][0], points[0][1], width * 0.62, tint(c, -0.25))
    return draw


STROKE_DRAW = {
    "horizontal": _stroke([(-0.8, 0.05), (0.0, -0.05), (0.8, 0.05)]),
    "vertical": _stroke([(0.0, -0.85), (0.05, 0.0), (0.0, 0.85)]),
    "sweep": _stroke([(0.45, -0.8), (0.3, -0.1), (-0.15, 0.45), (-0.75, 0.8)]),
    "press": _stroke([(-0.6, -0.75), (-0.1, -0.1), (0.35, 0.45), (0.85, 0.75)], 0.36),
    "dot": _stroke([(-0.12, -0.25), (0.12, 0.2)], 0.5),
    "hook": _stroke([(-0.05, -0.85), (0.0, 0.5), (-0.1, 0.75), (-0.55, 0.45)]),
}

FORGE_ICON = {
    "anvil": anvil, "hammer": hammer, "tap": tap, "bellows": bellows, "tongs": tongs, "ingot": ingot,
    "quench": quench, "water": water, "oil": oil, "plunge": plunge, "bubbles": bubbles, "chisel": chisel,
    "again": scroll_again,
}
FORGE_ICON.update({"stroke_" + k: v for k, v in STROKE_DRAW.items()})

# /forge stage key → icon kind (cards/forge.py stage path)
STAGE_ICON = {"ignite": "flame", "heat": "forge:ingot", "hammer": "forge:hammer", "quench": "forge:quench",
              "inscribe": "forge:chisel"}


# ── buttons: medallions uploaded as application emojis (bot/emojis.py) ─

SIZE = 128
# key: (drawn icon, colour, is_character). The keys are "forge_" + the action keys in bot/forging.py.
ICONS = {
    "forge_pump": ("forge:bellows", (236, 120, 52), False),
    "forge_hold": ("misc:hold", (206, 164, 86), False),
    "forge_vent": ("misc:wind", (110, 160, 232), False),
    "forge_pull": ("forge:tongs", (190, 196, 210), False),
    "forge_keep": ("flame", (246, 140, 60), False),
    "forge_hard": ("forge:hammer", (200, 206, 220), False),
    "forge_light": ("forge:tap", (170, 214, 236), False),
    "forge_reheat": ("flame", (240, 110, 52), False),
    "forge_water": ("forge:water", (96, 170, 240), False),
    "forge_oil": ("forge:oil", (204, 150, 72), False),
    "forge_plunge": ("forge:plunge", (110, 186, 246), False),
    "forge_breath": ("forge:bubbles", (150, 210, 240), False),
    "forge_wait": ("hourglass", (190, 176, 150), False),
    "forge_again": ("forge:again", (236, 150, 70), False),
}
ICONS.update({f"forge_{k}": (f"forge:stroke_{k}", (246, 200, 110), False) for k in STROKE_DRAW})
FALLBACK = {"forge_pump": "💨", "forge_hold": "✋", "forge_vent": "🌬️", "forge_pull": "🪝", "forge_keep": "🔥",
            "forge_hard": "🔨", "forge_light": "🪶", "forge_reheat": "🔥", "forge_water": "💧", "forge_oil": "🛢️",
            "forge_plunge": "💦", "forge_breath": "🫧", "forge_wait": "⏳", "forge_again": "⚒️",
            "forge_horizontal": "➖", "forge_vertical": "⏐", "forge_sweep": "↙️", "forge_press": "↘️",
            "forge_dot": "⏺️", "forge_hook": "↩️"}


def render_icon(key):
    glyph, color, is_char = ICONS[key]
    img = Image.new("RGBA", T.P(SIZE, SIZE), (0, 0, 0, 0))
    c, r = SIZE / 2, SIZE / 2 - 10
    T.medallion(img, (c, c), r, glyph, color, cjk_char=is_char)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def icon_png(key):
    buf = io.BytesIO()
    render_icon(key).save(buf, format="PNG")
    return buf.getvalue()
