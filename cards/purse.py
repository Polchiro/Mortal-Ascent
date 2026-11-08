"""
Character Sheet · Purse tab ("Treasury", Night Ink theme with a gold accent: cards/ink.py).

render_purse(data) draws bot.sheet.data.purse_data:
one vault per live currency (economy.md keeps the later ones hidden): Lotus Coins as an ancient square-holed
coin, Moon Pearls as a pearl on a crescent moon, each with the short and the exact amount. Only the currencies
are drawn; the blessing and the ledger stay in the data (the blessing has /blessing).
"""
import math

from PIL import Image, ImageDraw, ImageFilter

from . import ink as k
from . import theme as t
from .theme import P, S, alpha, font, mix, short

W, H = 1200, 370
GOLD_ACC = k.accent("purse")
COIN_GLYPHS = "莲花通宝"           # read top, bottom, right, left on the coin, like a real cash coin


# ── Currency art ──────────────────────────────────────────────────────

def lotus_coin(img, center, r):
    """An ancient round coin with a square hole: gold, beaded rim, four characters and a lotus glow."""
    cx, cy = center
    t.soft_glow(img, (cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18), alpha(GOLD_ACC, 140), 18)
    side = round(2 * r * S)
    coin = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    grad = Image.radial_gradient("L").resize((side, side))
    body = Image.composite(Image.new("RGBA", (side, side), (120, 78, 24, 255)),
                           Image.new("RGBA", (side, side), (250, 214, 130, 255)), grad)
    # light from the top-left
    sheen = Image.linear_gradient("L").rotate(-45, expand=False).resize((side, side))
    dark = Image.new("RGBA", (side, side), (70, 40, 10, 255))
    dark.putalpha(sheen.point(lambda v: round(v * 0.45)))
    body.alpha_composite(dark)
    m = Image.new("L", (side, side), 0)
    md = ImageDraw.Draw(m)
    md.ellipse((0, 0, side - 1, side - 1), fill=255)
    hole = r * 0.32 * S
    md.rectangle((side / 2 - hole, side / 2 - hole, side / 2 + hole, side / 2 + hole), fill=0)
    body.putalpha(m)
    coin.alpha_composite(body)
    img.alpha_composite(coin, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    # rims
    for rr, col, w in ((r, (90, 56, 16), 2.2), (r - 5, (255, 236, 180), 1.2), (r - 11, (150, 100, 34), 1.4)):
        d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), outline=col, width=round(w * S))
    for i in range(40):
        a = math.radians(i * 9)
        bx, by = cx + (r - 8) * math.cos(a), cy + (r - 8) * math.sin(a)
        d.ellipse(P(bx - 1.1, by - 1.1, bx + 1.1, by + 1.1), fill=(255, 230, 170, 220))
    h = r * 0.32
    for off, col in ((3, (150, 100, 34)), (0, (255, 236, 180))):
        d.rectangle(P(cx - h - off, cy - h - off, cx + h + off, cy + h + off), outline=col, width=round(1.4 * S))
    # four characters
    f = t.cjk(round(r * 0.36))
    pos = ((0, -1), (0, 1), (1, 0), (-1, 0))
    for ch, (dx, dy) in zip(COIN_GLYPHS, pos):
        x, y = cx + dx * r * 0.63, cy + dy * r * 0.63
        t.text(d, (x + 1, y + 1.5), ch, f, (110, 66, 18), "mm", shadow=False)
        t.text(d, (x, y), ch, f, (255, 240, 200), "mm", shadow=False)
    # sparkle
    sp = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sp)
    sx, sy = cx - r * 0.5, cy - r * 0.62
    for a, l in ((0, 14), (90, 14), (45, 6), (135, 6)):
        dx, dy = math.cos(math.radians(a)) * l, math.sin(math.radians(a)) * l
        sd.line(P(sx - dx, sy - dy, sx + dx, sy + dy), fill=(255, 255, 240, 230), width=round(1.6 * S))
    img.alpha_composite(sp.filter(ImageFilter.GaussianBlur(0.6 * S)))


def moon_pearl(img, center, r):
    """A luminous pearl resting in a silver crescent moon."""
    cx, cy = center
    t.soft_glow(img, (cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20), alpha(k.MOON, 150), 20)
    d = ImageDraw.Draw(img)
    # crescent: a silver disc minus an offset disc
    side = round(2 * r * S)
    cres = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    m = Image.new("L", (side, side), 0)
    md = ImageDraw.Draw(m)
    md.ellipse((0, 0, side - 1, side - 1), fill=255)
    md.ellipse((side * 0.0, -side * 0.28, side * 1.0, side * 0.72), fill=0)
    silver = t.vgradient((side, side), (150, 168, 196), (236, 242, 252))
    silver.putalpha(m)
    cres.alpha_composite(silver)
    img.alpha_composite(cres, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    # pearl
    pr = r * 0.52
    pcx, pcy = cx, cy - r * 0.08
    ps = round(2 * pr * S)
    g = Image.radial_gradient("L").resize((ps, ps))
    pearl = Image.composite(Image.new("RGBA", (ps, ps), (120, 146, 196, 255)),
                            Image.new("RGBA", (ps, ps), (252, 252, 255, 255)), g.point(lambda v: min(255, v * 1.2)))
    pm = Image.new("L", (ps, ps), 0)
    ImageDraw.Draw(pm).ellipse((0, 0, ps - 1, ps - 1), fill=255)
    pearl.putalpha(pm)
    img.alpha_composite(pearl, P(pcx - pr, pcy - pr))
    d = ImageDraw.Draw(img)
    d.ellipse(P(pcx - pr * 0.55, pcy - pr * 0.62, pcx - pr * 0.05, pcy - pr * 0.22), fill=(255, 255, 255, 170))
    d.ellipse(P(pcx - pr, pcy - pr, pcx + pr, pcy + pr), outline=(220, 230, 250, 200), width=max(1, S))
    for a, rr in ((-40, 1.25), (200, 1.15), (110, 1.35)):
        x, y = pcx + pr * rr * math.cos(math.radians(a)), pcy + pr * rr * math.sin(math.radians(a))
        d.ellipse(P(x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=(235, 244, 255, 220))


ART = {"lotus_coins": lotus_coin, "moon_pearls": moon_pearl}


# ── Panels ────────────────────────────────────────────────────────────

def vault(img, box, c):
    x0, y0, x1, y1 = box
    color = c["color"]
    k.plaque(img, box, fill=mix(color, k.PANEL, 0.9), cut=16)
    cy = (y0 + y1) / 2
    art = ART.get(c["key"])
    if art:
        art(img, (x0 + 118, cy), 74)
    else:
        t.medallion(img, (x0 + 118, cy), 60, c["icon"], color, cjk_char=False)
    d = ImageDraw.Draw(img)
    tx = x0 + 226
    t.spaced(d, (tx, y0 + 46), c["name"].upper(), font("Cinzel.ttf", 15, "Bold"), k.GOLD, 2.6)
    k.chip(img, (x1 - 24, y0 + 46), c["note"].split("·")[0].strip(), color, anchor="r")
    d = ImageDraw.Draw(img)
    f_big = font("Cinzel.ttf", 58, "Black")
    amount = short(c["amount"])
    t.soft_glow(img, (tx, cy - 22, tx + t.width(d, amount, f_big), cy + 30), alpha(color, 50), 14)
    d = ImageDraw.Draw(img)
    t.text(d, (tx - 2, cy + 6), amount, f_big, mix(color, (255, 255, 255), 0.25), "lm")
    d.line(P(tx, cy + 46, x1 - 30, cy + 46), fill=alpha(k.GOLD, 90), width=max(1, S))
    k.gem(d, tx, cy + 46, 3.5, color)
    if amount != f"{c['amount']:,}":           # the exact amount, when the short one rounds it
        t.text(d, (tx + 12, cy + 68), f"{c['amount']:,}", font("Inter.ttf", 18, "SemiBold"), k.PARCHMENT, "lm")


def render_purse(data):
    img = k.canvas(W, H, "purse", seed=11)
    k.sheet_frame(img, "purse")
    k.title(img, (40, 66), f"{data['name']}'s Treasury", GOLD_ACC)
    cur = data["currencies"]
    n = max(1, len(cur))
    gap = 20
    w = (1140 - gap * (n - 1)) / n
    for i, c in enumerate(cur):
        x = 30 + i * (w + gap)
        vault(img, (x, 136, x + w, 336), c)
    return t.finish(img)
