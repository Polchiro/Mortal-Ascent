"""
The trade window card (docs/trading.md): two offers side by side, no boxes.

  render_trade(data)    the public window: both players, their items and currencies, confirmed seals,
                        and the state (adding · one confirmed · complete · cancelled)
  render_preview(data)  the Trade Preview before confirming: You give · You receive

data comes from bot/trading.card_data (+ "avatars": {uid: png bytes}, "viewer": uid for the preview).
The card grows taller with the longest offer, so every line is shown.
"""
import io

from PIL import Image, ImageDraw

from . import theme as T
from . import victory as V
from .theme import P, S, alpha, font, mix

W = 1200
H = 760                       # the height with up to 5 lines a side; taller offers make a taller card
ROW = 64
TOP = 250                     # first item row
COL = [(48, 568), (632, 1152)]
WHITE = (250, 244, 232)
SOFT = (206, 198, 186)
DIM = (150, 142, 132)
GOLD = (240, 200, 110)
JADE = (110, 214, 160)
RED = (232, 96, 80)
LOTUS = (240, 196, 110)
PEARL = (196, 214, 246)


def height(data):
    n = max([len(s["rows"]) for s in data["sides"]] + [5])
    return TOP + n * ROW + 290


def _avatar(img, center, r, raw, name, ring):
    cx, cy = center
    T.soft_glow(img, (cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16), alpha(ring, 110), 12)
    size = round(2 * r * S)
    face = None
    if raw:
        try:
            face = Image.open(io.BytesIO(raw)).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            face = None
    initial = face is None
    if initial:
        face = Image.new("RGBA", (size, size), (34, 28, 26, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    face.putalpha(mask)
    img.alpha_composite(face, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    if initial:
        T.text(d, (cx, cy + 2), (name[:1] or "?").upper(), font("Cinzel.ttf", round(r * 1.1), "Bold"), GOLD, "mm")
    d.ellipse(P(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), outline=alpha(ring, 255), width=round(3 * S))


def _seal(img, center, text, color):
    """A round stamp: CONFIRMED (gold) or WAITING (grey)."""
    cx, cy = center
    r = 54
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=alpha(color, 235), width=round(3 * S))
    d.ellipse(P(cx - r + 7, cy - r + 7, cx + r - 7, cy + r - 7), outline=alpha(color, 150), width=max(1, round(1.2 * S)))
    T.text(d, (cx, cy), text, font("Inter.ttf", 14, "Black"), color, "mm")


def _side(img, side, x0, x1, title, avatar, now_state, mine_first=True):
    d = ImageDraw.Draw(img)
    if title:
        T.spaced(d, (x0, 46), title, font("Cinzel.ttf", 22, "Bold"), mix(GOLD, WHITE, 0.2), 2.6)
    _avatar(img, (x0 + 46, 126), 44, avatar, side["name"], GOLD if side["confirmed"] else JADE)
    d = ImageDraw.Draw(img)
    name, nf = _shrink(d, side["name"], "Cinzel.ttf", "Bold", (40, 34, 30), x1 - x0 - 230)
    T.gold_text(img, (x0 + 108, 112), name, nf, "lm")
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 110, 156), side["realm"], font("Inter.ttf", 25, "Medium"), SOFT, "lm")
    if now_state != "cancelled":
        if side["confirmed"]:
            _seal(img, (x1 - 56, 124), "CONFIRMED", GOLD)
        elif now_state == "open" or now_state == "one":
            _seal(img, (x1 - 56, 124), "ADDING", DIM)
    d = ImageDraw.Draw(img)
    d.line(P(x0, 206, x1, 206), fill=(255, 230, 190, 50), width=max(1, round(1.2 * S)))
    rows = side["rows"]
    if not rows:
        T.text(d, (x0, TOP + 8), "No items", font("Inter.ttf", 28, "Medium"), DIM, "lm")
    for i, r in enumerate(rows):
        y = TOP + 8 + i * ROW
        col = T.RARITY.get(r["color_key"], T.RARITY[None])
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
    # currencies, under the items
    y = height_rows(img) - 214
    d.line(P(x0, y - 34, x1, y - 34), fill=(255, 230, 190, 50), width=max(1, round(1.2 * S)))
    for k, (cur, icon, color, label) in enumerate((("lotus_coins", "lotus", LOTUS, "Lotus Coins"),
                                                   ("moon_pearls", "pearl", PEARL, "Moon Pearls"))):
        cy = y + k * 52
        amt = side[cur]
        T.icon(img, icon, (x0 + 24, cy), 38, color if amt else DIM)
        d = ImageDraw.Draw(img)
        T.text(d, (x0 + 62, cy), label, font("Inter.ttf", 27, "SemiBold"), SOFT if amt else DIM, "lm")
        T.text(d, (x1, cy), f"{amt:,}" if amt else "—", font("Cinzel.ttf", 34, "Bold"), color if amt else DIM, "rm")


def height_rows(img):
    return round(img.size[1] / S)


def _shrink(d, s, face, weight, sizes, max_w):
    for size in sizes:
        f = font(face, size, weight)
        if T.width(d, s, f) <= max_w:
            return s, f
    f = font(face, sizes[-1], weight)
    return T.fit(d, s, f, max_w), f


def _divider(img, h):
    d = ImageDraw.Draw(img)
    x = W / 2
    d.line(P(x, 60, x, h - 120), fill=(240, 200, 110, 90), width=max(1, round(1.4 * S)))
    for y in (60, h - 120):
        d.polygon([P(x, y - 8), P(x + 8, y), P(x, y + 8), P(x - 8, y)], fill=alpha(GOLD, 220))
    cy = h / 2 - 50
    T.soft_glow(img, (x - 40, cy - 40, x + 40, cy + 40), alpha(GOLD, 80), 14)
    d = ImageDraw.Draw(img)
    d.ellipse(P(x - 26, cy - 26, x + 26, cy + 26), fill=(16, 14, 14, 255), outline=alpha(GOLD, 255), width=round(2 * S))
    for sgn in (-1, 1):                         # two arrows, one each way
        yy = cy + sgn * 7
        d.line(P(x - 12, yy, x + 12, yy), fill=alpha(GOLD, 255), width=round(2.5 * S))
        tip = x + 12 * sgn
        d.polygon([P(tip, yy), P(tip - 7 * sgn, yy - 6), P(tip - 7 * sgn, yy + 6)], fill=alpha(GOLD, 255))


def _status(img, data, h):
    kind, text = data["status"]
    color = {"complete": JADE, "cancelled": RED, "one": GOLD}.get(kind, SOFT)
    d = ImageDraw.Draw(img)
    d.line(P(36, h - 96, W - 36, h - 96), fill=(255, 230, 190, 46), width=max(1, round(1.2 * S)))
    T.text(d, (W / 2, h - 58), text, font("Inter.ttf", 32, "Bold"), color, "mm")
    if data.get("note"):
        T.text(d, (W / 2, h - 22), T.fit(d, data["note"], font("Inter.ttf", 23, "Medium"), W - 120),
               font("Inter.ttf", 23, "Medium"), (240, 150, 130), "mm")


def _canvas(h):
    img = T.canvas(W, h, seed=41, accent="train")
    shade = Image.new("RGBA", img.size, (6, 6, 8, 120))
    img.alpha_composite(shade)
    return img


def render_trade(data):
    h = height(data)
    img = _canvas(h)
    kind = data["status"][0]
    avatars = data.get("avatars") or {}
    a, b = data["sides"]
    _side(img, a, *COL[0], None, avatars.get(a["uid"]), kind)
    _side(img, b, *COL[1], None, avatars.get(b["uid"]), kind)
    _divider(img, h)
    if kind in ("complete", "cancelled"):
        veil = Image.new("RGBA", img.size, (4, 4, 6, 120 if kind == "complete" else 165))
        img.alpha_composite(veil)
        V.crest(img, (W / 2, h / 2 - 60), 200, "won" if kind == "complete" else "lost")
        T.gold_text(img, (W / 2, h / 2 + 90), "Trade Complete" if kind == "complete" else "Trade Cancelled",
                    font("Cinzel.ttf", 64, "Bold"), "mm",
                    top=(255, 240, 200) if kind == "complete" else (250, 170, 150),
                    bottom=(196, 146, 70) if kind == "complete" else (160, 60, 50))
    _status(img, data, h)
    return T.finish(img)


def render_preview(data):
    """The Trade Preview for one player: what you give (left) and what you receive (right)."""
    viewer = data["viewer"]
    mine = next(s for s in data["sides"] if s["uid"] == viewer)
    theirs = next(s for s in data["sides"] if s["uid"] != viewer)
    h = height(data)
    img = _canvas(h)
    avatars = data.get("avatars") or {}
    _side(img, dict(mine, confirmed=False), *COL[0], "YOU GIVE", avatars.get(mine["uid"]), "preview")
    _side(img, dict(theirs, confirmed=False), *COL[1], "YOU RECEIVE", avatars.get(theirs["uid"]), "preview")
    _divider(img, h)
    _status(img, {"status": ("one", "Check every line. A completed trade can't be undone."), "note": None}, h)
    return T.finish(img)
