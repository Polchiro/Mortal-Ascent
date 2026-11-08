"""
The trade cards (docs/trading.md), in the jade-and-gold frame style: dark slate, a gold double frame with
cloud-curl corners, a jade staff with a golden lotus between the two offers, no boxes.

  render_trade(data)    the public window: both players, their items and currencies, 成交 / 商议 seals,
                        and the state (adding · one confirmed · complete · cancelled)
  render_preview(data)  the Trade Preview before confirming: You give · You receive
  render_picker(data)   the private Add Item / Add Currency screens: categories, grade + items, quantity,
                        currencies

data comes from bot/trading (card_data, picker data) + "avatars": {uid: png bytes}.
The trade card grows taller with the longest offer, so every line is shown.
"""
import io
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import ink as K
from . import theme as T
from . import victory as V
from .theme import P, S, alpha, cjk, font, mix

W = 1200
H = 760
ROW = 64
TOP = 250
COL = [(72, 560), (640, 1128)]
WHITE = (250, 244, 232)
SOFT = (206, 198, 186)
DIM = (140, 134, 126)
GOLD = (236, 200, 120)
GOLD_DK = (150, 112, 52)
JADE = (110, 214, 160)
JADE_DK = (40, 110, 84)
RED = (232, 96, 80)
LOTUS = (240, 196, 110)
PEARL = (196, 214, 246)


def height(data):
    n = max([len(s["rows"]) for s in data["sides"]] + [5])
    return TOP + n * ROW + 290


# ── the frame ─────────────────────────────────────────────────────────

@lru_cache(maxsize=8)
def _slate(w, h, dragons="all", size=150):
    """Dark slate with faint grain, a jade breath in the middle and darker edges."""
    rng = random.Random(5)
    img = Image.new("RGBA", (w * S, h * S), (20, 22, 24, 255))
    grain = Image.effect_noise((w * S // 3 + 1, h * S // 3 + 1), 30).resize((w * S, h * S), Image.BILINEAR)
    img = Image.blend(img, Image.merge("RGBA", (grain, grain, grain, Image.new("L", grain.size, 255))), 0.05)
    T.soft_glow(img, (w * 0.25, h * 0.2, w * 0.75, h * 0.8), (40, 90, 70, 60), 120)
    veins = Image.new("RGBA", img.size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(veins)
    for _ in range(int(w * h / 40000)):                  # soft marble veins
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        pts = [P(x, y)]
        for _ in range(8):
            x += rng.uniform(20, 60)
            y += rng.uniform(-18, 18)
            pts.append(P(x, y))
        vd.line(pts, fill=(255, 255, 255, 14), width=round(2 * S), joint="curve")
    img.alpha_composite(veins.filter(ImageFilter.GaussianBlur(2 * S)))
    vign = Image.radial_gradient("L").resize((w * S, h * S)).point(lambda v: round(min(200, max(0, v - 90) * 1.5)))
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shade.putalpha(vign)
    img.alpha_composite(shade)
    _frame(img, w, h, dragons, size)
    return img


def _corner(d, x, y, sx, sy):
    """Gold cloud curls folding into one corner (sx, sy = ±1 for the direction inwards)."""
    g = alpha(GOLD, 230)
    j = alpha(JADE_DK, 220)
    K.cloud_curl(d, x + sx * 30, y + sy * 28, 20, g, flip=sx, width=2.8)
    K.cloud_curl(d, x + sx * 66, y + sy * 16, 11, g, flip=sx, width=2.0)
    K.cloud_curl(d, x + sx * 16, y + sy * 62, 11, g, flip=sx, width=2.0)
    K.cloud_curl(d, x + sx * 48, y + sy * 46, 7, j, flip=-sx, width=1.8)
    d.line(P(x + sx * 8, y + sy * 110, x + sx * 8, y + sy * 8, x + sx * 110, y + sy * 8), fill=g, width=round(3 * S))
    K.gem(d, x + sx * 8, y + sy * 8, 7, JADE)


@lru_cache(maxsize=12)
def _dragon(which, size, flip):
    """A gold dragon corner piece (art/ui/dragon_corner_top|bottom.png), `size` card px wide, S×."""
    art = _ui(f"dragon_corner_{which}")
    if art is None:
        return None
    k = size * S / art.size[0] * (0.49 if which == "bottom" else 1.0)    # the bottom piece is a narrow one
    art = art.resize((round(art.size[0] * k), round(art.size[1] * k)), Image.LANCZOS)
    return art.transpose(Image.FLIP_LEFT_RIGHT) if flip else art


@lru_cache(maxsize=16)
def _ui(name):
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "ui", name + ".png")
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _frame(img, w, h, dragons="all", size=150):
    """The gold double frame; gold dragons in the corners (`dragons`: all · diagonal), cloud curls elsewhere."""
    d = ImageDraw.Draw(img)
    for inset, col, wd in ((10, GOLD_DK, 2.4), (16, GOLD, 1.4), (22, (90, 70, 40), 1.0)):
        d.rectangle(P(inset, inset, w - inset, h - inset), outline=alpha(col, 230), width=round(wd * S))
    corners = {"tl": ("top", True, 4, 4), "tr": ("top", False, None, 4),
               "bl": ("bottom", False, 4, None), "br": ("bottom", True, None, None)}
    use = {"all": ("tl", "tr", "bl", "br"), "diagonal": ("tr", "bl")}[dragons]
    drawn = set()
    for key in use:
        which, flip, x, y = corners[key]
        art = _dragon(which, size, flip)
        if art is None:
            continue
        px = round(x * S) if x is not None else img.size[0] - art.size[0] - round(4 * S)
        py = round(y * S) if y is not None else img.size[1] - art.size[1] - round(4 * S)
        img.alpha_composite(art, (px, py))
        drawn.add(key)
    d = ImageDraw.Draw(img)
    for key, (x, sx), (y, sy) in (("tl", (14, 1), (14, 1)), ("tr", (w - 14, -1), (14, 1)), ("bl", (14, 1), (h - 14, -1)),
                                  ("br", (w - 14, -1), (h - 14, -1))):
        if key not in drawn:
            _corner(d, x, y, sx, sy)
    for x in (w / 2,):                                   # small diamonds mid-top and mid-bottom
        for y in (16, h - 16):
            d.polygon([P(x, y - 7), P(x + 7, y), P(x, y + 7), P(x - 7, y)], fill=alpha(GOLD, 255))


def _canvas(h, dragons="all", size=150):
    return _slate(W, h, dragons, size).copy()


def _plaque(img, cx, y, text="Mortal Ascent"):
    """The title cartouche sitting on the top frame line."""
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 30, "Bold")
    w = T.width(d, text.upper(), f) + 70
    box = (cx - w / 2, y - 26, cx + w / 2, y + 26)
    d.rounded_rectangle(P(*box), radius=10 * S, fill=(18, 18, 18, 255), outline=alpha(GOLD, 255), width=round(2 * S))
    d.rounded_rectangle(P(box[0] + 5, box[1] + 5, box[2] - 5, box[3] - 5), radius=7 * S,
                        outline=alpha(GOLD_DK, 200), width=max(1, round(1.2 * S)))
    for sgn in (-1, 1):                                   # scroll ends
        ex = cx + sgn * (w / 2 + 18)
        K.cloud_curl(d, ex, y, 12, alpha(GOLD, 240), flip=-sgn, width=2.2)
        d.polygon([P(cx + sgn * w / 2, y - 7), P(cx + sgn * (w / 2 + 8), y), P(cx + sgn * w / 2, y + 7)],
                  fill=alpha(GOLD, 255))
    T.gold_text(img, (cx, y + 1), text.upper(), f, "mm")


def _lotus(img, cx, cy, s):
    """A golden lotus finial: layered petals and a jade bud."""
    d = ImageDraw.Draw(img)
    T.soft_glow(img, (cx - s * 1.6, cy - s * 1.4, cx + s * 1.6, cy + s * 0.8), alpha(GOLD, 90), s * 0.5)
    d = ImageDraw.Draw(img)
    for ang, ln, wd, col in ((-80, 0.8, 0.26, GOLD_DK), (80, 0.8, 0.26, GOLD_DK), (-52, 0.95, 0.3, (196, 150, 70)),
                             (52, 0.95, 0.3, (196, 150, 70)), (-24, 1.1, 0.32, GOLD), (24, 1.1, 0.32, GOLD),
                             (0, 1.25, 0.34, (255, 226, 160))):
        T.petal(d, (cx, cy), ang, s * ln, s * wd, alpha(col, 255))
    d.ellipse(P(cx - s * 0.16, cy - s * 0.5, cx + s * 0.16, cy - s * 0.1), fill=alpha(JADE, 255))
    d.line(P(cx - s * 0.9, cy + 2, cx + s * 0.9, cy + 2), fill=alpha(GOLD_DK, 255), width=round(2 * S))


def _energy(img, x, top, bot):
    """Jade and gold qi twisting up the staff (the Trade Complete screen)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for phase, col in ((0, (120, 240, 180, 230)), (math.pi, (250, 214, 130, 230))):
        pts = [P(x + math.sin((y - top) / 46 + phase) * 16, y) for y in range(round(top), round(bot), 3)]
        d.line(pts, fill=col, width=round(3 * S), joint="curve")
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(6 * S)))
    img.alpha_composite(layer)
    rng = random.Random(3)
    d = ImageDraw.Draw(img)
    for _ in range(40):
        sx, sy = x + rng.uniform(-60, 60), rng.uniform(top, bot)
        r = rng.uniform(1.2, 3)
        d.ellipse(P(sx - r, sy - r, sx + r, sy + r), fill=(255, 236, 170, rng.randint(120, 230)))


def _staff(img, h, cy, energy=False):
    """The jade staff between the offers, with the lotus on top and the swap medallion."""
    x = W / 2
    top, bot = 92, h - 110
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(P(x, top, x, bot), fill=(110, 220, 170, 120), width=round(14 * S))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10 * S)))
    d = ImageDraw.Draw(img)
    d.line(P(x, top, x, bot), fill=alpha(JADE_DK, 255), width=round(6 * S))
    d.line(P(x - 1, top, x - 1, bot), fill=alpha(JADE, 200), width=round(2 * S))
    for t in (0.25, 0.75):                               # gold bands on the staff
        y = top + (bot - top) * t
        d.rounded_rectangle(P(x - 7, y - 4, x + 7, y + 4), radius=3 * S, fill=alpha(GOLD, 255))
    d.polygon([P(x, bot + 14), P(x + 8, bot), P(x - 8, bot)], fill=alpha(GOLD, 255))
    if energy:
        _energy(img, x, top, bot)
    _lotus(img, x, 74, 46)
    if energy:
        return
    # the swap medallion
    T.soft_glow(img, (x - 46, cy - 46, x + 46, cy + 46), alpha(JADE, 90), 14)
    d = ImageDraw.Draw(img)
    d.ellipse(P(x - 32, cy - 32, x + 32, cy + 32), fill=(18, 22, 22, 255), outline=alpha(GOLD, 255), width=round(3 * S))
    d.ellipse(P(x - 25, cy - 25, x + 25, cy + 25), outline=alpha(JADE, 200), width=round(1.5 * S))
    for sgn in (-1, 1):
        yy = cy + sgn * 8
        d.line(P(x - 13, yy, x + 13, yy), fill=alpha(GOLD, 255), width=round(2.6 * S))
        tip = x + 13 * sgn
        d.polygon([P(tip, yy), P(tip - 8 * sgn, yy - 6), P(tip - 8 * sgn, yy + 6)], fill=alpha(GOLD, 255))


# ── pieces ────────────────────────────────────────────────────────────

def _avatar(img, center, r, raw, name, ring):
    cx, cy = center
    T.soft_glow(img, (cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18), alpha(ring, 120), 12)
    size = round(2 * r * S)
    face = None
    if raw:
        try:
            face = Image.open(io.BytesIO(raw)).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            face = None
    initial = face is None
    if initial:                                          # a jade disc
        face = T.vgradient((size, size), (66, 120, 96), (24, 60, 46)).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    face.putalpha(mask)
    img.alpha_composite(face, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    if initial:
        T.gold_text(img, (cx, cy + 2), (name[:1] or "?").upper(), font("Cinzel.ttf", round(r * 1.05), "Bold"), "mm")
        d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5), outline=alpha(GOLD_DK, 255), width=round(4 * S))
    d.ellipse(P(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), outline=alpha(ring, 255), width=round(2 * S))


def _seal(img, center, chars, word, color):
    """A round bronze stamp: two characters above and below, the English word through the middle."""
    cx, cy = center
    r = 52
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(22, 22, 20, 235), outline=alpha(color, 240), width=round(3 * S))
    d.ellipse(P(cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6), outline=alpha(color, 140), width=max(1, round(1.2 * S)))
    T.text(d, (cx, cy - 26), chars[0], cjk(26), color, "mm")
    T.text(d, (cx, cy + 27), chars[1], cjk(26), color, "mm")
    T.text(d, (cx, cy + 1), word, font("Inter.ttf", 13, "Black"), mix(color, WHITE, 0.3), "mm")


def _shrink(d, s, face, weight, sizes, max_w):
    for size in sizes:
        f = font(face, size, weight)
        if T.width(d, s, f) <= max_w:
            return s, f
    f = font(face, sizes[-1], weight)
    return T.fit(d, s, f, max_w), f


def _rule(d, x0, x1, y):
    d.line(P(x0, y, x1, y), fill=(236, 200, 120, 70), width=max(1, round(1.2 * S)))


def _item_row(img, x0, x1, y, r):
    col = T.RARITY.get(r["color_key"], T.RARITY[None])
    T.soft_glow(img, (x0 - 4, y - 30, x0 + 56, y + 30), alpha(col, 90), 10)
    T.seal(img, (x0 + 26, y), 26, r["icon"], col)
    d = ImageDraw.Draw(img)
    q = f"×{r['qty']:,}" if not r.get("unique") else ""
    qf = font("Cinzel.ttf", 34, "Bold")
    qw = T.width(d, q, qf) if q else 0
    name, f = _shrink(d, r["name"], "Inter.ttf", "Bold", (30, 28, 26, 24), x1 - x0 - 84 - qw - 16)
    T.text(d, (x0 + 66, y - 13), name, f, WHITE, "lm")
    T.text(d, (x0 + 66, y + 17), r["grade"], font("Inter.ttf", 22, "SemiBold"), mix(col, WHITE, 0.25), "lm")
    if q:
        T.text(d, (x1, y), q, qf, GOLD, "rm")


def _side(img, side, x0, x1, title, avatar, state):
    d = ImageDraw.Draw(img)
    if title:
        T.spaced(d, (x0, 52), title, font("Cinzel.ttf", 22, "Bold"), GOLD, 2.6)
    _avatar(img, (x0 + 50, 130), 44, avatar, side["name"], GOLD if side["confirmed"] else JADE)
    d = ImageDraw.Draw(img)
    name, nf = _shrink(d, side["name"], "Cinzel.ttf", "Bold", (40, 34, 30), x1 - x0 - 240)
    T.gold_text(img, (x0 + 114, 116), name, nf, "lm")
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 116, 160), side["realm"], font("Inter.ttf", 25, "Medium"), SOFT, "lm")
    if state in ("open", "one", "complete"):
        if side["confirmed"]:
            _seal(img, (x1 - 54, 130), "成交", "CONFIRMED", GOLD)
        else:
            _seal(img, (x1 - 54, 130), "商议", "ADDING", (150, 160, 150))
    d = ImageDraw.Draw(img)
    _rule(d, x0, x1, 210)
    rows = side["rows"]
    if not rows:
        T.text(d, (x0, TOP + 8), "No items", font("Inter.ttf", 28, "Medium"), DIM, "lm")
    for i, r in enumerate(rows):
        _item_row(img, x0, x1, TOP + 8 + i * ROW, r)
    y = round(img.size[1] / S) - 214
    d = ImageDraw.Draw(img)
    _rule(d, x0, x1, y - 34)
    for k, (cur, icon, color, label) in enumerate((("lotus_coins", "lotus", LOTUS, "Lotus Coins"),
                                                   ("moon_pearls", "pearl", PEARL, "Moon Pearls"))):
        cy = y + k * 52
        amt = side[cur]
        T.icon(img, icon, (x0 + 24, cy), 38, color if amt else DIM)
        d = ImageDraw.Draw(img)
        T.text(d, (x0 + 62, cy), label, font("Inter.ttf", 27, "SemiBold"), SOFT if amt else DIM, "lm")
        T.text(d, (x1, cy), f"{amt:,}" if amt else "—", font("Cinzel.ttf", 34, "Bold"), color if amt else DIM, "rm")


def _status(img, text, color, h, note=None):
    d = ImageDraw.Draw(img)
    _rule(d, 44, W - 44, h - 100)
    d.polygon([P(W / 2, h - 107), P(W / 2 + 7, h - 100), P(W / 2, h - 93), P(W / 2 - 7, h - 100)], fill=alpha(GOLD, 255))
    T.text(d, (W / 2, h - 60 if not note else h - 70), text, font("Inter.ttf", 32, "Bold"), color, "mm")
    if note:
        T.text(d, (W / 2, h - 34), T.fit(d, note, font("Inter.ttf", 23, "Medium"), W - 140),
               font("Inter.ttf", 23, "Medium"), (240, 150, 130), "mm")


def _banner(img, cx, cy, text, color_top, color_bottom):
    f = font("Cinzel.ttf", 64, "Bold")
    d = ImageDraw.Draw(img)
    w = T.width(d, text, f)
    for sgn in (-1, 1):                                  # ≪ ≫ arrowheads pointing in, gold with jade hearts
        x = cx - sgn * (w / 2 + 40)
        for k in range(2):
            tip = x + sgn * k * 26
            pts = [P(tip, cy), P(tip - sgn * 26, cy - 20), P(tip - sgn * 18, cy), P(tip - sgn * 26, cy + 20)]
            d.polygon(pts, fill=alpha(GOLD, 255))
            d.polygon([P(tip - sgn * 6, cy), P(tip - sgn * 20, cy - 10), P(tip - sgn * 16, cy), P(tip - sgn * 20, cy + 10)],
                      fill=alpha(JADE_DK, 255))
    T.gold_text(img, (cx, cy), text, f, "mm", top=color_top, bottom=color_bottom)


# ── the trade window and the preview ──────────────────────────────────

STATUS_COLOR = {"complete": JADE, "cancelled": RED, "one": GOLD}


def render_trade(data):
    h = height(data)
    img = _canvas(h)
    kind, text = data["status"]
    avatars = data.get("avatars") or {}
    a, b = data["sides"]
    _staff(img, h, h / 2 - 40, energy=kind == "complete")
    _side(img, a, *COL[0], None, avatars.get(a["uid"]), kind)
    _side(img, b, *COL[1], None, avatars.get(b["uid"]), kind)
    if kind in ("complete", "cancelled"):
        veil = Image.new("RGBA", img.size, (6, 8, 8, 70 if kind == "complete" else 160))
        img.alpha_composite(veil)
        if kind == "complete":
            _energy(img, W / 2, 92, h - 110)
        V.crest(img, (W / 2, h / 2 - 70), 200, "won" if kind == "complete" else "lost")
        if kind == "complete":
            _banner(img, W / 2, h / 2 + 90, "Trade Complete", (255, 240, 200), (196, 146, 70))
        else:
            _banner(img, W / 2, h / 2 + 90, "Trade Cancelled", (250, 180, 160), (160, 60, 50))
    _status(img, text, STATUS_COLOR.get(kind, SOFT), h, data.get("note"))
    return T.finish(img)


def render_preview(data):
    viewer = data["viewer"]
    mine = next(s for s in data["sides"] if s["uid"] == viewer)
    theirs = next(s for s in data["sides"] if s["uid"] != viewer)
    h = height(data)
    img = _canvas(h)
    avatars = data.get("avatars") or {}
    _staff(img, h, h / 2 - 40)
    _side(img, dict(mine, confirmed=False), *COL[0], "YOU GIVE", avatars.get(mine["uid"]), "preview")
    _side(img, dict(theirs, confirmed=False), *COL[1], "YOU RECEIVE", avatars.get(theirs["uid"]), "preview")
    _status(img, "Check every line. A completed trade can't be undone.", GOLD, h)
    return T.finish(img)


# ── the picker (private Add Item / Add Currency screens) ──────────────

PH = 560


def _picker_head(img, kicker, title, sub=None):
    d = ImageDraw.Draw(img)
    T.spaced(d, (100, 66), kicker.upper(), font("Cinzel.ttf", 24, "Bold"), mix(JADE, WHITE, 0.3), 2.6)
    t, tf = _shrink(d, title, "Cinzel.ttf", "Bold", (54, 48, 42), W - 200)
    T.gold_text(img, (98, 122), t, tf, "lm")
    d = ImageDraw.Draw(img)
    if sub:
        T.text(d, (100, 172), sub, font("Inter.ttf", 27, "Medium"), SOFT, "lm")
    _rule(d, 96, W - 250, 204)
    _plaque(img, W / 2, 18)


def _medallion(img, cx, cy, r, icon, color, label, count, lit=True, key=None):
    T.soft_glow(img, (cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20), alpha(color, 110 if lit else 30), 14)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(20, 24, 24, 255), outline=alpha(GOLD if lit else DIM, 255),
              width=round(3 * S))
    d.ellipse(P(cx - r + 7, cy - r + 7, cx + r - 7, cy + r - 7), outline=alpha(color if lit else DIM, 160),
              width=max(1, round(1.4 * S)))
    art = _cat_art(key, r - 7, lit) if key else None
    if art is not None:
        img.alpha_composite(art, (round((cx - r + 7) * S), round((cy - r + 7) * S)))
    else:
        T.icon(img, icon, (cx, cy), r * 1.05, color if lit else DIM)
    d = ImageDraw.Draw(img)
    T.text(d, (cx, cy + r + 30), label, font("Inter.ttf", 26, "Bold"), WHITE if lit else DIM, "mm")
    T.text(d, (cx, cy + r + 60), f"{count} item{'s' if count != 1 else ''}" if count else "none",
           font("Inter.ttf", 22, "Medium"), SOFT if lit else DIM, "mm")


@lru_cache(maxsize=24)
def _cat_art(key, r, lit):
    """The painted category icon (art/ui/trade_cat_<key>.png) as a disc of radius r, greyed when empty."""
    art = _ui(f"trade_cat_{key}")
    if art is None:
        return None
    size = round(2 * r * S)
    art = art.resize((size, size), Image.LANCZOS)
    if not lit:
        a = art.getchannel("A")
        art = Image.blend(art.convert("RGB"), art.convert("L").convert("RGB"), 0.85).convert("RGBA")
        art.alpha_composite(Image.new("RGBA", art.size, (10, 10, 10, 120)))
        art.putalpha(a)
    return art


CAT_ICON = {"cores": ("misc:core", (230, 90, 120)), "herbs": ("herb", (110, 214, 140)),
            "materials": ("mat:base:weapon:3", (200, 180, 150)), "weapons": ("sword", (236, 170, 110)),
            "armor": ("gear:robe", (150, 186, 236)), "artifacts": ("pearl", (190, 150, 240)),
            "pills": ("pill", (240, 196, 110)), "other": ("chest", (200, 150, 90))}


def render_picker(data):
    """data: mode (categories · items · quantity · currency) and what that screen shows."""
    mode = data["mode"]
    if mode == "items":
        n = len(data["items"])
        h = max(PH, 330 + ((min(n, 12) + 1) // 2) * 96 + 60)
    elif mode == "categories":
        h = 700
    else:
        h = PH
    img = _canvas(h, "diagonal", 250)
    if mode == "categories":
        _picker_head(img, "Add an item", "Choose a category", "Only items you can trade are counted")
        cats = data["categories"]
        for i, c in enumerate(cats):
            col, row = i % 4, i // 4
            cx, cy = 180 + col * 280, 296 + row * 210
            icon, color = CAT_ICON.get(c["key"], ("chest", GOLD))
            _medallion(img, cx, cy, 48, icon, color, c["label"], c["count"], lit=c["count"] > 0, key=c["key"])
    elif mode == "items":
        _picker_head(img, data["category"], data["grade"] or "Choose a grade",
                     f"{len(data['items'])} tradeable" if data["items"] else None)
        d = ImageDraw.Draw(img)
        x = 100                                            # the grade tabs
        for g in data["grades"]:
            on = g == data["grade"]
            f = font("Inter.ttf", 24, "Bold" if on else "SemiBold")
            w = T.width(d, g, f) + 40
            if x + w > W - 100:
                break
            col = T.RARITY.get(g, T.RARITY.get(g.lower(), GOLD))
            d.rounded_rectangle(P(x, 226, x + w, 266), radius=20 * S, fill=alpha(col, 70) if on else (24, 26, 26, 200),
                                outline=alpha(col if on else DIM, 255), width=round(2 * S))
            T.text(d, (x + w / 2, 246), g, f, WHITE if on else SOFT, "mm")
            x += w + 12
        for i, it in enumerate(data["items"][:12]):
            col, row = i % 2, i // 2
            x0, x1 = 100 + col * 520, 100 + col * 520 + 470
            y = 330 + row * 96
            c = T.RARITY.get(it["color_key"], T.RARITY[None])
            T.soft_glow(img, (x0 - 4, y - 30, x0 + 56, y + 30), alpha(c, 90), 10)
            T.seal(img, (x0 + 26, y), 26, it["icon"], c)
            d = ImageDraw.Draw(img)
            name, f = _shrink(d, it["name"], "Inter.ttf", "Bold", (29, 27, 25, 23), x1 - x0 - 66)
            T.text(d, (x0 + 66, y - 14), name, f, WHITE, "lm")
            T.text(d, (x0 + 66, y + 18), f"Owned {it['owned']:,}", font("Inter.ttf", 23, "SemiBold"), SOFT, "lm")
            if it.get("offering"):
                T.text(d, (x1, y + 18), f"Offering {it['offering']:,}", font("Inter.ttf", 23, "Bold"), JADE, "rm")
        if len(data["items"]) > 12:
            d = ImageDraw.Draw(img)
            T.text(d, (W / 2, h - 40), f"+{len(data['items']) - 12} more in the menu", font("Inter.ttf", 24, "Medium"),
                   DIM, "mm")
    elif mode == "quantity":
        it = data["item"]
        col = T.RARITY.get(it["color_key"], T.RARITY[None])
        _picker_head(img, f"{data['category']} · {it['grade']}", it["name"], "How many to offer?")
        T.soft_glow(img, (110, 240, 350, 480), alpha(col, 120), 30)
        T.seal(img, (230, 360), 92, it["icon"], col)
        d = ImageDraw.Draw(img)
        owned, qty = it["owned"], data["qty"]
        T.text(d, (400, 280), "OFFERING", font("Inter.ttf", 22, "Bold"), SOFT, "lm")
        T.gold_text(img, (396, 350), f"{qty:,}", font("Cinzel.ttf", 96, "Bold"), "lm")
        d = ImageDraw.Draw(img)
        T.text(d, (W - 70, 280), "OWNED", font("Inter.ttf", 22, "Bold"), SOFT, "rm")
        T.text(d, (W - 70, 350), f"{owned:,}", font("Cinzel.ttf", 64, "Bold"), WHITE, "rm")
        x0, x1, y = 400, W - 70, 440                      # the bar between them
        d.rounded_rectangle(P(x0, y - 8, x1, y + 8), radius=8 * S, fill=(30, 34, 34, 255))
        frac = qty / owned if owned else 0
        if frac:
            d.rounded_rectangle(P(x0, y - 8, x0 + (x1 - x0) * frac, y + 8), radius=8 * S, fill=alpha(JADE, 255))
        d.ellipse(P(x0 + (x1 - x0) * frac - 13, y - 13, x0 + (x1 - x0) * frac + 13, y + 13),
                  fill=alpha(GOLD, 255), outline=(30, 24, 16, 255), width=round(2 * S))
    elif mode == "currency":
        _picker_head(img, "Add currency", "Lotus Coins & Moon Pearls", "Your balance and what you're offering")
        for i, c in enumerate(data["currencies"]):
            x0 = 100 + i * 520
            icon, color = ("lotus", LOTUS) if c["key"] == "lotus_coins" else ("pearl", PEARL)
            T.soft_glow(img, (x0 - 10, 240, x0 + 150, 400), alpha(color, 110), 24)
            T.icon(img, icon, (x0 + 70, 320), 110, color)
            d = ImageDraw.Draw(img)
            T.text(d, (x0 + 160, 262), c["label"], font("Cinzel.ttf", 34, "Bold"), color, "lm")
            T.text(d, (x0 + 160, 318), "Balance", font("Inter.ttf", 24, "Medium"), SOFT, "lm")
            T.text(d, (x0 + 470, 318), f"{c['balance']:,}", font("Inter.ttf", 30, "Bold"), WHITE, "rm")
            T.text(d, (x0 + 160, 370), "Offering", font("Inter.ttf", 24, "Medium"), SOFT, "lm")
            T.text(d, (x0 + 470, 370), f"{c['offering']:,}" if c["offering"] else "—", font("Cinzel.ttf", 36, "Bold"),
                   JADE if c["offering"] else DIM, "rm")
    if data.get("note"):
        d = ImageDraw.Draw(img)
        _rule(d, 56, W - 56, h - 92)
        T.text(d, (W / 2, h - 56), T.fit(d, data["note"], font("Inter.ttf", 28, "Bold"), W - 140),
               font("Inter.ttf", 28, "Bold"), JADE if not data["note"].startswith("⚠") else RED, "mm")
    return T.finish(img)


__all__ = ["render_trade", "render_preview", "render_picker", "W", "height"]
