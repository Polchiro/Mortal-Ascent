"""
/index: one page of the Jianghu Compendium, on a night sky with frosted-glass tiles.

  ┌ header: tier seal, section name, tier · where it starts, 万物录 (and the page when there are several)
  ├ tier strip: every tier of the section, the current one lit in its colour
  ├ intro line (short)
  ├ tiles in 2 or 3 columns, grouped under small headings when the tiles carry a group
  │   (painted icon, name, badge, 1-3 short lines; the last line in gold)
  └ footer bar: where to find this tier

render_compendium(page) takes the plain dict from bot.compendium.tier_page. Discord shows cards at
under half size, so body text is 26 px and nothing is under 22 px.
"""
from PIL import Image, ImageDraw

from . import art_icons
from . import theme as T
from .theme import P, S, alpha, cjk, font, mix

W = T.W
PAD = 28
GAP = 16
STRIP = (PAD, 142, W - PAD, 212)
NAME_F = ("Inter.ttf", 31, "Bold")
LINE_F = ("Inter.ttf", 26, "SemiBold")
LINE_H = 34
NAME_H = 36
MED_R = 44
INTRO_F = ("Inter.ttf", 25, "Medium")
FOOT_F = ("Inter.ttf", 25, "SemiBold")
GROUP_H = 50
TEXT = (238, 241, 248)
SOFT = (196, 205, 224)
GOLD_LINE = (244, 214, 148)
GLASS = (20, 28, 52, 178)
EDGE = (198, 164, 98)


def _f(spec):
    return font(*spec)


def _sky(h):
    """The night sky, cut from one tall cached sheet so every page height reuses it."""
    from .battle import _galaxy
    tall = _galaxy(W, 1800, seed=33)
    return tall.crop((0, 0, tall.size[0], min(tall.size[1], round(h * S)))) if h <= 1800 else _galaxy(W, h, 33).copy()


def _glass(img, box, edge=EDGE, a=178, r=14, width=1.6):
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(P(x0, y0, x1, y1), radius=r * S, fill=GLASS[:3] + (a,))
    img.alpha_composite(layer)
    ImageDraw.Draw(img).rounded_rectangle(P(x0, y0, x1, y1), radius=r * S, outline=alpha(edge, 200),
                                          width=round(width * S))


def _rows(tiles, cols):
    """[(heading or None, [tiles of one row], columns)]. Tiles with a group get a heading where the group
    starts; a group of 2 or 4 is laid out two to a row so it stays balanced."""
    groups = []
    grouped = any(t.get("group") for t in tiles)
    for t in tiles:
        g = t.get("group") if grouped else None
        if groups and groups[-1][0] == g:
            groups[-1][1].append(t)
        else:
            groups.append((g, [t]))
    out = []
    for g, items in groups:
        k = 2 if grouped and cols == 3 and len(items) in (2, 4) else cols
        for n in range(0, len(items), k):
            out.append((g if n == 0 else None, items[n:n + k], k))
    return out


def render_compendium(p):
    tiles = p["tiles"]
    cols = 3 if len(tiles) > 4 else 2
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    rows = _rows(tiles, cols)
    width = {k: (W - 2 * PAD - (k - 1) * GAP) / k for k in (2, 3)}
    lay = {id(t): _layout(probe, t, width[k]) for _, row, k in rows for t in row}
    intro = T.wrap(probe, p["intro"], _f(INTRO_F), W - 2 * PAD - 20, lines=2) if p.get("intro") else []
    y = STRIP[3] + 16 + (34 * len(intro) + 8 if intro else 0)
    plan = []
    for group, row, k in rows:
        if group:
            plan.append(("group", group, y))
            y += GROUP_H
        h = max(lay[id(t)]["h"] for t in row)
        plan.append(("row", row, y, h, k))
        y += h + GAP
    grid_y1 = y - GAP
    footer_lines = T.wrap(probe, p["footer"], _f(FOOT_F), W - 2 * PAD - 60, lines=3) if p.get("footer") else []
    footer_h = 26 + 34 * len(footer_lines)
    H = round(grid_y1 + 20 + (footer_h + 20 if footer_lines else 0) + 8)

    img = _sky(H)
    _header(img, p)
    _strip(img, p)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(intro):
        T.text(d, (W / 2, STRIP[3] + 32 + 34 * i), line, _f(INTRO_F), SOFT, "mm")
    for item in plan:
        if item[0] == "group":
            _group(img, item[1], item[2])
            continue
        _, row, ry, rh, k = item
        n, tw = len(row), width[k]
        for c, t in enumerate(row):
            x = PAD + (k - n) * (tw + GAP) / 2 + c * (tw + GAP)          # centre a short row
            _tile(img, (x, ry, x + tw, ry + rh), t, lay[id(t)])
    if not tiles:
        T.text(ImageDraw.Draw(img), (W / 2, STRIP[3] + 80), "Nothing here yet.", _f(LINE_F), SOFT, "mm")
    if footer_lines:
        _footer(img, (PAD, grid_y1 + 20, W - PAD, grid_y1 + 20 + footer_h), footer_lines)
    ImageDraw.Draw(img).rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(EDGE, 220),
                                          width=round(2 * S))
    return T.finish(img)


def _group(img, label, y):
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 26, "Bold")
    cy = y + GROUP_H / 2 - 4
    tw = T.width(d, label.upper(), f)
    T.gold_text(img, (W / 2, cy), label.upper(), f, "mm")
    d = ImageDraw.Draw(img)
    for x0, x1 in ((PAD + 20, W / 2 - tw / 2 - 20), (W / 2 + tw / 2 + 20, W - PAD - 20)):
        d.line(P(x0, cy, x1, cy), fill=alpha(EDGE, 120), width=max(1, S))


# ── header and strip ──────────────────────────────────────────────────

def _header(img, p):
    color = p["color"]
    T.soft_glow(img, (PAD + 4, 14, PAD + 124, 134), alpha(color, 90), 18)
    seal(img, (PAD + 64, 74), 54, p["seal"], color)
    T.gold_text(img, (PAD + 140, 20), p["section_label"].upper(), font("Cinzel.ttf", 52, "Black"),
                glow=alpha(T.GOLD, 90))
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 25, "Bold")
    tier = p["tier_label"].upper() + (" TIER" if p.get("tier_word", True) else "")
    T.spaced(d, (PAD + 142, 110), tier, f, mix(color, (255, 255, 255), 0.35), 1.6)
    tx = PAD + 142 + sum(T.width(d, ch, f) + 1.6 for ch in tier) + 12
    sub = p.get("subtitle") or ""
    if sub:
        sf = font("Inter.ttf", 26, "SemiBold")
        T.text(d, (tx, 110), T.fit(d, "·  " + sub, sf, W - PAD - 120 - tx), sf, TEXT, "lm")
    T.text(d, (W - PAD - 6, 52), "万物录", cjk(34), alpha(T.GOLD_HI, 230), "rm")
    if p.get("pages", 1) > 1:
        T.text(d, (W - PAD - 6, 104), f"Page {p['page']} / {p['pages']}", font("Inter.ttf", 24, "Bold"),
               GOLD_LINE, "rm")


def _strip(img, p):
    x0, y0, x1, y1 = STRIP
    _glass(img, STRIP, a=200, r=12)
    strip = p["strip"]
    n = len(strip)
    d = ImageDraw.Draw(img)
    lf = font("Cinzel.ttf", 22, "Bold")
    seal_f = cjk(30)
    compact = n > 6                       # beasts: 11 realms, so only the current one shows its name
    if compact and not any(s[0] == p["tier"] for s in strip):
        active_w = other_w = (x1 - x0) / n     # Overview: no realm is lit, all seals share the strip
    elif compact:
        active_w = 34 + 14 + max(T.width(d, s[2].upper(), lf) for s in strip) + 36
        other_w = (x1 - x0 - active_w) / (n - 1)
    if compact:
        widths = [active_w if s[0] == p["tier"] else other_w for s in strip]
    else:                                 # each tier as wide as its label needs, spare room shared equally
        need = [36 + 10 + T.width(d, s[2].upper(), lf) + 24 for s in strip]
        spare = max(0, (x1 - x0) - sum(need)) / n
        widths = [w + spare for w in need]
    x = x0
    cy = (y0 + y1) / 2
    for i, ((key, seal, label, color), w) in enumerate(zip(strip, widths)):
        active = key == p["tier"]
        if active:
            T.soft_glow(img, (x + 8, y0 + 8, x + w - 8, y1 - 8), alpha(color, 120), 10)
            d = ImageDraw.Draw(img)
            d.rounded_rectangle(P(x + 4, y0 + 6, x + w - 4, y1 - 6), radius=10 * S,
                                outline=alpha(mix(color, (255, 255, 255), 0.35), 255), width=round(2 * S))
        seal_c = mix(color, (255, 255, 255), 0.25) if active else mix(color, (0, 0, 0), 0.35)
        lab_c = GOLD_LINE if active else SOFT
        if compact and not active:
            _strip_seal(img, d, (x + w / 2, cy + 1), seal, seal_f, seal_c, active)
        else:
            lw = T.width(d, label.upper(), lf)
            gx = x + (w - (36 + 10 + lw)) / 2
            _strip_seal(img, d, (gx + 18, cy + 1), seal, seal_f, seal_c, active)
            d = ImageDraw.Draw(img)
            T.text(d, (gx + 46, cy), label.upper(), lf, lab_c, "lm")
        d = ImageDraw.Draw(img)
        if i:
            d.ellipse(P(x - 2.5, cy - 2.5, x + 2.5, cy + 2.5), fill=alpha(EDGE, 200))
        x += w


def seal(img, center, r, glyph, color, cjk_char=None):
    """A tile / header seal: a drawn emblem ('emblem:...', no medallion around it), a drawn icon in a
    medallion, or (old data) a character in a medallion."""
    if T.painted(img, glyph, center, r * 2.3):
        return
    if glyph.startswith("emblem:"):
        T.icon(img, glyph, center, r * 2 + 4, color)
    else:
        T.medallion(img, center, r, glyph, color, cjk_char=len(glyph) == 1 if cjk_char is None else cjk_char)


def _strip_seal(img, d, center, glyph, f, color, active):
    if len(glyph) == 1:
        T.text(d, center, glyph, f, color, "mm")
    elif glyph.startswith(("emblem:", "art:")) or art_icons.resolve(glyph):
        T.icon(img, glyph, center, 46 if active else 40, color)
        if not active:      # dim the tiers that aren't picked
            x, y = center
            T.soft_glow(img, (x - 19, y - 19, x + 19, y + 19), (0, 0, 0, 90), 1)
    else:
        T.icon(img, glyph, center, 26, color)


# ── tiles ─────────────────────────────────────────────────────────────

def _layout(d, t, tw):
    text_w = tw - 2 * MED_R - 52
    name = T.wrap(d, t["name"], _f(NAME_F), text_w, lines=2)
    top = len(name) * NAME_H + (38 if t.get("badge") else 0)
    lines = []           # (text, is the tile's last line: drawn in gold)
    for i, line in enumerate(t["lines"]):
        last = i == len(t["lines"]) - 1 and len(t["lines"]) > 1
        lines += [(part, last) for part in T.wrap(d, line, _f(LINE_F), tw - 36, lines=3)]
    top_h = max(2 * MED_R + 8, top)
    return {"name": name, "lines": lines, "top": top_h, "h": 16 + top_h + 14 + len(lines) * LINE_H + 16}


def _tile(img, box, t, lay):
    x0, y0, x1, y1 = box
    color = t["color"]
    if t.get("found"):                    # the item /index search jumped to
        T.soft_glow(img, (x0 - 6, y0 - 6, x1 + 6, y1 + 6), alpha(T.GOLD, 200), 10, "rect")
    _glass(img, box, edge=mix(color, EDGE, 0.35) if not t.get("found") else T.GOLD_HI,
           width=2.6 if t.get("found") else 1.6)
    T.soft_glow(img, (x0 + 10, y0 + 8, x0 + 20 + 2 * MED_R + 20, y0 + 20 + 2 * MED_R), alpha(color, 70), 14)
    mx, my = x0 + 14 + MED_R, y0 + 16 + MED_R
    seal(img, (mx, my), MED_R, t["glyph"], color, t.get("cjk", True))
    d = ImageDraw.Draw(img)
    tx = mx + MED_R + 16
    block = len(lay["name"]) * NAME_H + (38 if t.get("badge") else 0)
    ny = y0 + 16 + (lay["top"] - block) / 2 + NAME_H / 2
    for line in lay["name"]:
        T.text(d, (tx, ny), line, _f(NAME_F), TEXT, "lm")
        ny += NAME_H
    if t.get("badge"):
        label, bc = t["badge"]
        bf = font("Inter.ttf", 20, "Bold")
        bw = T.width(d, label.upper(), bf) + 24
        d.rounded_rectangle(P(tx, ny - 8, tx + bw, ny + 22), radius=15 * S, fill=alpha(mix(bc, (0, 0, 0), 0.55), 255),
                            outline=bc, width=max(1, S))
        T.text(d, (tx + bw / 2, ny + 7), label.upper(), bf, mix(bc, (255, 255, 255), 0.4), "mm")
    ly = y0 + 16 + lay["top"] + 14
    d.line(P(x0 + 18, ly - 7, x1 - 18, ly - 7), fill=alpha(mix(color, EDGE, 0.4), 120), width=max(1, S))
    for i, (line, gold) in enumerate(lay["lines"]):
        T.text(d, (x0 + 18, ly + LINE_H / 2 + i * LINE_H), line, _f(LINE_F), GOLD_LINE if gold else TEXT, "lm")


def _footer(img, box, lines):
    x0, y0, x1, y1 = box
    _glass(img, box, a=205, r=12)
    d = ImageDraw.Draw(img)
    f = _f(FOOT_F)
    y = (y0 + y1) / 2 - (len(lines) - 1) * 17
    for line in lines:
        mixed(d, ((x0 + x1) / 2, y), line, f, cjk(26), GOLD_LINE)
        y += 34


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
