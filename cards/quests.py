"""
/daily: the Daily Quests card, on the same night sky and frosted glass as /index.

  ┌ header: scroll seal, DAILY QUESTS, "Resets in 7h 12m", today's count (2 / 4)
  ├ one glass row per quest: painted icon, name, what to do, progress bar, 🪷 / 🌙 reward, state
  │   (READY to claim in gold, CLAIMED in green)
  └ the all-done panel: its coins and pearls, and the chests it can give (Common → Legendary) with
    their chances; the chest won is lit once claimed

render_quests(data) takes bot.quests.board(...).
"""
from functools import lru_cache

from PIL import Image, ImageDraw

from . import theme as T
from .compendium import EDGE, GOLD_LINE, PAD, SOFT, TEXT, _glass, _sky
from .theme import P, S, alpha, font, mix

W = T.W
ROW_H = 132
ROW_GAP = 14
TOP = 168
GREEN = (112, 222, 146)
LOTUS = (244, 196, 120)
PEARL = (186, 214, 255)
CHEST_LABEL = {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "epic": "Epic", "legendary": "Legendary"}


@lru_cache(maxsize=16)
def _chest(tier, width):
    return T.chest_art(tier, width)


def _clock(seconds):
    h, m = divmod(max(0, seconds) // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def render_quests(data):
    rows = data["quests"]
    bonus_y = TOP + len(rows) * (ROW_H + ROW_GAP) + 6
    H = bonus_y + 300 + 26
    img = _sky(H)
    _header(img, data)
    for i, q in enumerate(rows):
        _row(img, (PAD, TOP + i * (ROW_H + ROW_GAP), W - PAD, TOP + i * (ROW_H + ROW_GAP) + ROW_H), q)
    _bonus(img, (PAD, bonus_y, W - PAD, bonus_y + 300), data["bonus"])
    ImageDraw.Draw(img).rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(EDGE, 220),
                                          width=round(2 * S))
    return T.finish(img)


def _header(img, data):
    T.icon(img, "emblem:book", (PAD + 64, 78), 104, T.GOLD)
    T.gold_text(img, (PAD + 140, 26), "DAILY QUESTS", font("Cinzel.ttf", 52, "Black"), glow=alpha(T.GOLD, 90))
    d = ImageDraw.Draw(img)
    T.text(d, (PAD + 142, 116), f"{data['name']}  ·  Resets in {_clock(data['reset_in'])}",
           font("Inter.ttf", 27, "SemiBold"), SOFT, "lm")
    done = sum(q["done"] for q in data["quests"])
    T.text(d, (W - PAD - 10, 44), "TODAY", font("Cinzel.ttf", 22, "Bold"), SOFT, "rm")
    T.gold_text(img, (W - PAD - 10, 98), f"{done} / {len(data['quests'])}", font("Cinzel.ttf", 50, "Black"), "rm",
                top=(244, 247, 252), bottom=(150, 164, 194))


def _reward(img, x, y, kind, amount, color, f):
    """'🪷 120' drawn with the game's lotus / pearl icon; returns the x after it."""
    T.icon(img, kind, (x + 16, y), 32, color)
    d = ImageDraw.Draw(img)
    s = f"{amount:,}"
    T.text(d, (x + 38, y), s, f, mix(color, (255, 255, 255), 0.45), "lm")
    return x + 38 + T.width(d, s, f)


def _row(img, box, q):
    x0, y0, x1, y1 = box
    edge = GREEN if q["claimed"] else (T.GOLD_HI if q["done"] else EDGE)
    if q["done"] and not q["claimed"]:
        T.soft_glow(img, (x0 - 4, y0 - 4, x1 + 4, y1 + 4), alpha(T.GOLD, 120), 10, "rect")
    _glass(img, box, edge=edge, a=185, width=2.2 if q["done"] else 1.6)
    cy = (y0 + y1) / 2
    T.soft_glow(img, (x0 + 14, y0 + 14, x0 + 118, y1 - 14), (120, 150, 220, 60), 12)
    T.icon(img, q["icon"], (x0 + 66, cy), 96, T.GOLD)
    if q["claimed"]:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse(P(x0 + 18, cy - 48, x0 + 114, cy + 48), fill=(6, 10, 20, 110))
        img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    tx = x0 + 134
    T.text(d, (tx, y0 + 34), q["name"], font("Inter.ttf", 31, "Bold"), TEXT, "lm")
    T.text(d, (tx, y0 + 70), q["text"], font("Inter.ttf", 25, "Medium"), SOFT, "lm")
    # progress bar
    bx0, bx1, by = tx, tx + 430, y0 + 106
    d.rounded_rectangle(P(bx0, by - 7, bx1, by + 7), radius=7 * S, fill=(8, 12, 24, 230),
                        outline=alpha(EDGE, 120), width=max(1, S))
    frac = q["have"] / q["need"] if q["need"] else 1
    if frac > 0:
        fill = GREEN if q["done"] else (232, 186, 96)
        d.rounded_rectangle(P(bx0 + 2, by - 5, bx0 + 2 + (bx1 - bx0 - 4) * frac, by + 5), radius=5 * S, fill=fill)
    T.text(d, (bx1 + 16, by), f"{q['have']} / {q['need']}", font("Inter.ttf", 24, "Bold"),
           GREEN if q["done"] else TEXT, "lm")
    # reward and state on the right
    rf = font("Inter.ttf", 29, "Bold")
    sx = x1 - 196
    d.line(P(sx - 24, y0 + 22, sx - 24, y1 - 22), fill=alpha(EDGE, 90), width=max(1, S))
    _reward(img, sx, y0 + 40, "lotus", q["coins"], LOTUS, rf)
    _reward(img, sx, y0 + 84, "pearl", q["pearls"], PEARL, rf)
    if q["done"]:
        _state(img, (x1 - 300, cy), q["claimed"])


def _state(img, center, claimed):
    """A small READY (gold) or CLAIMED (green, with a tick) seal left of the reward."""
    cx, cy = center
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 21, "Bold")
    label, color = ("CLAIMED", GREEN) if claimed else ("READY", T.GOLD_HI)
    w = T.width(d, label, f) + (52 if claimed else 32)
    x0 = cx - w
    d.rounded_rectangle(P(x0, cy - 19, cx, cy + 19), radius=19 * S, fill=alpha(mix(color, (0, 0, 0), 0.7), 235),
                        outline=color, width=round(1.6 * S))
    if claimed:
        s = 8
        px = x0 + 22
        d.line([P(px - s, cy), P(px - s * 0.3, cy + s * 0.7), P(px + s, cy - s * 0.75)], fill=color,
               width=round(3 * S), joint="curve")
        T.text(d, (x0 + 38, cy), label, f, mix(color, (255, 255, 255), 0.4), "lm")
    else:
        T.text(d, (x0 + w / 2, cy), label, f, mix(color, (255, 255, 255), 0.3), "mm")


def _bonus(img, box, b):
    x0, y0, x1, y1 = box
    lit = b["ready"] or b["claimed"]
    if b["ready"]:
        T.soft_glow(img, (x0 - 6, y0 - 6, x1 + 6, y1 + 6), alpha(T.GOLD, 150), 12, "rect")
    _glass(img, box, edge=T.GOLD_HI if lit else EDGE, a=195, width=2.4 if lit else 1.8)
    d = ImageDraw.Draw(img)
    T.gold_text(img, (x0 + 30, y0 + 38), "COMPLETE ALL QUESTS", font("Cinzel.ttf", 30, "Black"), "lm",
                glow=alpha(T.GOLD, 70) if lit else None)
    d = ImageDraw.Draw(img)
    if b["claimed"]:
        status, sc = "Claimed today", GREEN
    elif b["ready"]:
        status, sc = "Ready to claim!", T.GOLD_HI
    else:
        status, sc = f"{b['done']} of {b['of']} done", SOFT
    T.text(d, (x1 - 30, y0 + 38), status, font("Inter.ttf", 26, "Bold"), sc, "rm")
    rf = font("Inter.ttf", 30, "Bold")
    x = _reward(img, x0 + 30, y0 + 92, "lotus", b["coins"], LOTUS, rf)
    x = _reward(img, x + 26, y0 + 92, "pearl", b["pearls"], PEARL, rf)
    d = ImageDraw.Draw(img)
    T.text(d, (x + 26, y0 + 92), f"+ a {b['chance']:.0%} chance of a chest:", font("Inter.ttf", 26, "SemiBold"),
           TEXT, "lm")
    # the chests
    tiers = list(b["tiers"])
    n = len(tiers)
    slot = (x1 - x0 - 60) / n
    won = b.get("chest")
    for i, t in enumerate(tiers):
        cx = x0 + 30 + slot * (i + 0.5)
        cy = y0 + 196
        color = T.RARITY.get(t, T.GOLD)
        if b["claimed"] and won == t:
            T.soft_glow(img, (cx - 92, cy - 70, cx + 92, cy + 66), alpha(T.GOLD_HI, 200), 16)
        art = _chest(t, 128)
        if art is not None:
            if (b["claimed"] and won != t) or not lit:
                a = art.getchannel("A")
                art = Image.blend(art, art.convert("L").convert("RGBA"), 0.55)
                art.putalpha(a.point(lambda v: v * 0.7))
            img.alpha_composite(art, (round(cx * S - art.size[0] / 2), round((cy - 6) * S - art.size[1] / 2)))
        else:
            T.icon(img, f"chest:{t}", (cx, cy - 6), 90, color)
        d = ImageDraw.Draw(img)
        label = "WON!" if b["claimed"] and won == t else CHEST_LABEL.get(t, t.title())
        T.text(d, (cx, y1 - 46), label, font("Inter.ttf", 23, "Bold"),
               T.GOLD_HI if b["claimed"] and won == t else mix(color, (255, 255, 255), 0.35), "mm")
        T.text(d, (cx, y1 - 20), _pct(b["tiers"][t]), font("Inter.ttf", 22, "SemiBold"), SOFT, "mm")
    if b["claimed"] and not won:
        T.text(ImageDraw.Draw(img), ((x0 + x1) / 2, y0 + 140), "No chest this time. Try again tomorrow!",
               font("Inter.ttf", 25, "SemiBold"), SOFT, "mm")


def _pct(p):
    v = p * 100
    return f"{v:.0f}%" if v >= 10 else f"{v:.1f}%".replace(".0%", "%")
