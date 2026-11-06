"""
The Forge Hall: the /forge card that the bot edits after every decision (docs/forge.md).

  ┌ scene window: a smithy wall, a brick hearth with its fire, and an anvil in front
  │   top left: the gear's icon, its name, tier · action · slot
  │   top right: round / strike / stroke X of Y, seconds to choose, difficulty chip
  │   right: the five stages as a path (done ✓, current lit)
  │   left + middle, per stage: the fire and heat gauge, the metal's colour, the hammer, the quench trough,
  │   the rune's strokes, or the result (the new passive / the cracked gear)
  ├ "On the anvil" (materials) · "Forging" (score) · "Passive" (rarity so far and its cap)
  └ warning bar: the stage's hint or omen

render_forge(data) takes plain data (bot/forge_card.card_data), so it can run off the event loop.
The hall is cached; only the fire, effects and panels are drawn each time. Nothing on it is under 24px,
because Discord shows the card at under half size on a computer.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from .alchemy import FIRE, _bricks, _flame_poly, _heat_gauge, _Local, _smoke
from .battle import _check, _chip, _heading, _shrink, _warning
from .forge_icons import STAGE_ICON, STROKE_DRAW
from .theme import P, S, alpha, font, mix

W, H = 1200, 880
SCENE = (16, 16, 1184, 500)
PANELS = [(16, 512, 400, 742), (412, 512, 788, 742), (800, 512, 1184, 742)]
WARN = (16, 754, 1184, 864)

CX = 600                       # the hearth and anvil centre line
WALL_END = 404
MOUTH = (486, 236, 714, 404)   # the hearth's opening
ANVIL_TOP = 418                # the anvil's face

STAGE_LABEL = {"ignite": "Ignite", "heat": "Heat", "hammer": "Hammer", "quench": "Quench", "inscribe": "Inscribe"}
DIFFICULTY_COLOR = {"Normal": (96, 196, 110), "Hard": (222, 182, 70), "Very Hard": (236, 140, 52),
                    "Extreme": (226, 72, 56), "Super Hard": (168, 110, 240)}
HEAT_CHIP = {"cold": ("Too cold", (90, 150, 240)), "zone": ("Steady", (236, 184, 70)),
             "hot": ("Too hot!", (226, 60, 44))}
METAL_COLORS = [(150, 36, 26), (206, 46, 34), (246, 132, 36), (255, 214, 80), (255, 250, 236)]
WATER, OIL = (70, 140, 220), (150, 100, 40)
STEEL = (150, 160, 176)
WHITE = (255, 248, 232)
GREEN = (110, 214, 140)
RED = (226, 72, 56)
LX = 46


# ── the hall (cached) ─────────────────────────────────────────────────

def _arch_pts(box, n=24):
    x0, y0, x1, y1 = box
    r = (x1 - x0) / 2
    cx = (x0 + x1) / 2
    top = y0 + r * 0.7
    pts = [(x0, y1), (x0, top)]
    for i in range(n + 1):
        a = math.radians(180 + 180 * i / n)
        pts.append((cx + math.cos(a) * r, top + math.sin(a) * r * 0.7))
    return pts + [(x1, top), (x1, y1)]


@lru_cache(maxsize=2)
def _hall(accent):
    """The card background with the smithy in the scene window: wall, hearth (cold mouth), floor. S×, RGBA."""
    acc = T.ACCENTS[accent]
    img = T.canvas(W, H, seed=31, accent=accent)
    x0, y0, x1, y1 = SCENE
    img.alpha_composite(T.vgradient(P(x1 - x0, WALL_END - y0), acc.sky[0], acc.sky[1]), P(x0, y0))
    d = ImageDraw.Draw(img)
    _bricks(d, (x0, y0, x1, WALL_END), mix(acc.sky[1], (0, 0, 0), 0.5), 11)
    floor = T.vgradient(P(x1 - x0, y1 - WALL_END), mix(acc.sky[1], (0, 0, 0), 0.4), mix(acc.sky[0], (0, 0, 0), 0.5))
    img.alpha_composite(floor, P(x0, WALL_END))
    d = ImageDraw.Draw(img)
    d.line(P(x0, WALL_END, x1, WALL_END), fill=alpha(mix(acc.rim, (0, 0, 0), 0.45), 255), width=round(2 * S))
    for k in range(15):
        x = x0 + (x1 - x0) * k / 14
        d.line(P(CX + (x - CX) * 0.45, WALL_END, x, y1), fill=alpha(mix(acc.sky[1], (0, 0, 0), 0.62), 255),
               width=max(1, S))
    # the hearth: a stone chimney breast, a brick arch and a dark mouth
    stone = mix(acc.mist, (0, 0, 0), 0.55)
    d.polygon([P(*p) for p in [(CX - 120, y0), (CX + 120, y0), (CX + 150, 170), (CX + 170, WALL_END),
                               (CX - 170, WALL_END), (CX - 150, 170)]], fill=alpha(stone, 255))
    d.polygon([P(*p) for p in [(CX - 120, y0), (CX - 104, y0), (CX - 134, 170), (CX - 150, 170)]],
              fill=alpha(mix(stone, (255, 255, 255), 0.12), 255))
    arch = _arch_pts((MOUTH[0] - 26, MOUTH[1] - 26, MOUTH[2] + 26, MOUTH[3]))
    d.polygon([P(*p) for p in arch], fill=alpha(mix(acc.warn, (0, 0, 0), 0.45), 255))
    for i in range(1, len(arch) - 2, 2):                     # voussoir joints
        ax, ay = arch[i]
        bx, by = (arch[i][0] + (CX - arch[i][0]) * 0.18, arch[i][1] + 18)
        d.line(P(ax, ay, bx, by), fill=alpha(mix(acc.warn, (0, 0, 0), 0.75), 255), width=round(2 * S))
    d.polygon([P(*p) for p in _arch_pts(MOUTH)], fill=(14, 8, 6, 255))
    d.rectangle(P(CX - 196, WALL_END - 16, CX + 196, WALL_END + 6), fill=alpha(mix(stone, (0, 0, 0), 0.2), 255))
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for k in range(10):
        a = 18 * (10 - k)
        sd.rectangle(P(x0 + k * 14, y0, x0 + (k + 1) * 14, y1), fill=(0, 0, 0, a))
        sd.rectangle(P(x1 - (k + 1) * 14, y0, x1 - k * 14, y1), fill=(0, 0, 0, a))
    img.alpha_composite(shade)
    return img


@lru_cache(maxsize=1)
def _anvil():
    """The anvil as a card-sized S× layer, face at ANVIL_TOP."""
    layer = Image.new("RGBA", P(W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    t = ANVIL_TOP
    body = [(CX - 210, t + 4), (CX - 120, t - 4), (CX + 150, t - 4), (CX + 150, t + 26), (CX + 70, t + 32),
            (CX + 52, t + 52), (CX + 96, t + 70), (CX + 104, 492), (CX - 104, 492), (CX - 96, t + 70),
            (CX - 52, t + 52), (CX - 70, t + 32), (CX - 120, t + 24)]
    d.polygon([P(*p) for p in body], fill=(46, 48, 56, 255))
    d.polygon([P(*p) for p in [(CX - 120, t - 4), (CX + 150, t - 4), (CX + 150, t + 6), (CX - 120, t + 6)]],
              fill=(150, 156, 170, 255))
    d.polygon([P(*p) for p in [(CX - 210, t + 4), (CX - 120, t - 4), (CX - 120, t + 6)]], fill=(110, 116, 128, 255))
    d.line(P(CX - 96, t + 70, CX + 96, t + 70), fill=(70, 74, 84, 255), width=round(2 * S))
    d.rectangle(P(CX - 104, 478, CX + 104, 492), fill=(30, 30, 36, 255))
    return layer


def _floor_shadow(img, cx, y, rx, ry, a=150):
    T.soft_glow(img, (cx - rx, y - ry, cx + rx, y + ry), (0, 0, 0, a), 12)


# ── fire, metal, tools ────────────────────────────────────────────────

def _hearth_fire(img, state, seed):
    """Flames in the hearth's mouth, sized by the fire's state."""
    rng = random.Random(seed)
    back_h, _, outer, middle, core, sparks, white = FIRE[state]
    h = back_h * 1.15
    _, my0, _, my1 = MOUTH
    T.soft_glow(img, (MOUTH[0] - 120, my0 - 60, MOUTH[2] + 120, WALL_END + 90), alpha(middle, {
        "cold": 50, "zone": 110, "hot": 170, "embers": 40}[state]), 34)
    loc = _Local((MOUTH[0], my0, MOUTH[2], my1))
    for i in range(9):
        x = MOUTH[0] + 18 + i * (MOUTH[2] - MOUTH[0] - 36) / 8
        fh = h * rng.uniform(0.7, 1.15) * (0.75 + 0.25 * (1 - abs(x - CX) / 120))
        fw = 20 * rng.uniform(0.8, 1.2)
        sway = rng.uniform(-10, 10)
        loc.d.polygon(loc.p(_flame_poly(x, my1 - 6, fh, fw, sway)), fill=alpha(outer, 230))
        loc.d.polygon(loc.p(_flame_poly(x, my1 - 6, fh * 0.7, fw * 0.62, sway * 0.7)), fill=alpha(middle, 240))
        loc.d.polygon(loc.p(_flame_poly(x, my1 - 6, fh * 0.42, fw * 0.36, sway * 0.4)), fill=alpha(core, 250))
        if white and i % 2 == 0:
            loc.d.polygon(loc.p(_flame_poly(x, my1 - 6, fh * 0.26, fw * 0.22, sway * 0.2)), fill=(255, 255, 250, 255))
    mask = Image.new("L", loc.img.size, 0)
    ImageDraw.Draw(mask).polygon(loc.p([P(*p) for p in _arch_pts(MOUTH)]), fill=255)
    for blur in (8, 1.2):
        layer = loc.img.filter(ImageFilter.GaussianBlur(blur * S))
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", layer.size, 0), mask))
        loc.paste(img, layer)
    d = ImageDraw.Draw(img)
    for _ in range(sparks):                                  # sparks drifting out of the mouth
        x, y = CX + rng.uniform(-160, 160), rng.uniform(150, MOUTH[1] + 40)
        r = rng.uniform(1.4, 3.2)
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=alpha(mix(core, (255, 255, 255), rng.random() * 0.5),
                                                            rng.randint(150, 255)))


def _bar_on_anvil(img, color, glow=True, cracked=False, seed=1):
    """A glowing bar of metal lying on the anvil."""
    y = ANVIL_TOP - 14
    if glow:
        T.soft_glow(img, (CX - 150, y - 50, CX + 150, y + 40), alpha(color, 170), 18)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(P(CX - 110, y - 12, CX + 110, y + 10), radius=6 * S, fill=alpha(color, 255),
                        outline=alpha(mix(color, (0, 0, 0), 0.4), 255), width=round(2 * S))
    d.rectangle(P(CX - 100, y - 9, CX + 100, y - 4), fill=alpha(mix(color, (255, 255, 255), 0.45), 255))
    if cracked:
        rng = random.Random(seed)
        x = CX - 20
        pts = [(x, y - 12)]
        for k in range(4):
            x += rng.uniform(-14, 14)
            pts.append((x, y - 12 + (k + 1) * 6))
        d.line([P(*p) for p in pts], fill=(10, 8, 8, 255), width=round(3 * S))


def _gear_on_anvil(img, data, color, glow=160):
    g = data["gear"]
    cy = ANVIL_TOP - 66
    T.soft_glow(img, (CX - 90, cy - 90, CX + 90, cy + 90), alpha(color, glow), 22)
    T.icon(img, g["icon"], (CX + 4, cy + 4), 118, (10, 8, 8))
    T.icon(img, g["icon"], (CX, cy), 118, mix(color, (255, 255, 255), 0.15))


def _hammer(img, angle, x=CX + 160, y=250):
    """A big hammer over the anvil, angle in degrees (0 = raised)."""
    T.icon(img, "forge:hammer", (x + 4, y + 4), 210, (8, 6, 6))
    T.icon(img, "forge:hammer", (x, y), 210, (184, 190, 204))


def _strike_flash(img, seed):
    rng = random.Random(seed)
    cx, cy = CX + 40, ANVIL_TOP - 22
    T.soft_glow(img, (cx - 70, cy - 50, cx + 70, cy + 40), (255, 220, 150, 200), 14)
    d = ImageDraw.Draw(img)
    for _ in range(16):
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
        r0, r1 = rng.uniform(10, 24), rng.uniform(50, 110)
        d.line(P(cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * r1, cy + math.sin(a) * r1),
               fill=(255, rng.randint(180, 240), 120, 230), width=round(2.5 * S))


def _trough(img, medium):
    """The quench trough in front of the anvil: water or oil."""
    col = OIL if medium == "oil" else WATER
    x0, x1, y0, y1 = CX - 230, CX + 230, 432, 492
    d = ImageDraw.Draw(img)
    d.polygon([P(x0, y0), P(x1, y0), P(x1 - 18, y1), P(x0 + 18, y1)], fill=(54, 36, 24, 255))
    d.rectangle(P(x0 - 6, y0 - 8, x1 + 6, y0 + 4), fill=(86, 58, 36, 255))
    d.rectangle(P(x0 + 10, y0 + 4, x1 - 10, y0 + 18), fill=alpha(col, 255))
    d.line(P(x0 + 20, y0 + 8, x1 - 60, y0 + 8), fill=alpha(mix(col, (255, 255, 255), 0.5), 200), width=round(2 * S))


def _held_blade(img, temp_color, y=330):
    """A blade held by tongs over the trough, glowing at its temperature."""
    T.soft_glow(img, (CX - 160, y - 40, CX + 160, y + 40), alpha(temp_color, 150), 18)
    d = ImageDraw.Draw(img)
    d.polygon([P(CX - 130, y - 10), P(CX + 110, y - 10), P(CX + 150, y), P(CX + 110, y + 10), P(CX - 130, y + 10)],
              fill=alpha(temp_color, 255), outline=alpha(mix(temp_color, (0, 0, 0), 0.4), 255))
    d.rectangle(P(CX - 190, y - 7, CX - 130, y + 7), fill=(60, 44, 32, 255))
    T.icon(img, "forge:tongs", (CX - 240, y + 26), 110, STEEL)


def _temp_color(temp):
    """Blade glow by temperature: white-yellow when hot, fading to dull red then steel."""
    stops = [(300, STEEL), (450, (150, 40, 28)), (600, (220, 60, 34)), (750, (250, 150, 50)), (900, (255, 236, 160))]
    temp = max(stops[0][0], min(stops[-1][0], temp))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if temp <= t1:
            return mix(c0, c1, (temp - t0) / (t1 - t0))
    return stops[-1][1]


def _stroke_icon(img, key, center, size, color):
    d = ImageDraw.Draw(img)
    STROKE_DRAW[key](d, center[0], center[1], size / 2, color, mix(color, (0, 0, 0), 0.5))


# ── left info column ──────────────────────────────────────────────────

def _caption(img, y, s, color=T.GOLD):
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (LX, y), T.fit(d, s.upper(), f, 300), f, color, 1.8)


def _note(img, y, s, color=T.ASH, lines=2, size=24):
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", size, "Medium")
    for i, line in enumerate(T.wrap(d, s, f, 300, lines)):
        T.text(d, (LX, y + i * 31), line, f, color, "lm")


def _big(img, y, s, glow=None, size=96):
    d = ImageDraw.Draw(img)
    s, f = _shrink(d, s, "Cinzel.ttf", "Black", (size, 80, 64, 52, 44), 330)
    T.gold_text(img, (LX, y), s, f, "ls", glow=glow)


def _left_ignite(img, data, acc):
    _big(img, 286, f"{data['heat']}°", glow=alpha(acc.rim, 110))
    _caption(img, 318, "Forge heat")
    label, col = HEAT_CHIP[data["heat_state"]]
    _chip(img, LX, 374, label, col)
    _note(img, 428, f"Safe zone {data['zone_width']}° wide, hidden. Read the fire.")


def _left_heat(img, data, acc):
    shown, target = data["color"], data["target"]
    _big(img, 270, data["color_name"].title(), glow=alpha(METAL_COLORS[shown], 120), size=64)
    _caption(img, 306, "Metal colour")
    d = ImageDraw.Draw(img)
    for i, col in enumerate(METAL_COLORS):                    # the colour scale, target ringed
        x = LX + 6 + i * 60
        d.rounded_rectangle(P(x, 340, x + 48, 384), radius=8 * S, fill=alpha(col, 255),
                            outline=alpha(T.GOLD_HI if i == target else (30, 22, 18), 255),
                            width=round((4 if i == target else 2) * S))
        if i == shown:
            d.polygon([P(x + 24, 394), P(x + 12, 412), P(x + 36, 412)], fill=alpha(T.GOLD_HI, 255))
    _note(img, 440, f"Pull it out at {data['target_name']}.", T.PARCHMENT)


def _left_hammer(img, data, acc):
    _big(img, 286, f"{data['strike'] + 1} / {data['strikes']}", glow=alpha(acc.rim, 90))
    _caption(img, 318, "Strike")
    _note(img, 372, data["hint"], T.PARCHMENT, lines=3)


def _left_quench(img, data, acc):
    if data["medium"] is None:
        _big(img, 286, f"{data['temp']}°", glow=alpha(_temp_color(data["temp"]), 120))
        _caption(img, 318, "Blade temperature")
        _note(img, 372, "Water: fast and risky. Oil: slow and safe.", T.PARCHMENT)
        return
    _big(img, 270, f"{data['temp']}°", glow=alpha(_temp_color(data["temp"]), 120))
    _caption(img, 302, "Blade temperature")
    lo, hi = 300, 920
    x0, x1, y = LX, LX + 300, 350
    d = ImageDraw.Draw(img)
    for k in range(60):
        t = lo + (hi - lo) * k / 60
        xa = x0 + (x1 - x0) * k / 60
        d.rectangle(P(xa, y - 9, xa + (x1 - x0) / 60 + 0.6, y + 9), fill=alpha(_temp_color(t), 255))
    half = data["window"] / 2
    wa = x0 + (x1 - x0) * (data["target"] - half - lo) / (hi - lo)
    wb = x0 + (x1 - x0) * (data["target"] + half - lo) / (hi - lo)
    d.rectangle(P(wa, y - 17, wb, y + 17), outline=alpha(GREEN, 255), width=round(3 * S))
    mx = x0 + (x1 - x0) * (max(lo, min(hi, data["temp"])) - lo) / (hi - lo)
    d.polygon([P(mx, y - 20), P(mx - 10, y - 36), P(mx + 10, y - 36)], fill=alpha(WHITE, 255))
    _note(img, 404, f"Plunge near {data['target']}° (± {half:.0f}°) in the {data['medium']}.", T.PARCHMENT)


def _left_inscribe(img, data, acc):
    _big(img, 286, f"{data['carved'] + 1} / {data['strokes']}", glow=alpha(acc.rim, 90))
    _caption(img, 318, "Stroke")
    _note(img, 372, f"Rune of {data['rune']}", T.PARCHMENT, size=26)
    _note(img, 412, "Carve the strokes in the order shown.")


def _left_success(img, data, acc):
    r = data["result"]
    col = _rarity_color(r["rarity"])
    _big(img, 270, r["rarity"], glow=alpha(col, 140), size=64)
    _caption(img, 306, "New passive" if r.get("passive") else "Forged")
    if r.get("passive"):
        _note(img, 352, r["passive"], WHITE, size=26)
        _note(img, 392, r.get("text", ""), T.PARCHMENT, lines=2)


def _left_failed(img, data, acc):
    _big(img, 286, f"{data['score']['total']}", glow=alpha(RED, 120))
    _caption(img, 318, "Score: too low")
    _note(img, 372, data["result"].get("saved") or "The materials are lost. The gear is safe.", T.PARCHMENT, lines=3)


# ── middle per stage ──────────────────────────────────────────────────

def _mid_ignite(img, data, acc, seed):
    _hearth_fire(img, data["heat_state"], seed)
    img.alpha_composite(_anvil())
    _heat_gauge(img, data["heat"])


def _mid_heat(img, data, acc, seed):
    _hearth_fire(img, "zone", seed)
    col = METAL_COLORS[data["color"]]
    T.soft_glow(img, (CX - 120, 300, CX + 120, 400), alpha(col, 200), 16)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(P(CX - 80, 340, CX + 80, 360), radius=6 * S, fill=alpha(col, 255))
    d.rectangle(P(CX + 80, 345, CX + 260, 355), fill=(60, 56, 60, 255))          # the tongs' reins
    img.alpha_composite(_anvil())


def _mid_hammer(img, data, acc, seed):
    _hearth_fire(img, "zone", seed)
    img.alpha_composite(_anvil())
    _bar_on_anvil(img, METAL_COLORS[{"cooling": 1, "dull": 2, "true": 3}.get(data["metal"], 2)])
    if data.get("struck"):
        _strike_flash(img, seed)
    _hammer(img, 0)


def _mid_quench(img, data, acc, seed):
    _hearth_fire(img, "embers", seed)
    _trough(img, data["medium"] or "water")
    _held_blade(img, _temp_color(data["temp"]))
    if data["medium"] is None:
        T.icon(img, "forge:oil", (CX + 330, 446), 70, OIL)
        T.icon(img, "forge:water", (CX - 330, 446), 70, WATER)


def _mid_inscribe(img, data, acc, seed):
    _hearth_fire(img, "embers", seed)
    img.alpha_composite(_anvil())
    _gear_on_anvil(img, data, acc.rim, glow=120)
    # the rune's strokes on a plaque above the anvil: carved ones gold, the next one lit, the rest faint
    n = len(data["clue"])
    w = 92
    x0 = CX - n * w / 2
    T.panel(img, (x0 - 18, 140, x0 + n * w + 18, 256), None, fill=(30, 20, 14), glow=True, accent=acc)
    for i, key in enumerate(data["clue"]):
        cx = x0 + w * i + w / 2
        if i < data["carved"]:
            col = GREEN if data["carved_ok"][i] else RED
        elif i == data["carved"]:
            T.soft_glow(img, (cx - 40, 158, cx + 40, 238), alpha(acc.rim, 150), 10)
            col = (255, 226, 150)
        else:
            col = mix(T.PARCHMENT, (0, 0, 0), 0.35)
        _stroke_icon(img, key, (cx, 198), 72, col)


def _mid_success(img, data, acc, seed):
    _hearth_fire(img, "embers", seed)
    img.alpha_composite(_anvil())
    r = data["result"]
    col = _rarity_color(r["rarity"])
    center = (CX, ANVIL_TOP - 66)
    d = ImageDraw.Draw(img)
    for k in range(16):
        a = math.radians(k * 22.5 + 11)
        d.line(P(center[0] + math.cos(a) * 70, center[1] + math.sin(a) * 70, center[0] + math.cos(a) * 190,
                 center[1] + math.sin(a) * 190), fill=alpha(col, 80), width=round(3 * S))
    _gear_on_anvil(img, data, col, glow=220)
    T.icon(img, f"passive:{r['rarity']}", (CX + 96, ANVIL_TOP - 130), 76, col)


def _mid_failed(img, data, acc, seed):
    rng = random.Random(seed)
    _hearth_fire(img, "embers", seed)
    img.alpha_composite(_anvil())
    _gear_on_anvil(img, data, (90, 70, 60), glow=60)
    d = ImageDraw.Draw(img)
    x, y = CX - 30, ANVIL_TOP - 130
    pts = [(x, y)]
    for k in range(6):                                       # a crack across the gear
        x += rng.uniform(4, 16)
        y += 20
        pts.append((x + rng.uniform(-10, 10), y))
    d.line([P(*p) for p in pts], fill=(255, 120, 60, 255), width=round(4 * S))
    _smoke(img, rng, 12, (CX - 300, 160, CX + 300, 440))
    T.banner(img, (CX - 300, 168, CX + 300, 244))
    d = ImageDraw.Draw(img)
    title, tf = _shrink(d, data["result"]["title"], "Cinzel.ttf", "Black", (36, 32, 28, 26, 24), 560)
    T.gold_text(img, (CX, 206), title, tf, "mm", glow=alpha(RED, 140))


LEFT = {"ignite": _left_ignite, "heat": _left_heat, "hammer": _left_hammer, "quench": _left_quench,
        "inscribe": _left_inscribe, "success": _left_success, "failed": _left_failed}
MIDDLE = {"ignite": _mid_ignite, "heat": _mid_heat, "hammer": _mid_hammer, "quench": _mid_quench,
          "inscribe": _mid_inscribe, "success": _mid_success, "failed": _mid_failed}


def _rarity_color(rarity):
    import forge
    return forge.RARITY_COLORS.get(rarity, T.GOLD)


# ── header, corner, stage path ───────────────────────────────────────

def _title(img, data, acc):
    g = data["gear"]
    x0, y0 = SCENE[0], SCENE[1]
    tier_col = T.RARITY.get(g["tier"], T.GOLD)
    T.seal(img, (x0 + 66, y0 + 68), 46, g["icon"], tier_col)
    d = ImageDraw.Draw(img)
    name, nf = _shrink(d, g["name"].upper(), "Cinzel.ttf", "Black", (44, 40, 36, 32), 640)
    T.gold_text(img, (x0 + 128, y0 + 76), name, nf, "ls", glow=alpha(acc.rim, 110))
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (x0 + 130, y0 + 104), T.fit(d, g["sub"].upper(), f, 640), f, mix(T.GOLD_HI, acc.rim, 0.25), 1.4)


def _corner(img, data, acc):
    c = data["corner"]
    x1, y0 = SCENE[2], SCENE[1]
    if c.get("label"):
        T.gold_text(img, (x1 - 26, y0 + 46), c["label"], font("Cinzel.ttf", 40, "Black"), "rm")
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 28, "SemiBold")
    if c.get("seconds"):
        tw = T.width(d, c["seconds"], f)
        T.icon(img, "hourglass", (x1 - 46 - tw, y0 + 96), 26, T.GOLD)
        d = ImageDraw.Draw(img)
        T.text(d, (x1 - 26, y0 + 96), c["seconds"], f, T.PARCHMENT, "rm")
    if c.get("difficulty"):
        _chip(img, x1 - 26, y0 + 146, c["difficulty"], DIFFICULTY_COLOR.get(c["difficulty"], T.GOLD), "r")


def _stage_path(img, data, acc):
    stages = data["stages"]
    n = len(stages)
    top, bottom = 214, 472
    gap = (bottom - top) / (n - 1)
    sx = 968
    d = ImageDraw.Draw(img)
    d.line(P(sx, top, sx, bottom), fill=alpha(T.BRONZE, 220), width=round(2.5 * S))
    for i, st in enumerate(stages):
        y = top + gap * i
        state = st["state"]
        if state == "current":
            T.soft_glow(img, (sx - 40, y - 40, sx + 220, y + 40), alpha(acc.rim, 90), 14)
            T.seal(img, (sx, y), 27, STAGE_ICON[st["key"]], acc.bright)
            color, size = T.GOLD_HI, 28
        else:
            col = {"done": GREEN, "failed": RED}.get(state, T.ASH_DK)
            T.seal(img, (sx, y), 21, STAGE_ICON[st["key"]], col)
            color = {"done": GREEN, "failed": (240, 110, 96)}.get(state, T.ASH)
            size = 26
        d = ImageDraw.Draw(img)
        label = STAGE_LABEL[st["key"]]
        if st.get("points") is not None:
            label += f"  {st['points']}"
        label, f = _shrink(d, label, "Inter.ttf", "Bold" if state == "current" else "SemiBold", (size, 24), 170)
        T.text(d, (sx + 38, y), label, f, color, "lm")
        if state == "done" and st.get("points") is None:
            _check(d, sx + 38 + T.width(d, label, f) + 18, y, 18, GREEN)


# ── bottom panels ─────────────────────────────────────────────────────

def _panel(img, box, title, acc):
    T.panel(img, box, None, fill=mix(acc.panel, (0, 0, 0), 0.2), glow=True, accent=acc)
    _heading(img, box, title)


def _materials_panel(img, data, acc):
    box = PANELS[0]
    _panel(img, box, "On the anvil", acc)
    x0, y0, x1, y1 = box
    rows = data["materials"]
    shown = rows[:4] if len(rows) <= 4 else rows[:3]
    rh = 40
    for i, m in enumerate(shown):
        y = y0 + 84 + rh * i
        T.icon(img, m["icon"], (x0 + 40, y), 36, T.GOLD)
        d = ImageDraw.Draw(img)
        q = f"×{m['qty']}"
        qf = font("Inter.ttf", 24, "Bold")
        qw = T.width(d, q, qf)
        name, f = _shrink(d, m["name"], "Inter.ttf", "SemiBold", (26, 24), x1 - x0 - 100 - qw)
        T.text(d, (x0 + 70, y), name, f, WHITE if not data.get("lost") else T.ASH, "lm")
        T.text(d, (x1 - 22, y), q, qf, T.GOLD_HI, "rm")
    if len(rows) > len(shown):
        d = ImageDraw.Draw(img)
        T.text(d, (x0 + 70, y0 + 84 + rh * 3), f"+ {len(rows) - len(shown)} more", font("Inter.ttf", 24, "Medium"),
               T.ASH, "lm")


def _row(d, box, y, label, value, vcol=WHITE):
    x0, _, x1, _ = box
    T.text(d, (x0 + 24, y), label, font("Inter.ttf", 24, "Medium"), T.PARCHMENT, "lm")
    T.text(d, (x1 - 24, y), value, font("Inter.ttf", 26, "Bold"), vcol, "rm")


def _score_panel(img, data, acc):
    box = PANELS[1]
    _panel(img, box, "Forging", acc)
    s = data["score"]
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    _row(d, box, y0 + 68, "Final score" if data.get("done") else "Score so far", f"{s['total']} / 100", T.GOLD_HI)
    _row(d, box, y0 + 100, "Fails below", f"{s['fail_below']}", (240, 130, 110))
    _row(d, box, y0 + 132, "Stages left", f"{s['left']}" if s["left"] else "none")
    if s.get("bonus"):
        _row(d, box, y0 + 164, "Help", s["bonus"], GREEN)
    bx0, bx1 = x0 + 24, x1 - 24
    T.bar(img, (bx0, y1 - 36, bx1, y1 - 16), s["total"] / 100, RED if data.get("done") and s["total"] < s["fail_below"]
          else acc.hp)
    d = ImageDraw.Draw(img)
    ex = bx0 + (bx1 - bx0) * s["fail_below"] / 100
    d.line(P(ex, y1 - 42, ex, y1 - 10), fill=(240, 110, 96), width=round(2.5 * S))


def _passive_panel(img, data, acc):
    box = PANELS[2]
    _panel(img, box, "Passive", acc)
    x0, y0, x1, y1 = box
    p = data["passive"]
    rarity = p.get("rarity")
    shown = rarity or p.get("cap")
    center = (x0 + 66, y0 + 136)
    col = _rarity_color(shown) if shown else T.ASH_DK
    if shown:
        T.icon(img, f"passive:{shown}", center, 88, col)
    if not rarity:                                            # not forged yet: the cap, dimmed
        veil = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(veil).ellipse(P(center[0] - 48, center[1] - 48, center[0] + 48, center[1] + 48),
                                     fill=(16, 12, 12, 130))
        img.alpha_composite(veil)
    d = ImageDraw.Draw(img)
    tx = x0 + 126
    head = p.get("head") or (rarity or "None yet")
    head, hf = _shrink(d, head, "Inter.ttf", "Bold", (28, 26, 24), x1 - tx - 18)
    T.text(d, (tx, y0 + 80), head, hf, col if rarity else T.PARCHMENT, "lm")
    f = font("Inter.ttf", 24, "Medium")
    lines = []
    for line in p.get("lines", []):
        lines += T.wrap(d, line, f, x1 - tx - 18, 2)
    for i, line in enumerate(lines[:4]):
        T.text(d, (tx, y0 + 116 + i * 31), line, f, T.PARCHMENT if i or rarity else T.ASH, "lm")


# ── the card ──────────────────────────────────────────────────────────

def render_forge(data):
    accent = data.get("accent", "forge")
    acc = T.ACCENTS[accent]
    img = _hall(accent).copy()
    mode = data["mode"]
    seed = data.get("seed", 1)
    MIDDLE[mode](img, data, acc, seed)
    shade = Image.new("RGBA", P(SCENE[2] - SCENE[0], 150), (0, 0, 0, 0))
    shade.putalpha(Image.linear_gradient("L").rotate(180).resize(shade.size).point(lambda v: v * 0.55))
    img.alpha_composite(shade, P(SCENE[0], SCENE[1]))
    T.frame(img, SCENE, 0.8)
    _title(img, data, acc)
    _corner(img, data, acc)
    LEFT[mode](img, data, acc)
    _stage_path(img, data, acc)
    _materials_panel(img, data, acc)
    _score_panel(img, data, acc)
    _passive_panel(img, data, acc)
    warn = T.ELEMENT_ACCENTS["Blood"] if mode == "failed" else acc
    _warning(img, {"warning": data["warning"], "warning_icon": data.get("warning_icon", "forge:anvil")}, warn, WARN)
    T.frame(img, (6, 6, W - 6, H - 6), 1.0)
    return T.finish(img)
