"""
Small drawn plant pictures for the /gather choice cards (cards/herbfield.py), one per herb and decoy.

Each plant is drawn from its kind (moss, root, mushroom, flower, lily, lotus, berry, fruit, grass, leaf, dew,
vine) and its key detail (glow, a north or south stone, warm or cold, near bones, no shadow ...), so a decoy
differs from its herb in exactly the detail its look text names. Pillow only; each picture is cached.

plant(name) -> RGBA image, PW×PH card pixels drawn at S×.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from .theme import P, S, alpha, font, mix

PW, PH = 240, 170
GROUND = 142
CX = PW / 2

GREEN, DKGREEN = (88, 176, 92), (40, 96, 52)
WHITE = (255, 250, 236)

# name → (kind, options). Every herb and decoy in alchemy.HERBS / alchemy.DECOYS has an entry.
PLANTS = {
    # Mortal
    "Spirit Grass":    ("grass", {"sway": True}),
    "Ghost Grass":     ("grass", {"sway": True, "tips": (170, 170, 170)}),
    "Red Berry":       ("berry", {"scent": True}),
    "Bitter Nettle":   ("berry", {"spiky": True}),
    "Dew Leaf":        ("leaf", {"dew": True}),
    "Iron Root":       ("root", {"color": (70, 74, 82), "sheen": True}),
    # Yellow
    "Sun Ginseng":     ("root", {"color": (226, 176, 70), "warm": True}),
    "Fool's Ginseng":  ("root", {"color": (226, 176, 70), "cold": True}),
    "Blood Flower":    ("flower", {"color": (176, 24, 36), "veins": True}),
    "Silver Moss":     ("moss", {"face": "N"}),
    "Snake Moss":      ("moss", {"face": "S"}),
    "Stone Root":      ("root", {"color": (130, 130, 124), "rock": True}),
    # Mystic
    "Moon Mushroom":   ("mushroom", {"sky": "moon"}),
    "Shadow Mushroom": ("mushroom", {"sky": "sun"}),
    "Heart Lotus":     ("lotus", {"color": (240, 140, 180), "heart": True}),
    "Jade Lily":       ("lily", {"color": (200, 236, 210), "sheen": True}),
    "Weeping Lily":    ("lily", {"color": (200, 236, 210), "sap": True}),
    "Thunder Root":    ("root", {"color": (36, 34, 40), "bolt": True}),
    # Earth
    "Golden Ginseng":  ("root", {"color": (236, 190, 80), "person": True, "glow": True}),
    "Grave Ginseng":   ("root", {"color": (236, 190, 80), "person": True, "glow": True, "bones": True}),
    "Phoenix Flower":  ("flower", {"color": (246, 130, 40), "sparks": True}),
    "Fire Thorn":      ("flower", {"color": (246, 130, 40), "thorns": True}),
    "Snow Lily":       ("lily", {"color": (250, 250, 255), "snow": True}),
    "Mountain Root":   ("root", {"color": (130, 96, 60), "cliff": True, "massive": True}),
    # Heaven
    "Heaven Lotus":    ("lotus", {"color": (250, 220, 150), "nine": True, "float": True}),
    "Demon Lotus":     ("lotus", {"color": (250, 220, 150), "nine": True, "red_under": True}),
    "Immortal Peach":  ("fruit", {"color": (250, 170, 150), "glow": True, "shadow": True}),
    "Void Fruit":      ("fruit", {"color": (250, 170, 150), "glow": True}),
    "Star Dew":        ("dew", {"stars": True}),
    "Chaos Root":      ("root", {"rainbow": True}),
}
KINDS = ("moss", "root", "mushroom", "flower", "lily", "lotus", "berry", "fruit", "grass", "leaf", "dew", "vine")


# ── helpers ───────────────────────────────────────────────────────────

def _glow(img, cx, cy, rx, ry, color, a=170, blur=10):
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse(P(cx - rx, cy - ry, cx + rx, cy + ry), fill=alpha(color, a))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(blur * S)))


def _ground(d, color=(30, 46, 36)):
    d.ellipse(P(CX - 96, GROUND - 10, CX + 96, GROUND + 14), fill=alpha(color, 255))


def _leaf(d, x, y, ang, ln, wd, color):
    """A pointed leaf from (x, y) at `ang` degrees (0 = up)."""
    a = math.radians(ang)
    ux, uy = math.sin(a), -math.cos(a)
    nx, ny = -uy, ux
    tip = (x + ux * ln, y + uy * ln)
    mid = (x + ux * ln * 0.45, y + uy * ln * 0.45)
    d.polygon([P(x, y), P(mid[0] + nx * wd, mid[1] + ny * wd), P(*tip), P(mid[0] - nx * wd, mid[1] - ny * wd)],
              fill=alpha(color, 255))


def _sky_badge(img, kind):
    """A small moon or sun in the top right corner."""
    d = ImageDraw.Draw(img)
    x, y = PW - 34, 30
    if kind == "moon":
        _glow(img, x, y, 22, 22, (200, 220, 255), 120, 6)
        d = ImageDraw.Draw(img)
        d.ellipse(P(x - 15, y - 15, x + 15, y + 15), fill=(236, 240, 255, 255))
        d.ellipse(P(x - 8, y - 18, x + 20, y + 10), fill=(14, 26, 30, 255))
    else:
        _glow(img, x, y, 26, 26, (255, 210, 90), 150, 6)
        d = ImageDraw.Draw(img)
        for i in range(8):
            a = math.radians(i * 45)
            d.line(P(x + math.cos(a) * 15, y + math.sin(a) * 15, x + math.cos(a) * 22, y + math.sin(a) * 22),
                   fill=(255, 214, 100, 255), width=round(2.4 * S))
        d.ellipse(P(x - 11, y - 11, x + 11, y + 11), fill=(255, 226, 120, 255))


def _letter_badge(img, letter):
    """The compass letter of the way a stone faces (N or S), in a ring."""
    d = ImageDraw.Draw(img)
    x, y = PW - 30, 28
    d.ellipse(P(x - 19, y - 19, x + 19, y + 19), fill=(10, 18, 16, 255), outline=(236, 232, 214, 255), width=round(2 * S))
    T.text(d, (x, y + 1), letter, font("Cinzel.ttf", 24, "Black"), WHITE, "mm", shadow=False)


# ── the kinds ─────────────────────────────────────────────────────────

def _grass(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    r = random.Random(3)
    tip = o.get("tips")
    for i in range(11):
        x = CX - 50 + i * 10 + r.uniform(-3, 3)
        h = r.uniform(70, 110)
        bend = 26 if o.get("sway") else 4
        pts = [(x, GROUND - 2), (x + bend * 0.3, GROUND - h * 0.5), (x + bend, GROUND - h)]
        d.line([P(*p) for p in pts], fill=alpha(GREEN, 255), width=round(4 * S), joint="curve")
        if tip:                   # the top fifth of each blade is grey
            tx, ty = pts[2]
            d.line(P(x + bend * 0.7, GROUND - h * 0.8, tx, ty), fill=alpha(tip, 255), width=round(4.5 * S))
    if o.get("sway"):
        for k in range(3):
            y = GROUND - 100 + k * 18
            d.arc(P(CX + 50, y - 10, CX + 96, y + 10), 200, 340, fill=(200, 236, 210, 200), width=round(2 * S))


def _berry(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    d.line(P(CX, GROUND, CX, GROUND - 70), fill=alpha(DKGREEN, 255), width=round(4 * S))
    spiky = o.get("spiky")
    berries = [(CX - 18, GROUND - 52), (CX - 4, GROUND - 60), (CX + 12, GROUND - 50), (CX - 8, GROUND - 44),
               (CX + 4, GROUND - 40)]
    if spiky:                 # berries hidden under spiky leaves: draw berries first, leaves over them
        for bx, by in berries:
            d.ellipse(P(bx - 8, by - 8 + 18, bx + 8, by + 8 + 18), fill=(206, 34, 40, 255))
        for ang in (-70, -35, 0, 35, 70):
            a = math.radians(ang)
            x0, y0 = CX, GROUND - 74
            pts = []
            for k in range(9):
                t = k / 8
                rr = 64 * t
                off = (8 if k % 2 else -2)
                pts.append((x0 + math.sin(a) * rr + math.cos(a) * off, y0 + 10 - math.cos(a) * rr * 0.55 + math.sin(a) * off))
            d.polygon([P(*p) for p in pts + [(x0, y0 + 14)]], fill=(52, 120, 56, 255))
        for ang in (-70, -35, 0, 35, 70):
            a = math.radians(ang)
            ex, ey = CX + math.sin(a) * 70, GROUND - 64 - math.cos(a) * 36
            for k in range(3):
                d.line(P(ex - 6 + k * 6, ey, ex - 10 + k * 6, ey - 12), fill=(200, 230, 170, 255), width=round(2 * S))
    else:
        for ang in (-60, 60, -20, 20):
            _leaf(d, CX, GROUND - 66, ang, 52, 14, GREEN)
        for bx, by in berries:
            d.ellipse(P(bx - 9, by - 9, bx + 9, by + 9), fill=(214, 36, 44, 255))
            d.ellipse(P(bx - 4, by - 6, bx, by - 2), fill=(255, 180, 180, 255))
    if o.get("scent"):
        for k in range(3):
            x = CX + 30 + k * 16
            d.arc(P(x, GROUND - 120 + k * 4, x + 16, GROUND - 96 + k * 4), 90, 270, fill=(250, 200, 220, 220),
                  width=round(2 * S))
            d.arc(P(x, GROUND - 144 + k * 4, x + 16, GROUND - 120 + k * 4), 270, 90, fill=(250, 200, 220, 220),
                  width=round(2 * S))


def _leaf_plant(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    d.line(P(CX, GROUND, CX + 4, GROUND - 40), fill=alpha(DKGREEN, 255), width=round(4 * S))
    d.ellipse(P(CX - 76, GROUND - 92, CX + 76, GROUND - 34), fill=(76, 170, 90, 255))
    d.ellipse(P(CX - 64, GROUND - 86, CX + 64, GROUND - 46), fill=(60, 140, 76, 255))
    d.line(P(CX - 70, GROUND - 63, CX + 70, GROUND - 63), fill=(110, 200, 120, 255), width=round(2 * S))
    if o.get("dew"):
        _glow(img, CX + 6, GROUND - 76, 18, 18, (200, 240, 255), 160, 4)
        d = ImageDraw.Draw(img)
        d.ellipse(P(CX - 8, GROUND - 90, CX + 20, GROUND - 62), fill=(170, 220, 250, 255), outline=(240, 250, 255, 255),
                  width=max(1, S))
        d.ellipse(P(CX - 2, GROUND - 86, CX + 5, GROUND - 79), fill=(255, 255, 255, 255))


def _root(img, o):
    rainbow = o.get("rainbow")
    color = o.get("color", (180, 150, 100))
    if o.get("warm"):
        _glow(img, CX, GROUND - 50, 60, 60, (255, 150, 40), 200, 12)
    if o.get("cold"):
        _glow(img, CX, GROUND - 50, 60, 60, (120, 190, 255), 200, 12)
    if o.get("glow"):
        _glow(img, CX, GROUND - 60, 64, 64, (255, 210, 90), 190, 12)
    d = ImageDraw.Draw(img)
    if o.get("cliff"):
        d.polygon([P(0, 0), P(PW * 0.9, 0), P(PW * 0.75, 50), P(PW * 0.55, 62), P(0, 70)], fill=(80, 76, 70, 255))
        d.line(P(0, 70, PW * 0.55, 62), fill=(120, 116, 108, 255), width=round(2 * S))
    if o.get("rock"):
        d.polygon([P(CX - 90, GROUND + 6), P(CX - 70, GROUND - 70), P(CX - 10, GROUND - 92), P(CX + 60, GROUND - 76),
                   P(CX + 92, GROUND + 6)], fill=(96, 96, 104, 255))
    elif o.get("bolt"):
        d.polygon([P(CX - 92, GROUND + 4), P(CX - 30, GROUND - 14), P(CX + 30, GROUND - 10), P(CX + 92, GROUND + 4)],
                  fill=(26, 20, 18, 255))
        for k in range(5):
            a = math.radians(200 + k * 35)
            d.line(P(CX, GROUND - 4, CX + math.cos(a) * 80, GROUND - 4 + math.sin(a) * -8), fill=(80, 50, 30, 255),
                   width=round(2 * S))
    else:
        _ground(d, (46, 36, 28))
    top = GROUND - (110 if o.get("massive") else 92)
    if o.get("person"):
        body = color
        d.ellipse(P(CX - 14, top + 4, CX + 14, top + 30), fill=alpha(body, 255))            # head
        d.polygon([P(CX - 22, top + 30), P(CX + 22, top + 30), P(CX + 30, top + 80), P(CX - 30, top + 80)],
                  fill=alpha(body, 255))                                                   # body
        d.polygon([P(CX - 30, top + 80), P(CX + 30, top + 80), P(CX + 44, top + 96), P(CX - 44, top + 96)],
                  fill=alpha(mix(body, (0, 0, 0), 0.15), 255))                              # folded legs
        for sx in (-1, 1):
            d.line(P(CX + sx * 22, top + 40, CX + sx * 38, top + 64), fill=alpha(body, 255), width=round(6 * S))
            d.line(P(CX + sx * 36, top + 96, CX + sx * 60, top + 110), fill=alpha(mix(body, (0, 0, 0), 0.3), 255),
                   width=round(2 * S))
        for ang in (-25, 0, 25):
            _leaf(d, CX, top + 6, ang, 26, 7, GREEN)
    else:
        wd = 34 if o.get("massive") else 22
        pts = [(CX - wd, top + 10), (CX + wd, top + 10), (CX + wd * 0.5, top + 60), (CX + 6, GROUND + 10),
               (CX - 6, GROUND + 10), (CX - wd * 0.6, top + 60)]
        if rainbow:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).polygon([P(*p) for p in pts], fill=(255, 255, 255, 255))
            bands = Image.new("RGBA", img.size, (0, 0, 0, 0))
            bd = ImageDraw.Draw(bands)
            cols = [(236, 70, 70), (246, 170, 60), (240, 230, 90), (90, 210, 120), (90, 160, 240), (170, 110, 240)]
            for i, c in enumerate(cols):
                bd.rectangle(P(CX - 40 + i * 14, top, CX - 26 + i * 14, GROUND + 12), fill=alpha(c, 255))
            bands = bands.filter(ImageFilter.GaussianBlur(4 * S))
            img.paste(bands, (0, 0), layer.getchannel("A"))
            _glow(img, CX, GROUND - 50, 50, 60, (220, 180, 255), 90, 10)
            d = ImageDraw.Draw(img)
        else:
            d.polygon([P(*p) for p in pts], fill=alpha(color, 255))
        tail = mix(color, (0, 0, 0), 0.3) if not rainbow else (180, 140, 220)
        for sx, ln in ((-1, 34), (1, 30), (-1, 20)):
            d.line(P(CX, top + 64, CX + sx * ln, top + 64 + ln * 0.8), fill=alpha(tail, 255), width=round(3 * S))
        for ang in (-30, 0, 30):
            _leaf(d, CX, top + 10, ang, 38, 9, GREEN)
        if o.get("sheen"):
            d.line(P(CX - 8, top + 18, CX - 2, top + 56), fill=(200, 210, 230, 255), width=round(3 * S))
    if o.get("cold"):
        for k, (x, y) in enumerate(((CX - 46, GROUND - 90), (CX + 44, GROUND - 70), (CX + 30, GROUND - 112))):
            for a in (0, 60, 120):
                ra = math.radians(a)
                d.line(P(x - math.cos(ra) * 9, y - math.sin(ra) * 9, x + math.cos(ra) * 9, y + math.sin(ra) * 9),
                       fill=(220, 240, 255, 255), width=round(2 * S))
    if o.get("warm"):
        for k in range(3):
            x = CX - 40 + k * 40
            d.arc(P(x - 8, GROUND - 130, x + 8, GROUND - 110), 90, 270, fill=(255, 170, 80, 220), width=round(2 * S))
            d.arc(P(x - 8, GROUND - 150, x + 8, GROUND - 130), 270, 90, fill=(255, 170, 80, 220), width=round(2 * S))
    if o.get("bolt"):
        d.polygon([P(PW - 54, 6), P(PW - 74, 46), P(PW - 60, 46), P(PW - 78, 86), P(PW - 44, 36), P(PW - 58, 36),
                   P(PW - 40, 6)], fill=(255, 236, 120, 255))
    if o.get("bones"):
        bone = (232, 222, 200, 255)
        for x, y, a in ((CX - 70, GROUND - 4, 0.3), (CX + 62, GROUND - 2, -0.4), (CX + 76, GROUND - 14, 0.9)):
            dx, dy = math.cos(a) * 16, math.sin(a) * 16
            d.line(P(x - dx, y - dy, x + dx, y + dy), fill=bone, width=round(4 * S))
            for ex, ey in ((x - dx, y - dy), (x + dx, y + dy)):
                d.ellipse(P(ex - 4, ey - 4, ex + 4, ey + 4), fill=bone)
        d.ellipse(P(CX - 96, GROUND - 26, CX - 70, GROUND - 2), fill=bone)
        d.ellipse(P(CX - 90, GROUND - 18, CX - 84, GROUND - 12), fill=(30, 20, 16, 255))
        d.ellipse(P(CX - 82, GROUND - 18, CX - 76, GROUND - 12), fill=(30, 20, 16, 255))


def _moss(img, o):
    d = ImageDraw.Draw(img)
    d.ellipse(P(CX - 84, GROUND - 60, CX + 84, GROUND + 10), fill=(96, 98, 104, 255))
    d.ellipse(P(CX - 70, GROUND - 56, CX + 40, GROUND - 26), fill=(118, 120, 126, 255))
    _glow(img, CX, GROUND - 58, 76, 20, (150, 255, 210), 200, 8)
    d = ImageDraw.Draw(img)
    for i in range(9):
        x = CX - 60 + i * 15
        d.ellipse(P(x - 10, GROUND - 70, x + 10, GROUND - 52), fill=(170, 250, 210, 255))
    _letter_badge(img, o["face"])


def _mushroom(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    _glow(img, CX, GROUND - 76, 70, 34, (140, 200, 255), 130, 10)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(P(CX - 11, GROUND - 70, CX + 11, GROUND + 2), radius=round(8 * S), fill=(230, 236, 240, 255))
    d.chord(P(CX - 72, GROUND - 112, CX + 72, GROUND - 40), 180, 360, fill=(150, 196, 240, 255))       # open, flat cap
    d.line(P(CX - 72, GROUND - 76, CX + 72, GROUND - 76), fill=(96, 140, 196, 255), width=round(3 * S))
    for x, y in ((CX - 30, GROUND - 96), (CX + 16, GROUND - 102), (CX + 40, GROUND - 88)):
        d.ellipse(P(x - 6, y - 5, x + 6, y + 5), fill=(220, 240, 255, 255))
    _sky_badge(img, o["sky"])


def _flower(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    d.line(P(CX, GROUND, CX, GROUND - 60), fill=alpha(DKGREEN, 255), width=round(4 * S))
    _leaf(d, CX, GROUND - 26, -60, 40, 10, GREEN)
    _leaf(d, CX, GROUND - 34, 60, 40, 10, GREEN)
    color = o["color"]
    cy = GROUND - 92
    if o.get("sparks"):
        _glow(img, CX, cy, 60, 50, (255, 120, 40), 170, 10)
        d = ImageDraw.Draw(img)
    for i in range(6):
        a = i * 60
        _leaf(d, CX, cy, a, 40, 16, color)
    for i in range(6):
        _leaf(d, CX, cy, i * 60 + 30, 26, 10, mix(color, (255, 255, 255), 0.2))
    if o.get("veins"):
        for i in range(6):
            a = math.radians(i * 60)
            d.line(P(CX, cy, CX + math.sin(a) * 34, cy - math.cos(a) * 34), fill=(60, 6, 12, 255), width=round(2.4 * S))
    d.ellipse(P(CX - 9, cy - 9, CX + 9, cy + 9), fill=(250, 210, 90, 255))
    if o.get("sparks"):
        r = random.Random(5)
        for _ in range(12):
            x, y = CX + r.uniform(-80, 80), cy + r.uniform(-60, 10)
            d.ellipse(P(x - 3, y - 3, x + 3, y + 3), fill=(255, 210, 110, 255))
    if o.get("thorns"):
        d.ellipse(P(CX - 80, GROUND - 40, CX + 80, GROUND + 6), fill=(70, 30, 20, 255))
        for i in range(14):
            x = CX - 72 + i * 11
            d.polygon([P(x - 5, GROUND - 14), P(x + 2, GROUND - 46 - (i % 3) * 6), P(x + 6, GROUND - 14)],
                      fill=(236, 110, 40, 255))


def _lily(img, o):
    d = ImageDraw.Draw(img)
    if o.get("snow"):
        d.ellipse(P(CX - 104, GROUND - 16, CX + 104, GROUND + 18), fill=(236, 244, 255, 255))
        r = random.Random(2)
        for _ in range(26):
            x, y = r.uniform(8, PW - 8), r.uniform(8, GROUND - 20)
            d.ellipse(P(x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=(255, 255, 255, 230))
    else:
        _ground(d)
    color = o["color"]
    if o.get("sheen"):
        _glow(img, CX, GROUND - 90, 50, 50, (120, 230, 180), 160, 10)
        d = ImageDraw.Draw(img)
    d.line(P(CX, GROUND, CX, GROUND - 70), fill=alpha(DKGREEN, 255), width=round(4 * S))
    _leaf(d, CX, GROUND - 4, -30, 60, 9, GREEN)
    _leaf(d, CX, GROUND - 4, 34, 56, 9, GREEN)
    cy = GROUND - 76
    for ang in (-60, -25, 25, 60, 0):
        _leaf(d, CX, cy, ang, 54, 13, color)
    for ang in (-20, 0, 20):
        _leaf(d, CX, cy, ang, 30, 3, (250, 220, 120))
    if o.get("sap"):
        for x, ln in ((CX - 40, 34), (CX + 36, 40), (CX - 10, 22)):
            d.line(P(x, cy - 20, x, cy - 20 + ln), fill=(40, 20, 30, 255), width=round(4 * S))
            d.ellipse(P(x - 5, cy - 22 + ln, x + 5, cy - 10 + ln), fill=(40, 20, 30, 255))


def _lotus(img, o):
    d = ImageDraw.Draw(img)
    float_ = o.get("float")
    # water
    d.ellipse(P(CX - 108, GROUND - 22, CX + 108, GROUND + 16), fill=(40, 80, 96, 255))
    for k in range(3):
        d.line(P(CX - 80 + k * 30, GROUND - 4 + k * 4, CX - 40 + k * 30, GROUND - 4 + k * 4), fill=(140, 200, 220, 200),
               width=round(2 * S))
    color = o["color"]
    cy = GROUND - (62 if float_ else 30)
    if float_:
        _glow(img, CX, cy, 70, 40, (255, 240, 180), 140, 10)
        d = ImageDraw.Draw(img)
        d.ellipse(P(CX - 50, GROUND - 14, CX + 50, GROUND + 2), fill=(20, 40, 50, 255))   # its shadow on the water
    nine = o.get("nine")
    n = 9 if nine else 7
    under = (190, 20, 30) if o.get("red_under") else mix(color, (60, 120, 60), 0.5)
    if nine:
        for i in range(n):          # the nine leaves, a ring under the flower
            a = math.radians(-180 + i * (180 / (n - 1)))
            x, y = CX + math.cos(a) * 76, cy + 10 + math.sin(a) * 6
            d.ellipse(P(x - 15, y - 7, x + 15, y + 7), fill=alpha(under if o.get("red_under") else (70, 150, 80), 255))
            d.ellipse(P(x - 15, y - 10, x + 15, y + 2), fill=(80, 170, 90, 255))
        if o.get("red_under"):
            d.ellipse(P(CX - 60, cy + 2, CX + 60, cy + 24), fill=(190, 20, 30, 255))
    else:
        d.ellipse(P(CX - 80, cy - 2, CX + 80, cy + 20), fill=(70, 150, 80, 255))
    for ang in (-75, 75, -50, 50):
        _leaf(d, CX, cy + 8, ang, 46, 14, mix(color, (0, 0, 0), 0.15))
    for ang in (-25, 25, 0):
        _leaf(d, CX, cy + 8, ang, 56, 15, color)
    if o.get("heart"):
        hx, hy = CX, cy - 22
        d.ellipse(P(hx - 12, hy - 10, hx, hy + 2), fill=(200, 40, 80, 255))
        d.ellipse(P(hx, hy - 10, hx + 12, hy + 2), fill=(200, 40, 80, 255))
        d.polygon([P(hx - 12, hy - 3), P(hx + 12, hy - 3), P(hx, hy + 13)], fill=(200, 40, 80, 255))
    else:
        d.ellipse(P(CX - 9, cy - 28, CX + 9, cy - 12), fill=(250, 214, 100, 255))


def _fruit(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    color = o["color"]
    cy = GROUND - 74
    if o.get("shadow"):
        d.ellipse(P(CX - 40, GROUND - 6, CX + 50, GROUND + 6), fill=(8, 14, 12, 255))
    d.line(P(CX - 90, 30, CX + 4, cy - 34), fill=(70, 46, 30, 255), width=round(5 * S))
    if o.get("glow"):
        _glow(img, CX, cy, 58, 58, (255, 220, 160), 200, 10)
        d = ImageDraw.Draw(img)
    d.ellipse(P(CX - 34, cy - 34, CX + 34, cy + 34), fill=alpha(color, 255))
    d.arc(P(CX - 34, cy - 34, CX + 34, cy + 34), 250, 290, fill=alpha(mix(color, (120, 30, 30), 0.5), 255),
          width=round(3 * S))
    d.ellipse(P(CX - 20, cy - 22, CX - 6, cy - 8), fill=(255, 240, 230, 255))
    _leaf(d, CX + 2, cy - 32, 40, 30, 9, GREEN)
    if o.get("shadow"):
        for x, y in ((CX - 70, 46), (CX - 46, 34)):
            for k in range(5):
                a = math.radians(k * 72)
                d.ellipse(P(x + math.cos(a) * 6 - 5, y + math.sin(a) * 6 - 5, x + math.cos(a) * 6 + 5, y + math.sin(a) * 6 + 5),
                          fill=(250, 190, 210, 255))


def _dew(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    _sky_badge(img, "sun")
    d = ImageDraw.Draw(img)
    for ang in (-50, -15, 20, 55):
        _leaf(d, CX, GROUND - 4, ang, 84, 11, GREEN)
    for x, y in ((CX - 46, GROUND - 60), (CX - 10, GROUND - 82), (CX + 30, GROUND - 70), (CX + 56, GROUND - 46)):
        _glow(img, x, y, 16, 16, (255, 255, 230), 200, 4)
        d = ImageDraw.Draw(img)
        pts = []
        for i in range(8):
            rr = 11 if i % 2 == 0 else 4
            a = math.radians(-90 + i * 45)
            pts.append(P(x + math.cos(a) * rr, y + math.sin(a) * rr))
        d.polygon(pts, fill=(255, 252, 220, 255))


def _vine(img, o):
    d = ImageDraw.Draw(img)
    _ground(d)
    pts = [(CX - 80 + i * 8, GROUND - 20 - 50 * abs(math.sin(i / 3))) for i in range(21)]
    d.line([P(*p) for p in pts], fill=alpha(DKGREEN, 255), width=round(4 * S), joint="curve")
    for i, (x, y) in enumerate(pts[::3]):
        _leaf(d, x, y, -40 if i % 2 else 40, 22, 7, GREEN)


DRAW = {"grass": _grass, "berry": _berry, "leaf": _leaf_plant, "root": _root, "moss": _moss, "mushroom": _mushroom,
        "flower": _flower, "lily": _lily, "lotus": _lotus, "fruit": _fruit, "dew": _dew, "vine": _vine}


# Herb/look-alike pairs whose paintings don't differ in just the detail the look text names (the snake
# for Snake Moss, a red Shadow Mushroom, a phoenix bird for Phoenix Flower, a red backdrop behind Ghost
# Grass and Grave Ginseng …). /gather keeps the drawn plants for both of each pair until they are
# repainted, so a painting never gives the answer away. /index and the bag still show every painting.
KEEP_DRAWN = {"Spirit Grass", "Ghost Grass", "Golden Ginseng", "Grave Ginseng", "Silver Moss", "Snake Moss", "Moon Mushroom", "Shadow Mushroom", "Jade Lily", "Weeping Lily",
              "Phoenix Flower", "Fire Thorn", "Heaven Lotus", "Demon Lotus", "Immortal Peach", "Void Fruit"}


@lru_cache(maxsize=64)
def plant(name):
    """The plant's picture: transparent, PW×PH card pixels at S×. Its painting (art/icons/herbs) when it
    has one, else the drawn plant."""
    from . import art_icons
    img = Image.new("RGBA", P(PW, PH), (0, 0, 0, 0))
    hit = None if name in KEEP_DRAWN else art_icons.resolve(art_icons.herb(name, ""))
    if hit:
        side = round(PH * S)
        img.alpha_composite(art_icons.image(hit[0], side), ((img.size[0] - side) // 2, 0))
        return img
    kind, opts = PLANTS[name]
    DRAW[kind](img, opts)
    return img
