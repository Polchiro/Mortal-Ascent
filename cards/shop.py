"""
/shop: the Moon Pearl Shop card, on the night sky of the other cards.

  ┌ ✧ MOON PEARL SHOP ✧, "Speed and style, never power.", your pearls
  ├ 2 × 4 gold-framed glass tiles: the item's painting (art/icons/shop), name, 🌙 price (red when you
  │   can't afford it), one line of what it does; "COMING SOON" on what isn't for sale yet
  └ where pearls come from

render_shop(data) takes bot.views.shop_data(player).
"""
from PIL import Image, ImageDraw

from . import theme as T
from .compendium import EDGE, SOFT, TEXT, _glass, _sky
from .theme import P, S, alpha, font, mix

W = T.W
PAD = 28
GAP = 20
COLS = 4
TILE_H = 340
TOP = 160
PEARL = (196, 222, 255)
RED = (255, 130, 110)


def render_shop(data):
    items = data["items"]
    rows = -(-len(items) // COLS)
    H = TOP + rows * (TILE_H + GAP) - GAP + 96
    img = _sky(H)
    _header(img, data)
    tw = (W - 2 * PAD - (COLS - 1) * GAP) / COLS
    for i, it in enumerate(items):
        r, c = divmod(i, COLS)
        x, y = PAD + c * (tw + GAP), TOP + r * (TILE_H + GAP)
        _tile(img, (x, y, x + tw, y + TILE_H), it, data["pearls"])
    d = ImageDraw.Draw(img)
    fy = H - 50
    f = font("Inter.ttf", 26, "SemiBold")
    parts = [("Get Moon Pearls with ", SOFT), ("/recharge", PEARL), (" or ", SOFT), ("/trade", PEARL), (".", SOFT)]
    total = sum(T.width(d, s, f) for s, _ in parts)
    x = W / 2 - total / 2
    for s, c in parts:
        T.text(d, (x, fy), s, f, c, "lm")
        x += T.width(d, s, f)
    d.rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(EDGE, 220), width=round(2 * S))
    return T.finish(img)


def _star(d, x, y, r, color):
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else r * 0.32
        a = k * 3.14159 / 4 - 3.14159 / 2
        pts.append(P(x + rr * __import__("math").cos(a), y + rr * __import__("math").sin(a)))
    d.polygon(pts, fill=color)


def _header(img, data):
    title = "MOON PEARL SHOP"
    f = font("Cinzel.ttf", 52, "Black")
    d = ImageDraw.Draw(img)
    tw = T.width(d, title, f)
    T.gold_text(img, (W / 2, 60), title, f, "mm", glow=alpha(T.GOLD, 100))
    d = ImageDraw.Draw(img)
    for sx in (W / 2 - tw / 2 - 34, W / 2 + tw / 2 + 34):
        _star(d, sx, 60, 13, T.GOLD_HI)
    sf, bf = font("Inter.ttf", 27, "Medium"), font("Inter.ttf", 27, "Bold")
    a, b, c = "Speed and style, never power.  You have ", f"{data['pearls']:,}", " Moon Pearls."
    total = T.width(d, a, sf) + 34 + T.width(d, b, bf) + T.width(d, c, sf)
    x = W / 2 - total / 2
    T.text(d, (x, 118), a, sf, TEXT, "lm")
    x += T.width(d, a, sf)
    T.icon(img, "pearl", (x + 15, 118), 28, PEARL)
    d = ImageDraw.Draw(img)
    x += 34
    T.text(d, (x, 118), b, bf, T.GOLD_HI, "lm")
    x += T.width(d, b, bf)
    T.text(d, (x, 118), c, sf, TEXT, "lm")


def _tile(img, box, it, pearls):
    x0, y0, x1, y1 = box
    soon = it.get("soon")
    T.soft_glow(img, (x0 + 30, y0 + 20, x1 - 30, y0 + 190), (240, 200, 120, 55 if not soon else 25), 24)
    _glass(img, box, edge=T.GOLD_HI if not soon else mix(EDGE, (0, 0, 0), 0.2), a=175, r=16, width=2.2)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(P(x0 + 7, y0 + 7, x1 - 7, y1 - 7), radius=11 * S, outline=alpha(EDGE, 110), width=max(1, S))
    cx = (x0 + x1) / 2
    T.icon(img, it["icon"], (cx, y0 + 96), 150, T.GOLD)
    if soon:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(P(x0 + 2, y0 + 2, x1 - 2, y1 - 2), radius=16 * S, fill=(8, 12, 24, 90))
        img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    room = x1 - x0 - 22
    nf = next((font("Inter.ttf", s, "Bold") for s in (27, 25, 23, 21)
               if T.width(d, it["name"], font("Inter.ttf", s, "Bold")) <= room), font("Inter.ttf", 21, "Bold"))
    T.text(d, (cx, y0 + 194), T.fit(d, it["name"], nf, room), nf, TEXT, "mm")
    pf = font("Inter.ttf", 28, "Bold")
    price = it["price"]
    color = PEARL if soon or pearls >= it.get("min_price", 0) else RED
    tw = T.width(d, price, pf)
    T.icon(img, "pearl", (cx - tw / 2 - 4, y0 + 236), 28, PEARL)
    T.text(ImageDraw.Draw(img), (cx - tw / 2 + 16, y0 + 236), price, pf, color, "lm")
    if it.get("was"):
        wf = font("Inter.ttf", 21, "SemiBold")
        wx = cx + tw / 2 + 30
        T.text(d, (wx, y0 + 238), it["was"], wf, mix(SOFT, (0, 0, 0), 0.25), "lm")
        ww = T.width(d, it["was"], wf)
        d.line(P(wx - 2, y0 + 238, wx + ww + 2, y0 + 238), fill=RED, width=round(2 * S))
    df = font("Inter.ttf", 22, "Medium")
    for k, line in enumerate(T.wrap(d, it["text"], df, x1 - x0 - 30, lines=2)):
        T.text(d, (cx, y0 + 278 + k * 28), line, df, SOFT, "mm")
    if soon:
        bf = font("Inter.ttf", 19, "Bold")
        label = "COMING SOON"
        bw = T.width(d, label, bf) + 26
        d.rounded_rectangle(P(cx - bw / 2, y0 + 18, cx + bw / 2, y0 + 46), radius=14 * S, fill=(40, 30, 70, 235),
                            outline=(190, 160, 255), width=max(1, S))
        T.text(d, (cx, y0 + 32), label, bf, (226, 214, 255), "mm")
