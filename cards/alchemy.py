"""
The Alchemy Chamber: the /craft card that the bot edits after every decision (docs/alchemy.md).

  ┌ scene window: a stone chamber, a glowing eight-trigram circle on the floor and a bronze ding cauldron
  │   top left: pill grade seal, pill name, grade · effect · duration
  │   top right: round X / Y, seconds to choose, difficulty chip
  │   right: the stages as a path (done ✓, current lit)
  │   middle + left, per stage: fire and heat gauge, floating herbs, Yin-Yang, the pulsing pill,
  │   the Pill Tribulation (storm, lightning), or the result (finished pill / explosion)
  ├ "In the cauldron" · "Refining" · "Pill patterns" (the tribulation swaps the first two for one panel)
  └ warning bar: the stage's hint or omen

render_alchemy(data) takes plain data (bot/craft_card.card_data), so it can run off the event loop.
The chamber and the cauldron are cached per accent; only the fire, effects and panels are drawn each time.
Discord shows the card at under half size on a computer, so nothing on it is under 24px.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from .battle import _check, _chip, _heading, _shrink, _warning
from .theme import P, S, alpha, cjk, font, mix

W, H = 1200, 880
SCENE = (16, 16, 1184, 500)
PANELS = [(16, 512, 400, 742), (412, 512, 788, 742), (800, 512, 1184, 742)]
WARN = (16, 754, 1184, 864)

CX = 600                      # the cauldron's centre line
RIM_Y = 330                   # top of the cauldron
FLOOR_Y = 466                 # centre of the formation circle
ARC_C, ARC_R = (600, 424), 214      # the heat gauge
ARC_A0, ARC_SPAN = 195, 150         # 0° at 195°, 100° at 345° (Pillow angles, clockwise from 3 o'clock)

CN = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
STAGE_CHAR = {1: "火", 2: "药", 3: "合", 4: "凝", 5: "封", 6: "劫"}
STAGE_LABEL = {1: "Ignite", 2: "Add herbs", 3: "Fuse", 4: "Condense", 5: "Seal", 6: "Tribulation"}
HERB_CHAR = {"qi": "气", "healing": "愈", "purity": "净", "breakthrough": "破", "core": "核"}
HERB_COLOR = {"qi": (110, 170, 240), "healing": (232, 96, 96), "purity": (100, 206, 196),
              "breakthrough": (204, 150, 92), "core": (236, 120, 60)}
AGE_COLOR = {10: (170, 160, 150), 50: (120, 206, 130), 100: (92, 214, 188), 500: (120, 170, 250),
             1000: (250, 204, 96)}
DIFFICULTY_COLOR = {"Normal": (96, 196, 110), "Hard": (222, 182, 70), "Very Hard": (236, 140, 52),
                    "Extreme": (226, 72, 56), "Super Hard": (168, 110, 240)}
HEAT_CHIP = {"cold": ("Too cold", (90, 150, 240)), "zone": ("Steady", (236, 184, 70)),
             "hot": ("Too hot!", (226, 60, 44))}
YIN, YANG = (120, 140, 250), (255, 176, 70)
PATTERN_WORD = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
WHITE = (255, 248, 232)
GREEN = (110, 214, 140)


# ── the chamber (cached) ──────────────────────────────────────────────

def _bricks(d, box, color, seed):
    x0, y0, x1, y1 = box
    r = random.Random(seed)
    bh, bw = 30, 74
    y, row = y0, 0
    while y < y1:
        x = x0 - (bw / 2 if row % 2 else 0)
        while x < x1:
            shade = r.uniform(-0.08, 0.1)
            fill = mix(color, (0, 0, 0), 0.2 + shade) if shade > 0 else mix(color, (255, 255, 255), -shade * 0.25)
            d.rectangle(P(max(x0, x + 1.5), y + 1.5, min(x1, x + bw - 1.5), min(y1, y + bh - 1.5)),
                        fill=alpha(fill, 255))
            x += bw
        y += bh
        row += 1


def _trigram(d, cx, cy, angle, size, color):
    """One of the eight trigrams: three bars, some broken, lying along the circle."""
    r = random.Random(round(angle))
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for k in range(3):
        off = (k - 1) * size * 0.42
        bx, by = cx + ca * off, cy + sa * off * 0.32
        tx, ty = -sa, ca * 0.32                    # along the ring (squashed into the floor's perspective)
        half = size * 0.55
        if r.random() < 0.5:
            d.line(P(bx - tx * half, by - ty * half, bx + tx * half, by + ty * half), fill=color, width=round(3 * S))
        else:
            for sgn in (-1, 1):
                d.line(P(bx + tx * half * 0.18 * sgn, by + ty * half * 0.18 * sgn, bx + tx * half * sgn,
                         by + ty * half * sgn), fill=color, width=round(3 * S))


def _formation(img, acc):
    """The glowing eight-trigram circle on the floor."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = alpha(mix(acc.rim, (255, 255, 255), 0.25), 230)
    for rx, ry, wd in ((330, 58, 3), (300, 50, 2), (210, 34, 2)):
        d.ellipse(P(CX - rx, FLOOR_Y - ry, CX + rx, FLOOR_Y + ry), outline=col, width=round(wd * S))
    for i in range(8):
        a = i * 45 + 22.5
        x = CX + math.cos(math.radians(a)) * 256
        y = FLOOR_Y + math.sin(math.radians(a)) * 42
        _trigram(d, x, y, a, 22, col)
    for i in range(24):
        a = math.radians(i * 15)
        x0, y0 = CX + math.cos(a) * 300, FLOOR_Y + math.sin(a) * 50
        x1, y1 = CX + math.cos(a) * 316, FLOOR_Y + math.sin(a) * 54
        d.line(P(x0, y0, x1, y1), fill=col, width=round(1.5 * S))
    glow = layer.filter(ImageFilter.GaussianBlur(6 * S))
    img.alpha_composite(glow)
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def _clouds(img, acc, seed):
    """Storm clouds under the ceiling for the Pill Tribulation."""
    x0, y0, x1, _ = SCENE
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = random.Random(seed)
    for _ in range(26):
        cx, cy = r.uniform(x0 - 40, x1 + 40), r.uniform(y0 - 10, y0 + 150)
        rw, rh = r.uniform(80, 190), r.uniform(26, 60)
        d.ellipse(P(cx - rw, cy - rh, cx + rw, cy + rh),
                  fill=alpha(mix(acc.mist, (10, 6, 20), r.uniform(0.1, 0.6)), r.randint(150, 230)))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14 * S)))


@lru_cache(maxsize=4)
def _chamber(accent):
    """The whole card background with the empty chamber in the scene window (S×, RGBA)."""
    acc = T.ACCENTS[accent]
    img = T.canvas(W, H, seed=23, accent=accent)
    x0, y0, x1, y1 = SCENE
    wall_end = 404
    wall = T.vgradient(P(x1 - x0, wall_end - y0), acc.sky[0], acc.sky[1])
    img.alpha_composite(wall, P(x0, y0))
    d = ImageDraw.Draw(img)
    _bricks(d, (x0, y0, x1, wall_end), mix(acc.sky[1], (0, 0, 0), 0.45), 5)
    floor = T.vgradient(P(x1 - x0, y1 - wall_end), mix(acc.sky[1], (0, 0, 0), 0.35), mix(acc.sky[0], (0, 0, 0), 0.5))
    img.alpha_composite(floor, P(x0, wall_end))
    d = ImageDraw.Draw(img)
    d.line(P(x0, wall_end, x1, wall_end), fill=alpha(mix(acc.rim, (0, 0, 0), 0.4), 255), width=round(2 * S))
    for k in range(15):                                     # flagstones fanning out from the cauldron
        x = x0 + (x1 - x0) * k / 14
        d.line(P(CX + (x - CX) * 0.45, wall_end, x, y1), fill=alpha(mix(acc.sky[1], (0, 0, 0), 0.6), 255),
               width=max(1, S))
    if accent == "tribulation":
        _clouds(img, acc, 9)
    # warm light behind the cauldron, dark corners
    T.soft_glow(img, (CX - 340, 180, CX + 340, 500), alpha(acc.rim, 46), 40)
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for k in range(10):
        a = 18 * (10 - k)
        sd.rectangle(P(x0 + k * 14, y0, x0 + (k + 1) * 14, y1), fill=(0, 0, 0, a))
        sd.rectangle(P(x1 - (k + 1) * 14, y0, x1 - k * 14, y1), fill=(0, 0, 0, a))
    img.alpha_composite(shade)
    _formation(img, acc)
    return img


def _meander(d, x0, x1, y, h, color):
    """A band of 回 key pattern."""
    step = h * 1.25
    x = x0
    while x + step <= x1:
        pts = [(x, y + h), (x, y), (x + step * 0.8, y), (x + step * 0.8, y + h * 0.7), (x + step * 0.3, y + h * 0.7),
               (x + step * 0.3, y + h * 0.35)]
        d.line([P(*p) for p in pts], fill=color, width=round(2 * S), joint="curve")
        x += step


@lru_cache(maxsize=2)
def _ding(dark=False):
    """The bronze ding cauldron as a card-sized S× RGBA layer: three legs, two handles, a meander band with 丹."""
    img = Image.new("RGBA", P(W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bronze_dk, bronze, gold = (64, 40, 18), (150, 104, 50), (232, 190, 110)
    if dark:
        bronze_dk, bronze, gold = mix(bronze_dk, (0, 0, 0), 0.5), mix(bronze, (20, 16, 14), 0.6), mix(gold, (30, 24, 20), 0.6)
    # legs (behind the bowl): left, right and the front one
    for lx, wd in ((CX - 98, 22), (CX + 98, 22), (CX, 26)):
        d.polygon([P(lx - wd / 2, 420), P(lx + wd / 2, 420), P(lx + wd * 0.38, 478), P(lx - wd * 0.38, 478)],
                  fill=alpha(bronze_dk, 255))
        d.line(P(lx - wd * 0.15, 424, lx - wd * 0.1, 474), fill=alpha(bronze, 255), width=round(2 * S))
    # handles
    for hx in (CX - 96, CX + 96):
        d.rounded_rectangle(P(hx - 22, RIM_Y - 64, hx + 22, RIM_Y + 4), radius=8 * S, fill=alpha(bronze_dk, 255),
                            outline=alpha(gold, 255), width=round(2 * S))
        d.rounded_rectangle(P(hx - 11, RIM_Y - 52, hx + 11, RIM_Y - 6), radius=4 * S, fill=(0, 0, 0, 0))
    # bowl: a half ellipse lit from the left
    bw, bh = 150, 116
    bowl = Image.new("L", P(2 * bw, bh), 0)
    ImageDraw.Draw(bowl).ellipse((0, -bowl.size[1], bowl.size[0] - 1, bowl.size[1] - 1), fill=255)
    shade = Image.new("RGBA", bowl.size)
    for x in range(bowl.size[0]):
        t = x / (bowl.size[0] - 1)
        light = max(0.0, 1 - abs(t - 0.38) * 2.4)
        c = mix(mix(bronze_dk, bronze, min(1, 0.25 + t * 2) if t < 0.5 else (1 - t) * 2), gold, light * 0.65)
        ImageDraw.Draw(shade).line((x, 0, x, bowl.size[1]), fill=c + (255,))
    shade.putalpha(bowl)
    img.alpha_composite(shade, P(CX - bw, RIM_Y + 10))
    d = ImageDraw.Draw(img)
    # meander band with the 丹 seal
    band = (CX - 142, RIM_Y + 22, CX + 142, RIM_Y + 50)
    d.rectangle(P(*band), fill=alpha(mix(bronze_dk, (0, 0, 0), 0.2), 255))
    d.line(P(band[0], band[1], band[2], band[1]), fill=alpha(gold, 255), width=round(2 * S))
    d.line(P(band[0] + 6, band[3], band[2] - 6, band[3]), fill=alpha(gold, 255), width=round(2 * S))
    _meander(d, band[0] + 10, CX - 28, band[1] + 6, 16, alpha(gold, 230))
    _meander(d, CX + 30, band[2] - 4, band[1] + 6, 16, alpha(gold, 230))
    d.ellipse(P(CX - 22, band[1] - 2, CX + 22, band[3] + 2), fill=alpha(bronze_dk, 255), outline=alpha(gold, 255),
              width=round(2 * S))
    T.text(d, (CX, (band[1] + band[3]) / 2), "丹", cjk(24), alpha(gold, 255), "mm", shadow=False)
    # rim and the dark mouth
    d.ellipse(P(CX - 160, RIM_Y - 12, CX + 160, RIM_Y + 24), fill=alpha(bronze, 255), outline=alpha(gold, 255),
              width=round(2.5 * S))
    d.ellipse(P(CX - 140, RIM_Y - 6, CX + 140, RIM_Y + 16), fill=alpha(mix(bronze_dk, (0, 0, 0), 0.6), 255))
    return img


# ── fire, sparks, smoke ───────────────────────────────────────────────

class _Local:
    """A small drawing layer over part of the card, so blurs stay cheap. Takes card coordinates."""

    def __init__(self, box):
        self.x0, self.y0 = box[0], box[1]
        self.img = Image.new("RGBA", P(box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def p(self, pts):
        return [(x - self.x0 * S, y - self.y0 * S) for x, y in pts]

    def paste(self, img, layer):
        img.alpha_composite(layer, P(self.x0, self.y0))


def _flame_poly(x, base, h, w, sway):
    pts = []
    n = 14
    for i in range(n + 1):
        t = i / n
        half = w * (1 - t) ** 0.75 * min(1, 0.45 + t * 4)
        pts.append((x - half + sway * t * t, base - h * t))
    for i in range(n, -1, -1):
        t = i / n
        half = w * (1 - t) ** 0.75 * min(1, 0.45 + t * 4)
        pts.append((x + half + sway * t * t, base - h * t))
    return [P(*p) for p in pts]


FIRE = {
    # state: (back height, front height, outer, middle, core, sparks, white cores)
    "cold":   (46, 22, (60, 110, 236), (110, 170, 255), (200, 230, 255), 6, False),
    "zone":   (96, 44, (236, 136, 40), (250, 190, 70), (255, 238, 170), 20, False),
    "hot":    (176, 74, (206, 40, 26), (246, 96, 36), (255, 190, 90), 48, True),
    "embers": (22, 12, (180, 70, 30), (230, 120, 50), (255, 190, 110), 10, False),
}


def _fire_layer(img, state, rng, front):
    back_h, front_h, outer, middle, core, _, white = FIRE[state]
    h = front_h if front else back_h
    base = 488 if front else 446
    xs = [CX - 150 + k * 300 / 10 for k in range(11)] if front else [CX - 190 + k * 380 / 12 for k in range(13)]
    loc = _Local((CX - 290, max(SCENE[1], base - h * 1.3 - 40), CX + 290, SCENE[3]))
    d = loc.d
    for i, x in enumerate(xs):
        edge = 1 - abs(x - CX) / (230 if front else 260)
        fh = h * (0.55 + 0.45 * max(0.2, edge)) * rng.uniform(0.75, 1.15)
        fw = (16 if front else 22) * rng.uniform(0.8, 1.2)
        sway = rng.uniform(-14, 14)
        d.polygon(loc.p(_flame_poly(x, base, fh, fw, sway)), fill=alpha(outer, 230))
        d.polygon(loc.p(_flame_poly(x, base, fh * 0.7, fw * 0.62, sway * 0.7)), fill=alpha(middle, 240))
        d.polygon(loc.p(_flame_poly(x, base, fh * 0.42, fw * 0.36, sway * 0.4)), fill=alpha(core, 250))
        if white and i % 2 == 0:
            d.polygon(loc.p(_flame_poly(x, base, fh * 0.26, fw * 0.22, sway * 0.2)), fill=(255, 255, 250, 255))
    loc.paste(img, loc.img.filter(ImageFilter.GaussianBlur(10 * S)))
    loc.paste(img, loc.img.filter(ImageFilter.GaussianBlur(1.2 * S)))


def _fire_glow(img, state):
    _, _, outer, middle, _, _, _ = FIRE[state]
    strength = {"cold": 60, "zone": 110, "hot": 170, "embers": 40}[state]
    T.soft_glow(img, (CX - 260, 330, CX + 260, 500), alpha(middle, strength), 30)


def _sparks(img, state, rng):
    n = FIRE[state][5]
    _, _, outer, middle, core, _, _ = FIRE[state]
    d = ImageDraw.Draw(img)
    top = {"cold": 360, "zone": 260, "hot": 150, "embers": 380}[state]
    for _ in range(n):
        x, y = CX + rng.uniform(-240, 240), rng.uniform(top, 440)
        r = rng.uniform(1.2, 3.0)
        col = mix(core, (255, 255, 255), rng.random() * 0.5)
        if rng.random() < 0.4:
            d.line(P(x, y, x + rng.uniform(-6, 6), y - rng.uniform(8, 20)), fill=alpha(col, 200), width=max(1, S))
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=alpha(col, rng.randint(150, 255)))


def _fire(img, state, seed, front_only=False):
    rng = random.Random(seed)
    if not front_only:
        _fire_glow(img, state)
        _fire_layer(img, state, rng, front=False)
    return rng


def _smoke(img, rng, n=14, area=(CX - 360, 150, CX + 360, 470), color=(110, 102, 96)):
    x0, y0, x1, y1 = area
    loc = _Local(SCENE)
    for _ in range(n):
        cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(40, 110)
        loc.d.ellipse(loc.p([P(cx - r, cy - r * 0.7), P(cx + r, cy + r * 0.7)]),
                      fill=alpha(mix(color, (0, 0, 0), rng.random() * 0.5), rng.randint(90, 170)))
    loc.paste(img, loc.img.filter(ImageFilter.GaussianBlur(18 * S)))


# ── middle pieces ─────────────────────────────────────────────────────

def _heat_color(v):
    blue, gold, red = (80, 140, 250), (246, 190, 70), (236, 56, 40)
    return mix(blue, gold, v / 50) if v <= 50 else mix(gold, red, (v - 50) / 50)


def _arc_point(v, r=ARC_R):
    a = math.radians(ARC_A0 + ARC_SPAN * v / 100)
    return ARC_C[0] + math.cos(a) * r, ARC_C[1] + math.sin(a) * r


def _heat_gauge(img, heat):
    """The arc over the cauldron: 0°–100°, blue → gold → red, with a marker at the heat. The safe zone is never drawn."""
    cx, cy = ARC_C
    r = ARC_R
    d = ImageDraw.Draw(img)
    box = P(cx - r, cy - r, cx + r, cy + r)
    d.arc(P(cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5), ARC_A0, ARC_A0 + ARC_SPAN, fill=(0, 0, 0, 200),
          width=round(18 * S))
    for k in range(100):
        a0 = ARC_A0 + ARC_SPAN * k / 100
        d.arc(box, a0, a0 + ARC_SPAN / 100 + 0.4, fill=_heat_color(k + 0.5) + (255,), width=round(8 * S))
    for v in range(0, 101, 10):
        x0, y0 = _arc_point(v, r + 10)
        x1, y1 = _arc_point(v, r + (24 if v % 50 == 0 else 18))
        d.line(P(x0, y0, x1, y1), fill=alpha(T.GOLD_HI, 220), width=round((2.5 if v % 50 == 0 else 1.5) * S))
    f = font("Inter.ttf", 24, "Bold")
    for v, dx, dy, anchor in ((0, -6, 26, "mm"), (50, 0, 30, "mm"), (100, 6, 26, "mm")):
        x, y = _arc_point(v, r - 34)
        T.text(d, (x + dx, y + dy - 22), f"{v}°", f, T.PARCHMENT, anchor)
    mx, my = _arc_point(max(0, min(100, heat)))
    col = _heat_color(max(0, min(100, heat)))
    T.soft_glow(img, (mx - 24, my - 24, mx + 24, my + 24), alpha(col, 220), 8)
    d = ImageDraw.Draw(img)
    d.ellipse(P(mx - 15, my - 15, mx + 15, my + 15), fill=(250, 246, 236, 255), outline=(30, 20, 14, 255),
              width=round(2 * S))
    d.ellipse(P(mx - 7, my - 7, mx + 7, my + 7), fill=(30, 20, 14, 255))


def _seal_label(img, center, r, char, color, label, size=24):
    T.medallion(img, center, r, char, color)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", size, "Bold")
    T.text(d, (center[0], center[1] + r + 22), T.fit(d, label, f, 220), f, WHITE, "mm")


def _floating_herbs(img, herbs):
    n = len(herbs)
    if not n:
        return
    gap = 230 if n <= 2 else 170
    for i, h in enumerate(herbs):
        x = CX + (i - (n - 1) / 2) * gap
        y = 200 + (10 if i % 2 else 0)
        col = HERB_COLOR.get(h["type"], T.GOLD)
        T.soft_glow(img, (x - 60, y - 60, x + 60, y + 60), alpha(col, 120), 14)
        label = h["name"] + (f" ×{h['count']}" if h.get("count", 1) > 1 else "")
        _seal_label(img, (x, y), 40, HERB_CHAR.get(h["type"], "草"), col, label, 26)


def _yin_yang(img, center, r, yin, yang):
    cx, cy = center
    total = max(1, yin + yang)
    tint = mix(YIN, YANG, yang / total)
    T.soft_glow(img, (cx - r * 1.7, cy - r * 1.7, cx + r * 1.7, cy + r * 1.7), alpha(tint, 170), 22)
    size = round(2 * r * S)
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dd = ImageDraw.Draw(disc)
    light, dark = (250, 232, 196, 255), (26, 22, 52, 255)
    dd.ellipse((0, 0, size - 1, size - 1), fill=light)
    dd.pieslice((0, 0, size - 1, size - 1), 90, 270, fill=dark)          # left half dark
    q = size // 4
    dd.ellipse((q, 0, 3 * q, 2 * q), fill=light)                         # top bulge light
    dd.ellipse((q, 2 * q, 3 * q, 4 * q), fill=dark)                      # bottom bulge dark
    e = size // 14
    dd.ellipse((2 * q - e, q - e, 2 * q + e, q + e), fill=dark)
    dd.ellipse((2 * q - e, 3 * q - e, 2 * q + e, 3 * q + e), fill=light)
    img.alpha_composite(disc, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), outline=T.GOLD, width=round(3 * S))
    d.ellipse(P(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), outline=alpha(tint, 200), width=round(1.5 * S))


def _rings(img, center, r0, step, earned, cap, total=9, color=T.GOLD_HI, faint=None):
    """Pill patterns as rings: bright = earned, faint = still possible, dotted = locked by herb age."""
    cx, cy = center
    d = ImageDraw.Draw(img)
    faint = faint or T.GOLD
    for i in range(total):
        r = r0 + step * (i + 1)
        box = P(cx - r, cy - r, cx + r, cy + r)
        if i < earned:
            d.ellipse(box, outline=alpha(color, 255), width=round(2.6 * S))
        elif i < cap:
            d.ellipse(box, outline=alpha(faint, 90), width=round(1.6 * S))
        else:
            for k in range(0, 360, 12):
                a = math.radians(k)
                x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
                d.ellipse(P(x - 1.3, y - 1.3, x + 1.3, y + 1.3), fill=alpha(T.ASH_DK, 220))


def _pill(img, center, r, color, glow=160):
    cx, cy = center
    T.soft_glow(img, (cx - r * 3, cy - r * 3, cx + r * 3, cy + r * 3), alpha(color, glow), r * 0.9)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=mix(color, (255, 255, 255), 0.2) + (255,),
              outline=alpha(mix(color, (255, 255, 255), 0.6), 255), width=round(2 * S))
    d.ellipse(P(cx - r * 0.55, cy - r * 0.6, cx - r * 0.05, cy - r * 0.15), fill=(255, 255, 255, 150))


def _lightning(img, start, end, seed):
    rng = random.Random(seed)
    pts = [start]
    n = 9
    for i in range(1, n):
        t = i / n
        x = start[0] + (end[0] - start[0]) * t + rng.uniform(-34, 34)
        y = start[1] + (end[1] - start[1]) * t + rng.uniform(-10, 10)
        pts.append((x, y))
    pts.append(end)
    loc = _Local((SCENE[0], SCENE[1], SCENE[2], 330))
    d = loc.d
    for k in (3, 6):                                     # two forks off the main bolt
        bx, by = pts[k]
        d.line(loc.p([P(bx, by), P(bx + rng.uniform(-60, 60), by + rng.uniform(30, 60))]), fill=(210, 190, 255, 255),
               width=round(3 * S))
    d.line(loc.p([P(*p) for p in pts]), fill=(220, 200, 255, 255), width=round(12 * S), joint="curve")
    wide = loc.img.filter(ImageFilter.GaussianBlur(14 * S))
    for _ in range(3):
        loc.paste(img, wide)
    loc.paste(img, loc.img.filter(ImageFilter.GaussianBlur(3 * S)))
    d = ImageDraw.Draw(img)
    d.line([P(*p) for p in pts], fill=(255, 255, 255, 255), width=round(5 * S), joint="curve")
    ex, ey = end
    T.soft_glow(img, (ex - 40, ey - 40, ex + 40, ey + 40), (255, 255, 255, 220), 10)


# ── left info column ──────────────────────────────────────────────────

LX = 46


def _caption(img, y, s, color=T.GOLD):
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (LX, y), T.fit(d, s.upper(), f, 300), f, color, 1.8)


def _note(img, y, s, color=T.ASH, lines=2, size=24):
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", size, "Medium")
    for i, line in enumerate(T.wrap(d, s, f, 290, lines)):
        T.text(d, (LX, y + i * 31), line, f, color, "lm")


def _big(img, y, s, glow=None, size=96):
    T.gold_text(img, (LX, y), s, font("Cinzel.ttf", size, "Black"), "ls", glow=glow)


def _big_cjk(img, y, s, color):
    d = ImageDraw.Draw(img)
    T.text(d, (LX - 4, y), s, cjk(88), color, "ls")


def _left_ignite(img, data, acc):
    _big(img, 286, f"{data['heat']}°", glow=alpha(_heat_color(data["heat"]), 110))
    _caption(img, 318, "Cauldron heat")
    label, col = HEAT_CHIP[data["heat_state"]]
    _chip(img, LX, 374, label, col)
    _note(img, 428, f"Safe zone {data['zone_width']}° wide, hidden. Read the fire.")


def _left_herbs(img, data, acc):
    _big(img, 286, data["next_pos"], glow=alpha(acc.rim, 90))
    _caption(img, 318, "Herb to add")
    _note(img, 368, f"{data['placed']} of {data['total']} in the cauldron", T.PARCHMENT)
    _note(img, 410, "Read the clues below. A wrong herb causes a backlash.")


def _balance_bar(img, y, label, value, color):
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 26, "Bold")
    T.text(d, (LX, y - 30), label, f, mix(color, (255, 255, 255), 0.4), "lm")
    T.text(d, (LX + 290, y - 30), str(value), font("Inter.ttf", 30, "Bold"), WHITE, "rm")
    x0, x1 = LX, LX + 290
    T.bar(img, (x0, y - 12, x1, y + 16), value / 100, color)
    d = ImageDraw.Draw(img)
    mx = x0 + (x1 - x0) * 0.5
    d.line(P(mx, y - 20, mx, y + 24), fill=T.GOLD_HI, width=round(3 * S))


def _left_balance(img, data, acc):
    _caption(img, 196, "Seal the core" if data["mode"] == "seal" else "Balance at 50")
    _balance_bar(img, 268, "Yin", data["yin"], YIN)
    _balance_bar(img, 356, "Yang", data["yang"], YANG)
    _note(img, 410, f"Move {data['move']} of {data['moves']}" + (" · wild herbs push the bars" if data.get("wild")
                                                                 else ""), T.PARCHMENT)


def _left_condense(img, data, acc):
    _big_cjk(img, 290, "凝", mix(acc.rim, (255, 255, 255), 0.3))
    _caption(img, 318, "Pill pulse")
    d = ImageDraw.Draw(img)
    T.diamonds(d, LX + 12, 360, data["pulse"] + 1, total=5, size=12, color=acc.rim)
    _note(img, 408, data["pulse_text"], T.PARCHMENT, size=26)


def _left_tribulation(img, data, acc):
    _big_cjk(img, 290, "九纹", (244, 236, 255))
    _caption(img, 318, "Nine patterns await", mix(acc.rim, (255, 255, 255), 0.3))
    _note(img, 366, f"Strike {data['strike']} of {data['strikes']}", WHITE, size=26)
    _note(img, 404, f"{data['blocked']} blocked so far. Block all {data['strikes']} for the ninth ring.")


def _left_success(img, data, acc):
    n = data["result"]
    _big_cjk(img, 290, CN[n] + "纹", T.GOLD_HI)
    _caption(img, 318, f"{PATTERN_WORD[n]}-pattern pill")
    _note(img, 366, f"Effect ×{data['effect']:.2f}", WHITE, size=26)
    _note(img, 402, f"Toxicity +{data['toxicity']}", T.PARCHMENT, size=26)


def _left_exploded(img, data, acc):
    _caption(img, 196, "Final score")
    _big(img, 290, f"{data['score']:.0%}", glow=alpha((236, 72, 52), 120))
    _note(img, 330, data["why"], T.PARCHMENT)


# ── middles ───────────────────────────────────────────────────────────

def _mid_ignite(img, data, acc, seed):
    state = data["heat_state"]
    rng = _fire(img, state, seed)
    img.alpha_composite(_ding())
    _fire_layer(img, state, rng, front=True)
    _sparks(img, state, rng)
    _heat_gauge(img, data["heat"])


def _steady(img, seed, state="zone"):
    rng = _fire(img, state, seed)
    img.alpha_composite(_ding())
    _fire_layer(img, state, rng, front=True)
    _sparks(img, state, rng)
    return rng


def _mid_herbs(img, data, acc, seed):
    _steady(img, seed)
    _floating_herbs(img, data["herbs_left"])


def _mid_balance(img, data, acc, seed):
    _steady(img, seed)
    _yin_yang(img, (CX, 214), 66, data["yin"], data["yang"])


def _mid_condense(img, data, acc, seed):
    rng = _fire(img, "zone", seed)
    img.alpha_composite(_ding())
    p = data["pulse"]
    color = mix(T.RARITY.get(data["pill"]["grade"], T.GOLD), (255, 236, 190), 0.35)
    T.soft_glow(img, (CX - 150, RIM_Y - 30, CX + 150, RIM_Y + 30), alpha(color, 60 + 40 * p), 14)
    _pill(img, (CX, RIM_Y - 18 - 4 * p), 20 + 4 * p, color, glow=70 + 40 * p)
    _fire_layer(img, "zone", rng, front=True)
    _sparks(img, "zone", rng)


def _mid_tribulation(img, data, acc, seed):
    rng = _fire(img, "zone", seed)
    img.alpha_composite(_ding())
    _fire_layer(img, "zone", rng, front=True)
    center = (CX, 196)
    T.soft_glow(img, (CX - 110, 86, CX + 110, 306), alpha(acc.rim, 120), 20)
    _rings(img, center, 18, 8, 8, 9, color=(236, 226, 255), faint=(236, 226, 255))
    _pill(img, center, 18, (150, 160, 255), glow=200)
    start = {"left": (380, 18), "above": (CX - 30, 16), "right": (820, 18)}[data["strike_dir"]]
    end = {"left": (CX - 60, 180), "above": (CX - 6, 150), "right": (CX + 60, 180)}[data["strike_dir"]]
    _lightning(img, start, end, seed + data["strike"])


def _mid_success(img, data, acc, seed):
    rng = _fire(img, "embers", seed)
    img.alpha_composite(_ding())
    _fire_layer(img, "embers", rng, front=True)
    n = data["result"]
    color = mix(T.RARITY.get(data["pill"]["grade"], T.GOLD), (255, 236, 190), 0.3)
    center = (CX, 200)
    d = ImageDraw.Draw(img)
    for k in range(16):                                   # rays
        a = math.radians(k * 22.5 + 11)
        d.line(P(center[0] + math.cos(a) * 40, center[1] + math.sin(a) * 40, center[0] + math.cos(a) * 128,
                 center[1] + math.sin(a) * 128), fill=alpha(color, 70), width=round(3 * S))
    _rings(img, center, 18, 8, n, n, color=T.GOLD_HI)
    _pill(img, center, 20, color, glow=230)


def _mid_exploded(img, data, acc, seed):
    rng = random.Random(seed)
    img.alpha_composite(_ding(dark=True))
    d = ImageDraw.Draw(img)
    for _ in range(26):                                   # soot
        x, y = CX + rng.uniform(-420, 420), rng.uniform(120, 490)
        r = rng.uniform(6, 26)
        d.ellipse(P(x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(8, 6, 6, rng.randint(120, 200)))
    _smoke(img, rng)
    _fire(img, "embers", seed, front_only=True)
    _sparks(img, "embers", rng)
    for i, h in enumerate(data["herbs"][:4]):             # herbs flung across the floor
        x = CX + (-330, 300, -220, 370)[i]
        y = (452, 470, 482, 440)[i]
        T.medallion(img, (x, y), 22, HERB_CHAR.get(h["type"], "草"), mix(HERB_COLOR.get(h["type"], T.GOLD), (60, 50, 40), 0.4))
    T.banner(img, (CX - 262, 214, CX + 262, 290))
    title = "The core shattered" if data.get("core_lost") else "Cauldron exploded"
    d = ImageDraw.Draw(img)
    title, tf = _shrink(d, title.upper(), "Cinzel.ttf", "Black", (40, 36, 32), 490)
    T.gold_text(img, (CX, 252), title, tf, "mm", glow=alpha((236, 72, 52), 140))


LEFT = {"ignite": _left_ignite, "herbs": _left_herbs, "fuse": _left_balance, "seal": _left_balance,
        "condense": _left_condense, "tribulation": _left_tribulation, "success": _left_success,
        "exploded": _left_exploded}
MIDDLE = {"ignite": _mid_ignite, "herbs": _mid_herbs, "fuse": _mid_balance, "seal": _mid_balance,
          "condense": _mid_condense, "tribulation": _mid_tribulation, "success": _mid_success,
          "exploded": _mid_exploded}


# ── header, corner, stage path ───────────────────────────────────────

def _title(img, data, acc):
    pill = data["pill"]
    x0, y0 = SCENE[0], SCENE[1]
    T.seal(img, (x0 + 66, y0 + 68), 46, f"emblem:pill:{pill.get('kind', 'qi')}:{pill['grade']}",
           T.RARITY.get(pill["grade"], T.GOLD))
    d = ImageDraw.Draw(img)
    name, nf = _shrink(d, pill["name"].upper(), "Cinzel.ttf", "Black", (48, 44, 40, 36), 700)
    T.gold_text(img, (x0 + 128, y0 + 76), name, nf, "ls", glow=alpha(acc.rim, 110))
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (x0 + 130, y0 + 104), T.fit(d, pill["sub"].upper(), f, 700), f, mix(T.GOLD_HI, acc.rim, 0.25), 1.4)


def _corner(img, data, acc):
    c = data["corner"]
    x1, y0 = SCENE[2], SCENE[1]
    T.gold_text(img, (x1 - 26, y0 + 46), c["label"], font("Cinzel.ttf", 44, "Black"), "rm")
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
    gap = min(66, (bottom - top) / max(1, n - 1))
    y0 = top + ((bottom - top) - gap * (n - 1)) / 2
    sx = 968
    d = ImageDraw.Draw(img)
    d.line(P(sx, y0, sx, y0 + gap * (n - 1)), fill=alpha(T.BRONZE, 220), width=round(2.5 * S))
    for i, st in enumerate(stages):
        y = y0 + gap * i
        state = st["state"]
        if state == "current":
            T.soft_glow(img, (sx - 40, y - 40, sx + 220, y + 40), alpha(acc.rim, 90), 14)
            T.medallion(img, (sx, y), 27, STAGE_CHAR[st["key"]], acc.bright)
            color, f = T.GOLD_HI, font("Inter.ttf", 28, "Bold")
        else:
            col = {"done": GREEN, "failed": (226, 72, 56)}.get(state, T.ASH_DK)
            T.medallion(img, (sx, y), 21, STAGE_CHAR[st["key"]], col)
            color = {"done": GREEN, "failed": (240, 110, 96)}.get(state, T.ASH)
            f = font("Inter.ttf", 26, "SemiBold")
        d = ImageDraw.Draw(img)
        label, f = _shrink(d, STAGE_LABEL[st["key"]], "Inter.ttf", "Bold" if state == "current" else "SemiBold",
                           (f.size // S, 24), 168)
        T.text(d, (sx + 38, y), label, f, color, "lm")
        lw = T.width(d, label, f)
        if state == "done":
            _check(d, sx + 38 + lw + 18, y, 18, GREEN)
        elif state == "failed":
            xm = sx + 38 + lw + 18
            for sgn in (-1, 1):
                d.line(P(xm - 8, y - 8 * sgn, xm + 8, y + 8 * sgn), fill=(240, 110, 96), width=round(3.5 * S))


# ── bottom panels ─────────────────────────────────────────────────────

def _panel(img, box, title, acc):
    T.panel(img, box, None, fill=mix(acc.panel, (0, 0, 0), 0.2), glow=True, accent=acc)
    _heading(img, box, title)


def _herbs_panel(img, data, acc):
    box = PANELS[0]
    _panel(img, box, "In the cauldron", acc)
    x0, y0, x1, y1 = box
    rows = data["herbs"][:4]
    rh = min(46, (y1 - y0 - 66) / max(1, len(rows)))
    af = font("Inter.ttf", 24, "SemiBold")
    for i, h in enumerate(rows):
        y = y0 + 66 + rh * i + rh / 2
        live = h["state"] == "in"
        col = HERB_COLOR.get(h["type"], T.GOLD)
        T.medallion(img, (x0 + 40, y), 19, HERB_CHAR.get(h["type"], "草"), col if h["state"] != "lost" else T.ASH_DK)
        d = ImageDraw.Draw(img)
        age = f"{h['age']}-yr" if h.get("age") else ""
        aw = T.width(d, age, af)
        name, f = _shrink(d, h["name"], "Inter.ttf", "Bold", (26, 24), x1 - x0 - 104 - aw)
        T.text(d, (x0 + 68, y), name, f, WHITE if live else (T.ASH if h["state"] != "lost" else (226, 96, 84)), "lm")
        if age:
            T.text(d, (x1 - 20, y), age, af, AGE_COLOR.get(h["age"], T.ASH), "rm")
        if live:                                          # a green tick badge on the seal
            d.ellipse(P(x0 + 46, y + 2, x0 + 64, y + 20), fill=(16, 40, 24, 255), outline=GREEN, width=round(1.5 * S))
            _check(d, x0 + 55, y + 11, 10, GREEN)
        if h.get("qty", 1) > 1:                           # how many of this herb, as a badge on the seal
            d.ellipse(P(x0 + 42, y - 30, x0 + 68, y - 4), fill=(30, 20, 12, 255), outline=T.GOLD, width=round(1.5 * S))
            T.text(d, (x0 + 55, y - 17), str(h["qty"]), font("Inter.ttf", 20, "Bold"), T.GOLD_HI, "mm", shadow=False)


def _row(d, box, y, label, value, vcol=WHITE):
    x0, _, x1, _ = box
    T.text(d, (x0 + 24, y), label, font("Inter.ttf", 24, "Medium"), T.PARCHMENT, "lm")
    T.text(d, (x1 - 24, y), value, font("Inter.ttf", 26, "Bold"), vcol, "rm")


def _refining_panel(img, data, acc, box=None):
    box = box or PANELS[1]
    _panel(img, box, "Refining", acc)
    r = data["refining"]
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    score = r["score"]
    _row(d, box, y0 + 70, "Score so far" if not data.get("done") else "Final score",
         f"{score:.0%}" if score is not None else "—", T.GOLD_HI)
    _row(d, box, y0 + 104, "Herb age bonus", f"+{r['bonus']:.0%}" if r["bonus"] else "none")
    _row(d, box, y0 + 138, "Mistakes forgiven", f"{r['forgive']} left" if r["forgive"] else "none")
    _row(d, box, y0 + 172, "Explodes below", f"{r['explode']:.0%}", (240, 130, 110))
    bx0, bx1 = x0 + 24, x1 - 24
    frac = score or 0
    T.bar(img, (bx0, y1 - 36, bx1, y1 - 16), frac, (226, 72, 56) if score is not None and score < r["explode"]
          else acc.hp)
    d = ImageDraw.Draw(img)
    ex = bx0 + (bx1 - bx0) * r["explode"]
    d.line(P(ex, y1 - 42, ex, y1 - 10), fill=(240, 110, 96), width=round(2.5 * S))


def _patterns_panel(img, data, acc):
    box = PANELS[2]
    _panel(img, box, "Pill patterns", acc)
    x0, y0, x1, y1 = box
    p = data["patterns"]
    earned, cap = p["earned"], p["cap"]
    center = (x0 + 104, y0 + 136)
    _rings(img, center, 10, 7.4, earned, cap, color=T.GOLD_HI if acc.name == "alchemy" else (236, 226, 255))
    T.soft_glow(img, (center[0] - 16, center[1] - 16, center[0] + 16, center[1] + 16),
                alpha(T.RARITY.get(data["pill"]["grade"], T.GOLD), 200), 5)
    d = ImageDraw.Draw(img)
    d.ellipse(P(center[0] - 9, center[1] - 9, center[0] + 9, center[1] + 9),
              fill=mix(T.RARITY.get(data["pill"]["grade"], T.GOLD), (255, 255, 255), 0.3) + (255,))
    tx = x0 + 206
    if earned:
        T.text(d, (tx, y0 + 94), CN[earned] + "纹", cjk(44), T.GOLD_HI, "lm")
        T.text(d, (tx, y0 + 138), f"{earned} pattern{'s' if earned > 1 else ''}", font("Inter.ttf", 26, "Bold"), WHITE,
               "lm")
        T.text(d, (tx, y0 + 172), f"×{p['effect']:.2f} effect", font("Inter.ttf", 24, "Medium"), T.PARCHMENT, "lm")
    else:
        T.text(d, (tx, y0 + 94), "未成", cjk(44), T.ASH, "lm")
        T.text(d, (tx, y0 + 138), "None yet", font("Inter.ttf", 26, "Bold"), T.ASH, "lm")
    T.text(d, (tx, y0 + 206), f"Age cap {cap}", font("Inter.ttf", 24, "Medium"), T.ASH, "lm")


def _tribulation_panel(img, data, acc):
    box = (PANELS[0][0], PANELS[0][1], PANELS[1][2], PANELS[1][3])
    _panel(img, box, "The tribulation", acc)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    f, sf = font("Inter.ttf", 26, "SemiBold"), font("Inter.ttf", 24, "Medium")
    t = data["tribulation"]
    lines = T.wrap(d, f"Survive all {data['strikes']} strikes: a nine-pattern pill, ×{t['effect9']:.2f} effect, "
                      f"no toxicity, and the whole server hears of it.", f, x1 - x0 - 48, 2)
    for i, line in enumerate(lines):
        T.text(d, (x0 + 24, y0 + 76 + i * 36), line, f, WHITE, "lm")
    T.text(d, (x0 + 24, y0 + 158), f"Fail: the pill still forms, with {t['fail']} patterns.", sf, T.ASH, "lm")
    # one shield pip per strike: blocked, missed, still to come
    for k in range(data["strikes"]):
        cx, cy = x0 + 40 + k * 56, y0 + 200
        state = t["marks"][k]
        col = {"blocked": GREEN, "hit": (226, 72, 56)}.get(state, T.ASH_DK)
        T.icon(img, "shield", (cx, cy), 30, col)
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 40 + data["strikes"] * 56, y0 + 200), f"{data['blocked']} of {data['strikes']} blocked", sf,
           T.PARCHMENT, "lm")


# ── the card ──────────────────────────────────────────────────────────

def render_alchemy(data):
    accent = data.get("accent", "alchemy")
    acc = T.ACCENTS[accent]
    img = _chamber(accent).copy()
    mode = data["mode"]
    seed = data.get("seed", 1)
    MIDDLE[mode](img, data, acc, seed)
    # darken the top so the title and round read clearly over the fire light
    shade = Image.new("RGBA", P(SCENE[2] - SCENE[0], 150), (0, 0, 0, 0))
    shade.putalpha(Image.linear_gradient("L").rotate(180).resize(shade.size).point(lambda v: v * 0.5))
    img.alpha_composite(shade, P(SCENE[0], SCENE[1]))
    T.frame(img, SCENE, 0.8)
    _title(img, data, acc)
    _corner(img, data, acc)
    LEFT[mode](img, data, acc)
    _stage_path(img, data, acc)
    if mode == "tribulation":
        _tribulation_panel(img, data, acc)
    else:
        _herbs_panel(img, data, acc)
        _refining_panel(img, data, acc)
    _patterns_panel(img, data, acc)
    _warning(img, {"warning": data["warning"], "warning_icon": data.get("warning_icon", "flame")}, _warn_accent(data),
             WARN)
    T.frame(img, (6, 6, W - 6, H - 6), 1.0)
    return T.finish(img)


def _warn_accent(data):
    if data["mode"] == "exploded":
        return T.ELEMENT_ACCENTS["Blood"]
    return T.ACCENTS[data.get("accent", "alchemy")]
