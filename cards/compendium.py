"""
/index: one page of the Jianghu Compendium (Crimson Hall theme).

  ┌ header: tier seal medallion, section name, tier · where it starts, "Jianghu Compendium 万物录"
  ├ tier strip: every tier of the section, the current one lit in its colour
  ├ intro line
  ├ grid of item tiles (2 or 3 columns): seal / icon, name, badge, 1-3 short lines
  └ footer plate: where to find this tier

render_compendium(page) takes the plain dict from bot.compendium.tier_page. Discord shows cards at
under half size, so nothing is drawn under 20px.
"""
from PIL import ImageDraw

from . import theme as T
from .theme import P, alpha, cjk, font, mix

W = T.W
PAD = 30
GAP = 16
STRIP = (PAD, 136, W - PAD, 200)
NAME_F = ("Inter.ttf", 26, "Bold")
LINE_F = ("Inter.ttf", 22, "Medium")
LINE_H = 29
NAME_H = 31
MED_R = 38
INTRO_F = ("Inter.ttf", 22, "Medium")


def _f(spec):
    return font(*spec)


def render_compendium(p):
    tiles = p["tiles"]
    cols = 3 if len(tiles) > 4 else 2
    tw = (W - 2 * PAD - (cols - 1) * GAP) / cols
    probe = ImageDraw.Draw(T.canvas(W, 200))
    layouts = [_layout(probe, t, tw) for t in tiles]
    th = max([l["h"] for l in layouts] or [120])
    rows = max(1, -(-len(tiles) // cols))
    d0 = ImageDraw.Draw(T.canvas(W, 200))
    intro = T.wrap(d0, p["intro"], _f(INTRO_F), W - 2 * PAD - 20, lines=2) if p.get("intro") else []
    grid_y = STRIP[3] + 22 + 30 * len(intro) + (10 if intro else 0)
    footer_lines = T.wrap(d0, p["footer"], _f(("Inter.ttf", 22, "SemiBold")), W - 2 * PAD - 60, lines=3)
    footer_h = 30 + 30 * len(footer_lines)
    grid_y1 = grid_y + rows * th + (rows - 1) * GAP
    H = round(grid_y1 + 24 + footer_h + 24)

    img = T.canvas(W, H, seed=11)
    T.frame(img, (6, 6, W - 6, H - 6))
    _header(img, p)
    _strip(img, p)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(intro):
        T.text(d, (W / 2, STRIP[3] + 32 + 30 * i), line, _f(INTRO_F), T.ASH, "mm")
    for i, (t, lay) in enumerate(zip(tiles, layouts)):
        r, c = divmod(i, cols)
        in_row = min(cols, len(tiles) - r * cols)
        x = PAD + (cols - in_row) * (tw + GAP) / 2 + c * (tw + GAP)     # centre a short last row
        y = grid_y + r * (th + GAP)
        _tile(img, (x, y, x + tw, y + th), t, lay)
    if not tiles:
        T.text(d, (W / 2, grid_y + 60), "Nothing here yet.", _f(LINE_F), T.ASH, "mm")
    _footer(img, (PAD, grid_y1 + 24, W - PAD, grid_y1 + 24 + footer_h), footer_lines)
    return T.finish(img)


# ── header and strip ──────────────────────────────────────────────────

def _header(img, p):
    color = p["color"]
    T.medallion(img, (PAD + 62, 70), 50, p["seal"], color)
    T.gold_text(img, (PAD + 132, 26), p["section_label"].upper(), font("Cinzel.ttf", 46, "Black"), glow=T.EMBER)
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    tier = p["tier_label"].upper() + (" TIER" if p.get("tier_word", True) else "")
    T.spaced(d, (PAD + 134, 104), tier, f, mix(color, (255, 255, 255), 0.2), 1.6)
    tx = PAD + 134 + sum(T.width(d, ch, f) + 1.6 for ch in tier) + 10
    sub = p.get("subtitle") or ""
    if sub:
        sf = font("Inter.ttf", 24, "SemiBold")
        T.text(d, (tx, 104), T.fit(d, "·  " + sub, sf, W - PAD - 250 - tx), sf, T.PARCHMENT, "lm")
    # right corner: the book's name, and the page when a tier spans several
    T.spaced(d, (W - PAD - 10, 40), "JIANGHU COMPENDIUM", font("Cinzel.ttf", 20, "Bold"), T.GOLD, 1.8, "r")
    T.text(d, (W - PAD - 10, 76), "万物录", cjk(30), alpha(T.GOLD_HI, 255), "rm")
    if p.get("pages", 1) > 1:
        T.text(d, (W - PAD - 10, 108), f"Page {p['page']} / {p['pages']}", font("Inter.ttf", 22, "Bold"),
               T.GOLD_HI, "rm")


def _strip(img, p):
    x0, y0, x1, y1 = STRIP
    T.banner(img, STRIP)
    strip = p["strip"]
    n = len(strip)
    d = ImageDraw.Draw(img)
    lf = font("Cinzel.ttf", 20, "Bold")
    seal_f = cjk(28)
    compact = n > 6                       # beasts: 11 realms, so only the current one shows its name
    if compact and not any(s[0] == p["tier"] for s in strip):
        active_w = other_w = (x1 - x0) / n     # Overview: no realm is lit, all seals share the strip
    elif compact:
        active_w = 34 + 14 + max(T.width(d, s[2].upper(), lf) for s in strip) + 36
        other_w = (x1 - x0 - active_w) / (n - 1)
    if compact:
        widths = [active_w if s[0] == p["tier"] else other_w for s in strip]
    else:                                 # each tier as wide as its label needs, spare room shared equally
        need = [30 + 10 + T.width(d, s[2].upper(), lf) + 24 for s in strip]
        spare = max(0, (x1 - x0) - sum(need)) / n
        widths = [w + spare for w in need]
    x = x0
    cy = (y0 + y1) / 2
    for i, ((key, seal, label, color), w) in enumerate(zip(strip, widths)):
        active = key == p["tier"]
        if active:
            T.soft_glow(img, (x + 8, y0 + 6, x + w - 8, y1 - 6), alpha(color, 150), 10)
            d = ImageDraw.Draw(img)
            d.rectangle(P(x + 3, y0 + 4, x + w - 3, y1 - 4), outline=alpha(mix(color, (255, 255, 255), 0.3), 255),
                        width=round(2 * T.S))
        seal_c = mix(color, (255, 255, 255), 0.25) if active else mix(color, (0, 0, 0), 0.35)
        lab_c = T.GOLD_HI if active else alpha(T.ASH, 255)
        if compact and not active:
            T.text(d, (x + w / 2, cy + 1), seal, seal_f, seal_c, "mm")
        else:
            lw = T.width(d, label.upper(), lf)
            gx = x + (w - (30 + 10 + lw)) / 2
            T.text(d, (gx + 15, cy + 1), seal, seal_f, seal_c, "mm")
            T.text(d, (gx + 40, cy), label.upper(), lf, lab_c, "lm")
        if i:
            T.stud(d, x, cy, 3.5)
        x += w


# ── tiles ─────────────────────────────────────────────────────────────

def _layout(d, t, tw):
    text_w = tw - 2 * MED_R - 44
    name = T.wrap(d, t["name"], _f(NAME_F), text_w, lines=3)
    top = len(name) * NAME_H + (36 if t.get("badge") else 0)
    lines = []           # (text, is the tile's last line: drawn in gold)
    for i, line in enumerate(t["lines"]):
        last = i == len(t["lines"]) - 1 and len(t["lines"]) > 1
        lines += [(part, last) for part in T.wrap(d, line, _f(LINE_F), tw - 32, lines=4)]
    top_h = max(2 * MED_R + 8, top)
    return {"name": name, "lines": lines, "top": top_h, "h": 18 + top_h + 12 + len(lines) * LINE_H + 14}


def _tile(img, box, t, lay):
    x0, y0, x1, y1 = box
    color = t["color"]
    if t.get("found"):                    # the item /index search jumped to
        T.soft_glow(img, (x0 - 4, y0 - 4, x1 + 4, y1 + 4), alpha(T.GOLD, 190), 9, "rect")
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), fill=(12, 7, 8, 240), outline=T.BRONZE_DK, width=round(3 * T.S))
    d.rectangle(P(x0 + 2, y0 + 2, x1 - 2, y1 - 2), outline=alpha(color, 200), width=round(1.5 * T.S))
    if t.get("found"):
        d.rectangle(P(x0 - 1, y0 - 1, x1 + 1, y1 + 1), outline=T.GOLD_HI, width=round(3 * T.S))
    T.soft_glow(img, (x0 + 6, y0 + 6, x1 - 6, y0 + 40), alpha(color, 34), 8, "rect")
    mx, my = x0 + 16 + MED_R, y0 + 18 + MED_R
    T.medallion(img, (mx, my), MED_R, t["glyph"], color, cjk_char=t.get("cjk", True))
    d = ImageDraw.Draw(img)
    tx = mx + MED_R + 14
    block = len(lay["name"]) * NAME_H + (36 if t.get("badge") else 0)
    ny = y0 + 18 + (lay["top"] - block) / 2 + NAME_H / 2
    for line in lay["name"]:
        T.text(d, (tx, ny), line, _f(NAME_F), T.PARCHMENT, "lm")
        ny += NAME_H
    if t.get("badge"):
        label, bc = t["badge"]
        bf = font("Cinzel.ttf", 20, "Bold")
        bw = T.width(d, label.upper(), bf) + 20
        d.rectangle(P(tx, ny - 8, tx + bw, ny + 22), fill=alpha(mix(bc, (0, 0, 0), 0.6), 255), outline=bc,
                    width=max(1, T.S))
        T.text(d, (tx + bw / 2, ny + 7), label.upper(), bf, mix(bc, (255, 255, 255), 0.3), "mm")
    ly = y0 + 18 + lay["top"] + 12
    T.rule(d, x0 + 16, x1 - 16, ly - 6, alpha(color, 160))
    for i, (line, gold) in enumerate(lay["lines"]):
        T.text(d, (x0 + 16, ly + LINE_H / 2 + i * LINE_H), line, _f(LINE_F), T.GOLD_HI if gold else T.PARCHMENT, "lm")


def _footer(img, box, lines):
    x0, y0, x1, y1 = box
    T.banner(img, box)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 22, "SemiBold")
    y = (y0 + y1) / 2 - (len(lines) - 1) * 15
    for line in lines:
        mixed(d, ((x0 + x1) / 2, y), line, f, cjk(24), T.GOLD_HI)
        y += 30


def _is_cjk(ch):
    return "\u3400" <= ch <= "\u9fff"


def mixed(d, xy, s, f, cf, fill):
    """Centred text where Chinese characters (chest seals) use the CJK font, since Inter has none."""
    runs = []
    for ch in s:
        face = cf if _is_cjk(ch) else f
        if runs and runs[-1][1] is face:
            runs[-1][0] += ch
        else:
            runs.append([ch, face])
    total = sum(T.width(d, r, face) for r, face in runs)
    x = xy[0] - total / 2
    for r, face in runs:
        T.text(d, (x, xy[1]), r, face, fill, "lm")
        x += T.width(d, r, face)
