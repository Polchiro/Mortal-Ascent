"""
Character Sheet · Inventory tab (Crimson Hall theme).

render_bag(data) draws bot.sheet.data.bag_data: category tabs with counts,
a 4 × 3 grid of item tiles (rarity border, icon, quantity, equipped mark),
and the Inspect panel for the selected item.
"""
from PIL import ImageDraw

from . import theme as t
from .theme import P, font

H = 760
COLS, ROWS = 4, 3
NOTE_COLORS = {"gold": t.GOLD_HI, "red": t.GLOW, "jade": t.JADE}


def render_bag(data):
    img = t.canvas(t.W, H, seed=5)
    t.tab_strip(img, "inventory")
    t.frame(img, (6, 52, t.W - 6, H - 6))
    d = ImageDraw.Draw(img)
    t.gold_text(img, (40, 66), f"{data['name'].upper()}'S BAG", font("Cinzel.ttf", 32, "Black"), glow=t.EMBER)
    d = ImageDraw.Draw(img)
    used, cap = data["used"], data["capacity"]
    t.spaced(d, (1160, 80), "BAG SLOTS", font("Cinzel.ttf", 12, "Bold"), t.GOLD, 1.6, "r")
    t.bar(img, (900, 98, 1160, 114), used / cap if cap else 1, t.EMBER if used < cap else t.GLOW, f"{used} / {cap}")
    category_tabs(img, data, (30, 140, 1170, 184))
    grid(img, data, (30, 200, 760, 726))
    inspect_panel(img, data["inspect"], (776, 200, 1170, 726))
    return t.finish(img)


def category_tabs(img, data, box):
    x0, y0, x1, y1 = box
    n = len(data["categories"])
    w = (x1 - x0 - (n - 1) * 10) / n
    f = font("Cinzel.ttf", 14, "Bold")
    for i, (key, label, icon) in enumerate(data["categories"]):
        bx = x0 + i * (w + 10)
        active = key == data["category"]
        d = ImageDraw.Draw(img)
        if active:
            t.banner(img, (bx, y0, bx + w, y1))
            t.soft_glow(img, (bx + 20, y0 + 6, bx + w - 20, y1 - 6), t.alpha(t.GLOW, 70), 8)
        else:
            d.rectangle(P(bx, y0, bx + w, y1), fill=t.alpha(t.PANEL, 230), outline=t.BRONZE_DK, width=max(1, t.S))
        count = data["counts"].get(key, 0)
        color = t.GOLD_HI if active else t.ASH
        t.icon(img, icon, (bx + 26, (y0 + y1) / 2), 18, t.GOLD if active else t.ASH_DK)
        d = ImageDraw.Draw(img)
        t.text(d, (bx + 44, (y0 + y1) / 2), label.upper(), f, color, "lm")
        t.text(d, (bx + w - 14, (y0 + y1) / 2), str(count), font("Inter.ttf", 13, "Bold"),
               t.PARCHMENT if count else t.ASH_DK, "rm")


def grid(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box)
    gap = 12
    gy1 = y1 - 34
    tw = (x1 - x0 - 24 - gap * (COLS - 1)) / COLS
    th = (gy1 - y0 - 12 - gap * (ROWS - 1)) / ROWS
    tiles = data["tiles"]
    for i in range(COLS * ROWS):
        r, c = divmod(i, COLS)
        tx, ty = x0 + 12 + c * (tw + gap), y0 + 12 + r * (th + gap)
        tile(img, (tx, ty, tx + tw, ty + th), tiles[i] if i < len(tiles) else None)
    d = ImageDraw.Draw(img)
    if not tiles:
        t.text(d, ((x0 + x1) / 2, (y0 + gy1) / 2), "Nothing here yet. Explore to find more.",
               font("Inter.ttf", 15, "Medium"), t.ASH, "mm")
    t.text(d, ((x0 + x1) / 2, y1 - 17), f"Page {data['page']} of {data['pages']}", font("Cinzel.ttf", 13, "Bold"),
           t.GOLD, "mm")


def tile(img, box, it):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    if it is None:
        d.rectangle(P(x0, y0, x1, y1), fill=(10, 6, 7, 255), outline=t.alpha(t.BRONZE_DK, 200), width=max(1, t.S))
        return
    color = t.RARITY.get(it["rarity_key"], t.ASH)
    if it["selected"]:
        t.soft_glow(img, (x0 - 2, y0 - 2, x1 + 2, y1 + 2), t.alpha(t.GOLD, 150), 6, "rect")
    t.socket(img, (x0, y0, x1, y1), color, tint=False)
    d = ImageDraw.Draw(img)
    if it["selected"]:
        d.rectangle(P(x0 - 1, y0 - 1, x1 + 1, y1 + 1), outline=t.GOLD_HI, width=round(2 * t.S))
    cx = (x0 + x1) / 2
    t.soft_glow(img, (cx - 38, y0 + 18, cx + 38, y0 + 82), t.alpha(color, 70), 12)
    t.icon(img, it["icon"], (cx, y0 + 50), 54, t.mix(color, (255, 255, 255), 0.15))
    d = ImageDraw.Draw(img)
    f_name = font("Inter.ttf", 13, "Bold")
    lines = t.wrap(d, it["name"], f_name, x1 - x0 - 16)
    ny = y1 - 30 - (len(lines) - 1) * 8
    for j, line in enumerate(lines):
        t.text(d, (cx, ny + j * 16), line, f_name, t.PARCHMENT, "mm")
    t.text(d, (cx, y1 - 12), it["rarity"], font("Inter.ttf", 11, "SemiBold"), color, "mm")
    if it["qty"] > 1:
        q = f"×{it['qty']}"
        f_q = font("Inter.ttf", 12, "Bold")
        qw = t.width(d, q, f_q) + 12
        d.rounded_rectangle(P(x1 - qw - 6, y0 + 6, x1 - 6, y0 + 24), radius=round(4 * t.S), fill=(0, 0, 0, 230),
                            outline=t.BRONZE, width=max(1, t.S))
        t.text(d, (x1 - 6 - qw / 2, y0 + 15), q, f_q, t.GOLD_HI, "mm")
    tag = "EQUIPPED" if it["equipped"] else ("LEARNED" if it.get("learned") else None)
    if tag:
        f_t = font("Cinzel.ttf", 10, "Bold")
        tw = t.width(d, tag, f_t) + 12
        d.rectangle(P(x0 + 6, y0 + 6, x0 + 6 + tw, y0 + 22), fill=t.CRIMSON if it["equipped"] else (20, 60, 44),
                    outline=t.GOLD, width=max(1, t.S // 2))
        t.text(d, (x0 + 6 + tw / 2, y0 + 14), tag, f_t, t.GOLD_HI, "mm")


def inspect_panel(img, it, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Inspect")
    d = ImageDraw.Draw(img)
    if not it:
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2), "Pick an item to inspect it", font("Inter.ttf", 14, "Medium"),
               t.ASH, "mm")
        return
    color = t.RARITY.get(it["rarity_key"], t.ASH)
    cx = (x0 + x1) / 2
    t.medallion(img, (cx, y0 + 104), 48, it["icon"], color, cjk_char=False)
    d = ImageDraw.Draw(img)
    f_name = font("Cinzel.ttf", 20, "Bold")
    y = y0 + 172
    for line in t.wrap(d, it["name"].upper(), f_name, x1 - x0 - 30):
        t.text(d, (cx, y), line, f_name, t.GOLD_HI, "mm")
        y += 24
    sub = f"{it['rarity']}  ·  {it['kind']}" + (f"  ·  ×{it['qty']}" if it["qty"] > 1 else "")
    t.text(d, (cx, y + 2), t.fit(d, sub, font("Inter.ttf", 12, "SemiBold"), x1 - x0 - 30),
           font("Inter.ttf", 12, "SemiBold"), color, "mm")
    y += 24
    t.divider(d, x0 + 20, x1 - 20, y)
    y += 18
    f_body = font("Inter.ttf", 13, "Medium")
    for para in it["lines"]:
        for line in t.wrap(d, para, f_body, x1 - x0 - 40, lines=3):
            t.text(d, (x0 + 20, y), line, f_body, t.PARCHMENT, "lm")
            y += 19
    if it["effects"]:
        y += 10
        t.heading(img, (x0 + 20, y), "Effects", x1 - 20)
        d = ImageDraw.Draw(img)
        y += 24
        for eff in it["effects"]:
            t.stud(d, x0 + 26, y, 3.5)
            t.text(d, (x0 + 38, y), t.fit(d, eff, f_body, x1 - x0 - 60), f_body, t.GOLD_HI, "lm")
            y += 21
    y = max(y + 8, y1 - 18 - 22 * len(it["notes"]))
    for note, tone in it["notes"]:
        t.text(d, (cx, y), t.fit(d, note, font("Inter.ttf", 12, "Bold"), x1 - x0 - 30), font("Inter.ttf", 12, "Bold"),
               NOTE_COLORS.get(tone, t.ASH), "mm")
        y += 22
