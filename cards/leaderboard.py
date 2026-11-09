"""
/leaderboard: the top ten of a board (Realm, Lotus Coins, Moon Pearls) on the night sky and glass of /index.

  ┌ header: the board's painting, LEADERBOARD, how many cultivators are ranked
  ├ tabs: every board, the open one lit
  ├ podium: #2 · #1 (raised, with a crown) · #3 in gold / silver / bronze rings with their avatars
  ├ ranks 4-10 as glass rows: rank, name, realm, value
  └ your own rank, in gold

render_leaderboard(data) takes bot.leaderboard.board(...) plus "avatars": {user_id: png bytes}.
"""
import io
from functools import lru_cache

from PIL import Image, ImageDraw

from . import theme as T
from .compendium import EDGE, GOLD_LINE, PAD, SOFT, TEXT, _glass, _sky
from .theme import P, S, alpha, font, mix

W = T.W
MEDAL = {1: ((255, 214, 120), (186, 128, 40)), 2: ((236, 240, 248), (140, 152, 176)), 3: ((236, 168, 112), (150, 84, 40))}
LOTUS = (244, 196, 120)
PEARL = (186, 214, 255)
TABS = (PAD, 150, W - PAD, 214)
PODIUM_Y = 252
ROW_H = 66
ROW_GAP = 8


def render_leaderboard(data):
    rest = data["top"][3:]
    rows_y = PODIUM_Y + 400
    H = rows_y + len(rest) * (ROW_H + ROW_GAP) + 20 + 90 + 20
    img = _sky(H)
    _header(img, data)
    _tabs(img, data)
    _podium(img, data)
    me = data.get("me")
    for i, r in enumerate(rest):
        y = rows_y + i * (ROW_H + ROW_GAP)
        _row(img, (PAD, y, W - PAD, y + ROW_H), r, data["board"], me and me["user_id"] == r["user_id"])
    _me(img, (PAD, H - 110, W - PAD, H - 22), me, data["board"])
    ImageDraw.Draw(img).rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(EDGE, 220),
                                          width=round(2 * S))
    return T.finish(img)


def _header(img, data):
    T.icon(img, data["icon"], (PAD + 64, 78), 104, T.GOLD)
    T.gold_text(img, (PAD + 140, 26), "LEADERBOARD", font("Cinzel.ttf", 52, "Black"), glow=alpha(T.GOLD, 90))
    d = ImageDraw.Draw(img)
    T.text(d, (PAD + 142, 116), f"Top {len(data['top'])} of {data['players']:,} cultivators",
           font("Inter.ttf", 27, "SemiBold"), SOFT, "lm")
    T.text(d, (W - PAD - 6, 52), "风云榜", T.cjk(34), alpha(T.GOLD_HI, 230), "rm")


def _tabs(img, data):
    _glass(img, TABS, a=200, r=12)
    x0, y0, x1, y1 = TABS
    n = len(data["boards"])
    w = (x1 - x0) / n
    f = font("Cinzel.ttf", 24, "Bold")
    for i, (key, label) in enumerate(data["boards"]):
        cx, cy = x0 + w * (i + 0.5), (y0 + y1) / 2
        active = key == data["board"]
        if active:
            T.soft_glow(img, (x0 + w * i + 10, y0 + 8, x0 + w * (i + 1) - 10, y1 - 8), alpha(T.GOLD, 110), 10)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle(P(x0 + w * i + 6, y0 + 6, x0 + w * (i + 1) - 6, y1 - 6), radius=10 * S,
                                outline=alpha(T.GOLD_HI, 255), width=round(2 * S))
        d = ImageDraw.Draw(img)
        icon = {"realm": "art:index/techniques_heaven", "lotus_coins": "lotus", "moon_pearls": "pearl"}.get(key, "star")
        tw = T.width(d, label.upper(), f)
        sx = cx - (tw + 46) / 2
        T.icon(img, icon, (sx + 18, cy), 38 if icon.startswith("art:") else 32,
               LOTUS if key == "lotus_coins" else PEARL if key == "moon_pearls" else T.GOLD)
        T.text(ImageDraw.Draw(img), (sx + 46, cy), label.upper(), f, GOLD_LINE if active else SOFT, "lm")
        if i:
            d.line(P(x0 + w * i, y0 + 16, x0 + w * i, y1 - 16), fill=alpha(EDGE, 90), width=max(1, S))


@lru_cache(maxsize=64)
def _face(data, px):
    try:
        im = Image.open(io.BytesIO(data)).convert("RGBA").resize((px, px), Image.LANCZOS)
    except Exception:
        return None
    m = Image.new("L", (px * 2, px * 2), 0)
    ImageDraw.Draw(m).ellipse((0, 0, px * 2 - 1, px * 2 - 1), fill=255)
    im.putalpha(m.resize((px, px), Image.LANCZOS))
    return im


def _initial(img, center, r, name, color):
    cx, cy = center
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(22, 30, 54, 255))
    T.gold_text(img, (cx, cy), (name or "?")[0].upper(), font("Cinzel.ttf", round(r * 0.95), "Black"), "mm",
                top=mix(color, (255, 255, 255), 0.4), bottom=mix(color, (0, 0, 0), 0.3))


def _medallion(img, center, r, rank, row, avatar):
    """The avatar in a gold / silver / bronze ring, with its rank on a coin at the bottom."""
    cx, cy = center
    hi, lo = MEDAL[rank]
    T.soft_glow(img, (cx - r - 30, cy - r - 30, cx + r + 30, cy + r + 30), alpha(hi, 120 if rank == 1 else 80), 18)
    face = _face(avatar, round(2 * r * S)) if avatar else None
    if face is not None:
        img.alpha_composite(face, (round((cx - r) * S), round((cy - r) * S)))
    else:
        _initial(img, center, r, row["name"], hi)
    d = ImageDraw.Draw(img)
    for k, (w_, c) in enumerate(((9, lo), (5, hi), (1.6, mix(hi, (255, 255, 255), 0.5)))):
        rr = r + 5 - k * 1.5
        d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), outline=c, width=round(w_ * S))
    if rank == 1:
        _crown(img, (cx, cy - r - 20), hi, lo)
    by = cy + r + 2
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - 22, by - 22, cx + 22, by + 22), fill=mix(lo, (0, 0, 0), 0.35), outline=hi, width=round(2.4 * S))
    T.text(d, (cx, by + 1), str(rank), font("Cinzel.ttf", 26, "Black"), mix(hi, (255, 255, 255), 0.3), "mm")


def _crown(img, base, hi, lo):
    """A small three-pointed gold crown over the champion."""
    cx, by = base
    w, h = 34, 26
    pts = [(cx - w, by), (cx - w, by - h * 0.55), (cx - w * 0.5, by - h * 0.2), (cx, by - h),
           (cx + w * 0.5, by - h * 0.2), (cx + w, by - h * 0.55), (cx + w, by)]
    T.soft_glow(img, (cx - w - 14, by - h - 14, cx + w + 14, by + 10), alpha(hi, 120), 10)
    d = ImageDraw.Draw(img)
    d.polygon([P(*p) for p in pts], fill=hi, outline=lo)
    d.line(P(cx - w, by - 3, cx + w, by - 3), fill=lo, width=round(3 * S))
    for x, y in ((cx - w, by - h * 0.55), (cx, by - h), (cx + w, by - h * 0.55)):
        d.ellipse(P(x - 4.5, y - 4.5, x + 4.5, y + 4.5), fill=(250, 246, 230), outline=lo)


def _value(img, center, board, row, f, anchor="mm"):
    """The board's value: coins / pearls with their icon, or the realm and layer."""
    d = ImageDraw.Draw(img)
    cx, cy = center
    if board == "realm":
        T.text(d, (cx, cy), row["value"], f, GOLD_LINE, anchor)
        return
    icon, color = ("lotus", LOTUS) if board == "lotus_coins" else ("pearl", PEARL)
    s = row["value"]
    tw = T.width(d, s, f)
    size = f.size / S * 1.05 if hasattr(f, "size") else 30
    total = size + 8 + tw
    x = cx - total / 2 if anchor == "mm" else cx - total
    T.icon(img, icon, (x + size / 2, cy), size, color)
    T.text(ImageDraw.Draw(img), (x + size + 8, cy), s, f, mix(color, (255, 255, 255), 0.45), "lm")


def _podium(img, data):
    top, board = data["top"], data["board"]
    avatars = data.get("avatars") or {}
    spots = [(2, W / 2 - 360, PODIUM_Y + 128, 76), (1, W / 2, PODIUM_Y + 112, 92), (3, W / 2 + 360, PODIUM_Y + 128, 76)]
    for rank, cx, cy, r in spots:
        if rank > len(top):
            continue
        row = top[rank - 1]
        _medallion(img, (cx, cy), r, rank, row, avatars.get(row["user_id"]))
        d = ImageDraw.Draw(img)
        name_y = cy + r + 50
        nf = font("Inter.ttf", 34 if rank == 1 else 30, "Bold")
        T.text(d, (cx, name_y), T.fit(d, row["name"], nf, 320), nf, TEXT, "mm")
        if board == "realm":
            T.text(d, (cx, name_y + 40), row["realm"], font("Cinzel.ttf", 26, "Bold"), GOLD_LINE, "mm")
            T.text(d, (cx, name_y + 74), row["value"], font("Inter.ttf", 25, "SemiBold"), SOFT, "mm")
        else:
            _value(img, (cx, name_y + 42), board, row, font("Inter.ttf", 32, "Bold"))
            T.text(ImageDraw.Draw(img), (cx, name_y + 80), row["realm"], font("Inter.ttf", 24, "Medium"), SOFT, "mm")
    if not top:
        T.text(ImageDraw.Draw(img), (W / 2, PODIUM_Y + 160), "No cultivators ranked yet.",
               font("Inter.ttf", 30, "SemiBold"), SOFT, "mm")


def _row(img, box, row, board, mine):
    x0, y0, x1, y1 = box
    if mine:
        T.soft_glow(img, (x0 - 4, y0 - 4, x1 + 4, y1 + 4), alpha(T.GOLD, 110), 8, "rect")
    _glass(img, box, edge=T.GOLD_HI if mine else EDGE, a=180, width=2.2 if mine else 1.4)
    cy = (y0 + y1) / 2
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 52, cy), str(row["rank"]), font("Cinzel.ttf", 32, "Black"), SOFT, "mm")
    d.line(P(x0 + 96, y0 + 14, x0 + 96, y1 - 14), fill=alpha(EDGE, 90), width=max(1, S))
    nf = font("Inter.ttf", 29, "Bold")
    name = T.fit(d, row["name"], nf, 420)
    T.text(d, (x0 + 120, cy), name, nf, GOLD_LINE if mine else TEXT, "lm")
    if board == "realm":
        T.text(d, (x1 - 30, cy), f"{row['realm']}  ·  {row['value']}", font("Inter.ttf", 27, "SemiBold"),
               GOLD_LINE, "rm")
    else:
        T.text(d, (x0 + 130 + T.width(d, name, nf), cy + 2), f"·  {row['realm']}", font("Inter.ttf", 23, "Medium"),
               SOFT, "lm")
        _value(img, (x1 - 30, cy), board, row, font("Inter.ttf", 29, "Bold"), anchor="rm")


def _me(img, box, me, board):
    x0, y0, x1, y1 = box
    _glass(img, box, edge=T.GOLD_HI, a=205, width=2.2)
    cy = (y0 + y1) / 2
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 30, cy), "YOUR RANK", font("Cinzel.ttf", 24, "Bold"), SOFT, "lm")
    if not me:
        T.text(d, (x1 - 30, cy), "Use /start to join the ranks", font("Inter.ttf", 27, "SemiBold"), SOFT, "rm")
        return
    T.gold_text(img, (x0 + 220, cy), f"#{me['rank']:,}", font("Cinzel.ttf", 44, "Black"), "lm", glow=alpha(T.GOLD, 80))
    d = ImageDraw.Draw(img)
    nf = font("Inter.ttf", 29, "Bold")
    T.text(d, (x0 + 400, cy), T.fit(d, me["name"], nf, 330), nf, TEXT, "lm")
    if board == "realm":
        T.text(d, (x1 - 30, cy), f"{me['realm']}  ·  {me['value']}", font("Inter.ttf", 27, "SemiBold"), GOLD_LINE, "rm")
    else:
        _value(img, (x1 - 30, cy), board, me, font("Inter.ttf", 30, "Bold"), anchor="rm")
