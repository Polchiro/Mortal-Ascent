"""
/blessing: the Heavenly Blessings card, on the night sky of the other cards.

  ┌ Heavenly Blessings, and a status pill: your pearls · your active blessing and days left
  ├ one row per tier: its painted orb (art/icons/blessings), name, every boost, 🌙 price;
  │   the active tier glows gold with ACTIVE · n days
  └ how buying works (same tier adds 30 days; another replaces yours)

render_blessings(data) takes bot.views.blessing_data(player).
"""
from PIL import ImageDraw

from . import theme as T
from .compendium import EDGE, SOFT, TEXT, _glass, _sky
from .theme import P, S, alpha, font, mix

W = T.W
PAD = 70
ROW_H = 84
GAP = 12
TOP = 176
PEARL = (196, 222, 255)
RED = (255, 130, 110)
GREEN = (112, 222, 146)


def render_blessings(data):
    rows = data["tiers"]
    H = TOP + len(rows) * (ROW_H + GAP) - GAP + 100
    img = _sky(H)
    T.gold_text(img, (W / 2, 52), "HEAVENLY BLESSINGS", font("Cinzel.ttf", 54, "Black"), "mm", glow=alpha(T.GOLD, 100))
    _status(img, data)
    for i, r in enumerate(rows):
        y = TOP + i * (ROW_H + GAP)
        _row(img, (PAD, y, W - PAD, y + ROW_H), r, data["pearls"])
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 24, "Medium")
    T.text(d, (W / 2, H - 60), f"Each blessing lasts {data['days']} days. The same tier adds {data['days']} days;",
           f, SOFT, "mm")
    T.text(d, (W / 2, H - 30), "another tier replaces yours with a fresh 30 days (no refund).", f, SOFT, "mm")
    d.rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(EDGE, 220), width=round(2 * S))
    return T.finish(img)


def _status(img, data):
    d = ImageDraw.Draw(img)
    f, bf = font("Inter.ttf", 25, "Medium"), font("Inter.ttf", 25, "Bold")
    act = data.get("active")
    right = f"{act[0]} · {act[1]} day{'s' if act[1] != 1 else ''} left" if act else "No active blessing"
    parts = [("You have ", f, TEXT), (f"{data['pearls']:,}", bf, T.GOLD_HI), (" Moon Pearls", f, TEXT),
             ("   |   ", f, mix(EDGE, (0, 0, 0), 0.2)), (right, bf if act else f, GREEN if act else SOFT)]
    total = sum(T.width(d, s, ff) for s, ff, _ in parts) + 34
    x0, y0, x1, y1 = W / 2 - total / 2 - 28, 98, W / 2 + total / 2 + 28, 146
    _glass(img, (x0, y0, x1, y1), a=210, r=24, width=1.8)
    x = x0 + 28
    T.icon(img, "pearl", (x + 14, (y0 + y1) / 2), 28, PEARL)
    x += 34
    d = ImageDraw.Draw(img)
    for s, ff, c in parts:
        T.text(d, (x, (y0 + y1) / 2), s, ff, c, "lm")
        x += T.width(d, s, ff)


def _row(img, box, r, pearls):
    x0, y0, x1, y1 = box
    color = r["color"]
    active = r.get("active")
    if active:
        T.soft_glow(img, (x0 - 6, y0 - 6, x1 + 6, y1 + 6), alpha(T.GOLD, 140), 10, "rect")
    _glass(img, (x0 + 30, y0 + 6, x1, y1 - 6), edge=T.GOLD_HI if active else mix(color, EDGE, 0.5), a=185, r=40,
           width=2.4 if active else 1.6)
    # a soft band of the tier's colour behind the name
    T.soft_glow(img, (x0 + 60, y0 + 14, x0 + 520, y1 - 14), alpha(color, 55), 22, "rect")
    cy = (y0 + y1) / 2
    T.soft_glow(img, (x0 - 10, y0 - 8, x0 + 94, y1 + 8), alpha(color, 120), 14)
    T.icon(img, r["icon"], (x0 + 42, cy), 92 / 1.18, color)
    d = ImageDraw.Draw(img)
    tx = x0 + 104
    T.text(d, (tx, cy - 15), r["name"], font("Cinzel.ttf", 30, "Bold"), mix(color, (255, 255, 255), 0.55), "lm")
    pr = font("Inter.ttf", 28, "Bold")
    s = f"{r['price']:,}"
    tw = T.width(d, s, pr)
    px1 = x1 - 22
    px0 = px1 - tw - 70
    room = px0 - tx - 16 - (130 if active else 0)
    pf = next((font("Inter.ttf", z, "SemiBold") for z in (22, 21, 20, 19)
               if T.width(d, r["perks"], font("Inter.ttf", z, "SemiBold")) <= room), font("Inter.ttf", 19, "SemiBold"))
    T.text(d, (tx, cy + 21), T.fit(d, r["perks"], pf, room), pf, TEXT, "lm")
    # price pill on the right
    d.rounded_rectangle(P(px0, cy - 22, px1, cy + 22), radius=22 * S, fill=(10, 14, 28, 220),
                        outline=alpha(EDGE, 200), width=round(1.4 * S))
    T.icon(img, "pearl", (px0 + 26, cy), 28, PEARL)
    T.text(ImageDraw.Draw(img), (px0 + 46, cy), s, pr, PEARL if pearls >= r["price"] else RED, "lm")
    if active:
        bf = font("Inter.ttf", 19, "Bold")
        label = f"ACTIVE · {r['days_left']}d"
        bw = T.width(d, label, bf) + 24
        bx1 = px0 - 14
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(P(bx1 - bw, cy - 16, bx1, cy + 16), radius=16 * S, fill=(18, 60, 34, 235),
                            outline=GREEN, width=max(1, S))
        T.text(d, (bx1 - bw / 2, cy), label, bf, mix(GREEN, (255, 255, 255), 0.4), "mm")
