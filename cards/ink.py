"""
Night Ink theme: the shared look of the Character Sheet and the Internal Qi card.

Indigo ink backgrounds, gold frames, cloud curls (祥云) and diamond gems. Each card adds its own accent
on top (TAB_ACCENT): indigo for the Profile, gold for the Purse, jade for the Inventory, steel for the
Equipment, violet for the Techniques. Vermilion is kept for HP and seals.

Builds on cards/theme.py (fonts, text, icons, medallions, scaling); nothing here changes theme.py's
colours, so the fight, explore, craft and forge cards keep their own look.
"""
import math

from PIL import Image, ImageDraw

from . import theme as t
from .theme import P, S, alpha, font, mix

# ── Palette ───────────────────────────────────────────────────────────

VOID = (5, 8, 15)
PANEL = (10, 15, 26)
PANEL_HI = (18, 26, 42)
INK = (38, 58, 98)               # faded marks, big background characters
ASH = (152, 164, 184)            # secondary text
ASH_DK = (96, 108, 130)          # hints, empty things
PARCHMENT = (240, 236, 224)      # main text
SKY = (130, 192, 255)            # phase lines, highlights
GOLD, GOLD_HI, BRONZE, BRONZE_DK = t.GOLD, t.GOLD_HI, (152, 122, 74), (56, 48, 38)
VERMILION = (214, 60, 48)
JADE = (82, 210, 170)
AZURE = (70, 170, 236)           # Internal Qi
AZURE_HI = (150, 214, 255)
LOTUS, MOON = t.LOTUS, t.MOON
LACQUER = ((34, 54, 96), (12, 20, 40))

# One accent per card: (background glow, main colour). The main colour lights the active tab, gems and titles.
TAB_ACCENT = {
    "profile": ((20, 36, 70), (110, 160, 240)),
    "purse": ((52, 38, 12), (236, 186, 92)),
    "inventory": ((8, 42, 38), (82, 210, 170)),
    "equipment": ((22, 34, 56), (160, 196, 232)),
    "techniques": ((34, 22, 60), (178, 140, 246)),
}
for _k, (_deep, _main) in TAB_ACCENT.items():
    t.ACCENTS[f"ink_{_k}"] = t.Accent(f"ink_{_k}", _deep, LACQUER, _main, mix(_main, (255, 255, 255), 0.4), INK)
INK_HALL = t.Accent("ink", (20, 36, 70), LACQUER, (110, 160, 240), (170, 205, 255), INK)

# Gear tiers and technique grades as one character each (the tier ribbon on gear, the grade seal on scrolls)
TIER_CHAR = {"ordinary": "凡", "refined": "精", "spirit": "灵", "treasure": "宝", "divine": "神"}
GRADE_CHAR = {"Mortal": "凡", "Yellow": "黄", "Mystic": "玄", "Earth": "地", "Heaven": "天"}


def canvas(w, h, tab, seed=7):
    return t.canvas(w, h, seed=seed, accent=f"ink_{tab}")


def accent(tab):
    return TAB_ACCENT[tab][1]


# ── Ornaments ─────────────────────────────────────────────────────────

def cloud_curl(d, cx, cy, s, color, flip=1, width=2.0, turns=1.6):
    """A 祥云 cloud curl: an inward spiral."""
    pts = []
    n = 60
    for i in range(n + 1):
        th = i / n * turns * 2 * math.pi
        r = s * (1 - i / n * 0.85)
        pts.append(P(cx + flip * r * math.cos(th + math.pi), cy - r * math.sin(th + math.pi)))
    d.line(pts, fill=color, width=round(width * S), joint="curve")


def gem(d, cx, cy, r, color):
    """A small diamond gem in a gold setting."""
    d.polygon([P(cx, cy - r), P(cx + r, cy), P(cx, cy + r), P(cx - r, cy)], fill=BRONZE_DK, outline=GOLD_HI)
    r2 = r * 0.6
    d.polygon([P(cx, cy - r2), P(cx + r2, cy), P(cx, cy + r2), P(cx - r2, cy)], fill=color)
    d.polygon([P(cx, cy - r2), P(cx + r2 * 0.2, cy - r2 * 0.2), P(cx - r2 * 0.4, cy)], fill=(255, 255, 255, 120))


def octagon(box, c):
    x0, y0, x1, y1 = box
    return [P(x0 + c, y0), P(x1 - c, y0), P(x1, y0 + c), P(x1, y1 - c), P(x1 - c, y1), P(x0 + c, y1), P(x0, y1 - c),
            P(x0, y0 + c)]


def plaque(img, box, title=None, color=VERMILION, fill=PANEL, cut=12, tint=None):
    """A panel with cut corners and, optionally, a lacquer title tab with gems and cloud curls at its ends."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    shape = octagon(box, cut)
    ld.polygon(shape, fill=alpha(fill, 236))
    if tint:
        ld.rectangle(P(x0 + 4, y0 + 4, x1 - 4, y0 + 30), fill=alpha(tint, 40))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.line(shape + [shape[0]], fill=BRONZE, width=round(2 * S), joint="curve")
    inner = octagon((x0 + 5, y0 + 5, x1 - 5, y1 - 5), cut - 1)
    d.line(inner + [inner[0]], fill=alpha(GOLD, 70), width=max(1, S // 2))
    for cx, cy in ((x0 + cut / 2, y0 + cut / 2), (x1 - cut / 2, y0 + cut / 2), (x0 + cut / 2, y1 - cut / 2),
                   (x1 - cut / 2, y1 - cut / 2)):
        t.stud(d, cx, cy, 3.5)
    if title:
        title_tab(img, ((x0 + x1) / 2, y0), title, color)


def title_tab(img, center, title, color=VERMILION, size=15):
    mx, y0 = center
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", size, "Bold")
    tw = sum(t.width(d, ch, f) for ch in title.upper()) + 2.4 * (len(title) - 1) + 44
    t.banner(img, (mx - tw / 2, y0 - 13, mx + tw / 2, y0 + 13), INK_HALL)
    d = ImageDraw.Draw(img)
    for side in (-1, 1):
        ex = mx + side * (tw / 2 + 2)
        gem(d, ex, y0, 5, color)
        cloud_curl(d, ex + side * 16, y0 - 1, 7, GOLD, flip=side, width=1.6)
    t.spaced(d, (mx, y0 + 0.5), title.upper(), f, GOLD_HI, 2.4, "m")


def tab_strip(img, active, y=0, h=46):
    """The sheet's tab bar in ink lacquer; the active tab glows in its card's accent."""
    w = img.size[0] / S
    t.banner(img, (0, y, w, y + h), INK_HALL)
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 15, "Bold")
    seg = (w - 80) / len(t.TABS)
    for i, (key, label) in enumerate(t.TABS):
        cx = 40 + seg * (i + 0.5)
        if key == active:
            t.soft_glow(img, (cx - seg * 0.42, y + 6, cx + seg * 0.42, y + h - 6), alpha(accent(key), 130), 10)
            d = ImageDraw.Draw(img)
            t.spaced(d, (cx, y + h / 2), label.upper(), f, GOLD_HI, 2.5, "m")
            d.line(P(cx - 34, y + h - 7, cx + 34, y + h - 7), fill=GOLD, width=round(1.5 * S))
            gem(d, cx, y + h - 7, 3.5, accent(key))
        else:
            t.spaced(d, (cx, y + h / 2), label.upper(), f, ASH, 2.5, "m")
        if i:
            t.stud(d, 40 + seg * i, y + h / 2, 3.5)


def sheet_frame(img, tab):
    """Tab strip and outer frame shared by every sheet card."""
    tab_strip(img, tab)
    w, h = img.size[0] / S, img.size[1] / S
    t.frame(img, (6, 52, w - 6, h - 6), corners=True)


def title(img, xy, text, color, sub=None, size=34):
    """The card's title in gold with a glow in the card's accent, and an optional short line under it."""
    x, y = xy
    t.gold_text(img, (x, y), text.upper(), font("Cinzel.ttf", size, "Black"), glow=mix(color, (0, 0, 0), 0.55))
    if sub:
        d = ImageDraw.Draw(img)
        t.text(d, (x + 2, y + size + 22), sub, font("Inter.ttf", 14, "Medium"), ASH)


def chip(img, xy, text, color, size=11, anchor="l", fill=None):
    """A small rounded tag. Returns its width."""
    x, y = xy
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", size, "Bold")
    w = t.width(d, text, f) + 14
    h = size + 9
    if anchor == "r":
        x -= w
    elif anchor == "m":
        x -= w / 2
    d.rounded_rectangle(P(x, y - h / 2, x + w, y + h / 2), radius=round(h / 2 * S),
                        fill=alpha(fill or mix(color, (0, 0, 0), 0.7), 255), outline=alpha(color, 230),
                        width=max(1, S // 2))
    t.text(d, (x + w / 2, y + 0.5), text, f, mix(color, (255, 255, 255), 0.45), "mm", shadow=False)
    return w


def ribbon(img, box, text, color):
    """A small corner ribbon (EQUIPPED, LEARNED) with a notched end."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    h = y1 - y0
    d.polygon([P(x0, y0), P(x1, y0), P(x1 - h * 0.35, (y0 + y1) / 2), P(x1, y1), P(x0, y1)],
              fill=alpha(mix(color, (0, 0, 0), 0.35), 255), outline=alpha(GOLD, 230))
    t.text(d, ((x0 + x1 - h * 0.35) / 2, (y0 + y1) / 2 + 0.5), text, font("Cinzel.ttf", round(h * 0.55), "Bold"),
           GOLD_HI, "mm", shadow=False)


def heading(img, xy, text, x_end, color=GOLD):
    """Small spaced section title, a fading rule and a gem."""
    x, y = xy
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 13, "Bold")
    t.spaced(d, (x, y), text.upper(), f, color, 2.2)
    tw = sum(t.width(d, ch, f) for ch in text.upper()) + 2.2 * (len(text) - 1)
    steps = 20
    x0 = x + tw + 12
    for i in range(steps):
        a0, a1 = i / steps, (i + 1) / steps
        d.line(P(x0 + (x_end - 8 - x0) * a0, y, x0 + (x_end - 8 - x0) * a1, y),
               fill=alpha(GOLD, round(200 - 150 * a0)), width=max(1, S))
    gem(d, x_end - 4, y, 3.5, color)


def page_dots(img, center, page, pages, color):
    """Page n of m as a row of beads (with the numbers when there are many pages)."""
    cx, cy = center
    d = ImageDraw.Draw(img)
    if pages > 9:
        t.text(d, (cx, cy), f"Page {page} of {pages}", font("Cinzel.ttf", 13, "Bold"), GOLD, "mm")
        return
    gap = 16
    x0 = cx - (pages - 1) * gap / 2
    for i in range(pages):
        x = x0 + i * gap
        if i + 1 == page:
            t.soft_glow(img, (x - 8, cy - 8, x + 8, cy + 8), alpha(color, 200), 3)
            d = ImageDraw.Draw(img)
            gem(d, x, cy, 6, color)
        else:
            d.ellipse(P(x - 3, cy - 3, x + 3, cy + 3), fill=BRONZE_DK, outline=BRONZE)


def ornate_bar(img, box, frac, color, cap_icon, label, tag=None):
    """Bronze-housed bar: a medallion cap on the left, cloud curls and a gem on the right,
    a glossy fill with 10% ticks and a centre gem on top."""
    x0, y0, x1, y1 = box
    h = y1 - y0
    mid = (y0 + y1) / 2
    frac = max(0.0, min(1.0, frac))
    t.soft_glow(img, (x0, y0 - 6, x0 + (x1 - x0) * frac, y1 + 6), alpha(color, 70), 10, "rect")
    d = ImageDraw.Draw(img)
    hx0, hx1 = x0 - 6, x1 + 22
    hous = [P(hx0, y0 - 7), P(hx1 - 10, y0 - 7), P(hx1, mid), P(hx1 - 10, y1 + 7), P(hx0, y1 + 7)]
    d.polygon(hous, fill=(16, 20, 30, 255))
    d.line(hous + [hous[0]], fill=GOLD, width=round(1.8 * S), joint="curve")
    inner = [P(hx0 + 3, y0 - 4), P(hx1 - 11.5, y0 - 4), P(hx1 - 4, mid), P(hx1 - 11.5, y1 + 4), P(hx0 + 3, y1 + 4)]
    d.line(inner + [inner[0]], fill=alpha(BRONZE, 200), width=max(1, S))
    d.rectangle(P(x0, y0, x1, y1), fill=(6, 4, 4, 255))
    if frac > 0:
        fx = x0 + (x1 - x0) * frac
        g = t.vgradient((max(1, round((fx - x0) * S)), round(h * S)), mix(color, (255, 244, 230), 0.45),
                        mix(color, (0, 0, 0), 0.55), 0, round(h * S))
        st = Image.new("RGBA", g.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        for sx in range(-round(h * S), g.size[0], round(34 * S)):
            sd.polygon([(sx, g.size[1]), (sx + round(8 * S), g.size[1]), (sx + round(8 * S) + g.size[1], 0),
                        (sx + g.size[1], 0)], fill=(255, 255, 255, 22))
        g.alpha_composite(st)
        img.alpha_composite(g, P(x0, y0))
        d = ImageDraw.Draw(img)
        d.line(P(x0, y0 + 2.5, fx, y0 + 2.5), fill=(255, 255, 255, 90), width=max(1, S))
        d.line(P(fx, y0, fx, y1), fill=alpha(mix(color, (255, 255, 255), 0.7), 230), width=round(1.5 * S))
    for i in range(1, 10):
        tx = x0 + (x1 - x0) * i / 10
        d.line(P(tx, y1 - (5 if i != 5 else 8), tx, y1), fill=(0, 0, 0, 150), width=max(1, S))
    d.rectangle(P(x0, y0, x1, y1), outline=alpha(GOLD, 160), width=max(1, S))
    cloud_curl(d, hx1 + 12, mid - 6, 9, GOLD, flip=-1, width=2)
    cloud_curl(d, hx1 + 12, mid + 7, 6, alpha(BRONZE, 255), flip=-1, width=1.6)
    gem(d, hx1 + 2, mid, 6, color)
    gem(d, (x0 + x1) / 2, y0 - 7, 6, color)
    t.medallion(img, (x0 - 14, mid), h * 0.5 + 12, cap_icon, color, cjk_char=False)
    d = ImageDraw.Draw(img)
    if label:
        t.text(d, ((x0 + x1) / 2, mid + 0.5), label, font("Inter.ttf", round(h * 0.56), "Bold"), (255, 248, 236), "mm")
    if tag:
        t.spaced(d, (x0 + 14, mid), tag, font("Cinzel.ttf", round(h * 0.42), "Bold"), alpha((255, 240, 220), 200), 1.4)


def slim_bar(img, box, frac, color, label=None):
    """A thin glowing groove (mastery, blessing days, bag space)."""
    x0, y0, x1, y1 = box
    frac = max(0.0, min(1.0, frac))
    d = ImageDraw.Draw(img)
    r = (y1 - y0) / 2
    d.rounded_rectangle(P(x0 - 1.5, y0 - 1.5, x1 + 1.5, y1 + 1.5), radius=round((r + 1.5) * S), fill=(3, 5, 10, 255),
                        outline=alpha(BRONZE, 200), width=max(1, S))
    if frac > 0:
        fx = x0 + (x1 - x0) * frac
        g = t.vgradient((max(1, round((fx - x0) * S)), max(1, round((y1 - y0) * S))), mix(color, (255, 255, 255), 0.4),
                        mix(color, (0, 0, 0), 0.4))
        m = Image.new("L", g.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, g.size[0] - 1, g.size[1] - 1), radius=round(r * S), fill=255)
        g.putalpha(m)
        img.alpha_composite(g, P(x0, y0))
    if label:
        d = ImageDraw.Draw(img)
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 0.5), label, font("Inter.ttf", max(9, round((y1 - y0) * 0.66)), "Bold"),
               PARCHMENT, "mm")


def big_glyph(img, center, glyph, size, color, a=60):
    """A large faint character behind a panel (blended on its own layer so it stays faint)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    t.text(ImageDraw.Draw(layer), center, glyph, t.cjk(size), alpha(color, a), "mm", shadow=False)
    img.alpha_composite(layer)
