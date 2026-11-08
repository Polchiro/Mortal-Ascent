"""
Character Sheet · Inventory tab ("Collection", Night Ink theme with a jade accent: cards/ink.py).

render_bag(data) draws bot.sheet.data.bag_data:
- a category rail on the left (Chests, Manuals, Weapons, Armor, Artifacts, Pills, Herbs, Materials) with counts;
- the Materials groups as chips when the Materials tab is open;
- a 4 × 3 grid of item tiles: rarity glow and gem, quantity, EQUIPPED / LEARNED ribbons, the picked tile lit;
- the Inspect panel: the item, its rarity and kind, description, effects, notes, and the buttons it offers.
"""
from PIL import ImageDraw

from . import ink as k
from . import theme as t
from .theme import P, S, alpha, font, mix

W, H = 1200, 760
COLS, ROWS = 4, 3
JADE = k.accent("inventory")
NOTE_COLORS = {"gold": k.GOLD_HI, "red": (240, 110, 90), "jade": JADE}
ACTION_ICON = {"Open": "chest", "Learn": "scroll", "Equip": "sword", "Take": "pill", "Unequip": "fist",
               "Discard": "skull"}


def render_bag(data):
    img = k.canvas(W, H, "inventory", seed=5)
    k.sheet_frame(img, "inventory")
    k.title(img, (40, 66), f"{data['name']}'s Bag", JADE)
    capacity(img, data, (870, 82, 1160, 100))
    rail(img, data, (30, 140, 226, 726))
    top = 140
    grid_box = (242, top, 790, 726)
    k.plaque(img, grid_box, fill=k.PANEL)
    gy0 = top + 18
    if data.get("groups"):
        group_chips(img, data, (258, top + 16, 774, top + 42))
        gy0 = top + 54
    grid(img, data, (258, gy0, 774, 692))
    k.page_dots(img, ((242 + 790) / 2, 708), data["page"], data["pages"], JADE)
    inspect_panel(img, data["inspect"], (806, 140, 1170, 726))
    return t.finish(img)


def capacity(img, data, box):
    x0, y0, x1, y1 = box
    used, cap = data["used"], data["capacity"]
    full = cap and used >= cap
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0, y0 - 14), "BAG SPACE", font("Cinzel.ttf", 11, "Bold"), k.ASH, 2)
    t.text(d, (x1, y0 - 14), f"{used} / {cap}", font("Inter.ttf", 13, "Bold"),
           (240, 110, 90) if full else k.PARCHMENT, "rm")
    k.slim_bar(img, (x0, y0 + 2, x1, y1 - 4), used / cap if cap else 1, (240, 110, 90) if full else JADE)


def rail(img, data, box):
    """Category list: icon, name, count; the open one glows in jade with a gem marker."""
    x0, y0, x1, y1 = box
    k.plaque(img, box, fill=k.PANEL)
    cats = data["categories"]
    step = min(66, (y1 - y0 - 24) / max(1, len(cats)))
    y = y0 + 12 + step / 2
    f = font("Cinzel.ttf", 13, "Bold")
    for key, label, icon in cats:
        active = key == data["category"]
        count = data["counts"].get(key, 0)
        d = ImageDraw.Draw(img)
        if active:
            t.soft_glow(img, (x0 + 10, y - step / 2 + 6, x1 - 10, y + step / 2 - 6), alpha(JADE, 70), 8, "rect")
            d = ImageDraw.Draw(img)
            d.rounded_rectangle(P(x0 + 10, y - step / 2 + 6, x1 - 10, y + step / 2 - 6), radius=round(8 * S),
                                fill=alpha(mix(JADE, k.PANEL, 0.82), 255), outline=alpha(JADE, 220), width=max(1, S))
            k.gem(d, x0 + 10, y, 5, JADE)
        col = JADE if active else (k.ASH if count else k.ASH_DK)
        t.icon(img, icon, (x0 + 38, y), 22, mix(col, (255, 255, 255), 0.25) if active else col)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 60, y), label.upper(), f, k.GOLD_HI if active else (k.PARCHMENT if count else k.ASH_DK), "lm")
        t.text(d, (x1 - 22, y), str(count), font("Inter.ttf", 13, "Bold"), k.PARCHMENT if count else k.ASH_DK, "rm")
        if not active:
            d.line(P(x0 + 22, y + step / 2, x1 - 22, y + step / 2), fill=alpha(k.BRONZE_DK, 255), width=max(1, S))
        y += step


def group_chips(img, data, box):
    """Materials groups (Base · Bindings · Essences · Fuel & Liquids · Beast Cores); the open one is lit."""
    x0, y0, x1, y1 = box
    n = len(data["groups"])
    gap = 6
    w = (x1 - x0 - (n - 1) * gap) / n
    f = font("Cinzel.ttf", 10, "Bold")
    for i, (key, label, count) in enumerate(data["groups"]):
        bx = x0 + i * (w + gap)
        active = data.get("group") == key
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(P(bx, y0, bx + w, y1), radius=round(13 * S),
                            fill=alpha(mix(JADE, k.PANEL, 0.75) if active else k.PANEL_HI, 255),
                            outline=JADE if active else k.BRONZE_DK, width=max(1, S))
        t.text(d, (bx + w / 2, (y0 + y1) / 2), f"{label.upper()}  {count}", f,
               k.GOLD_HI if active else (k.PARCHMENT if count else k.ASH_DK), "mm")


def grid(img, data, box):
    x0, y0, x1, y1 = box
    gap = 12
    tw = (x1 - x0 - gap * (COLS - 1)) / COLS
    th = (y1 - y0 - gap * (ROWS - 1)) / ROWS
    tiles = data["tiles"]
    for i in range(COLS * ROWS):
        r, c = divmod(i, COLS)
        tx, ty = x0 + c * (tw + gap), y0 + r * (th + gap)
        tile(img, (tx, ty, tx + tw, ty + th), tiles[i] if i < len(tiles) else None)
    if not tiles:
        d = ImageDraw.Draw(img)
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2), "Nothing here yet", font("Cinzel.ttf", 18, "Bold"), k.ASH, "mm")
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 26), "Beasts, chests and /explore fill this bag",
               font("Inter.ttf", 13, "Medium"), k.ASH_DK, "mm")


def tile(img, box, it):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    shape = k.octagon(box, 10)
    if it is None:
        d.polygon(shape, fill=(8, 12, 20, 255))
        d.line(shape + [shape[0]], fill=alpha(k.BRONZE_DK, 255), width=max(1, S), joint="curve")
        return
    color = t.RARITY.get(it["rarity_key"], k.ASH)
    if it["selected"]:
        t.soft_glow(img, (x0 - 4, y0 - 4, x1 + 4, y1 + 4), alpha(k.GOLD, 150), 8, "rect")
        d = ImageDraw.Draw(img)
    d.polygon(shape, fill=(10, 14, 24, 255))
    cx = (x0 + x1) / 2
    iy = y0 + (y1 - y0) * 0.36
    t.soft_glow(img, (cx - 44, iy - 36, cx + 44, iy + 36), alpha(color, 90), 14)
    d = ImageDraw.Draw(img)
    # rarity band at the foot
    d.polygon([P(x0 + 1, y1 - 30), P(x1 - 1, y1 - 30), P(x1 - 1, y1 - 10), P(x1 - 10, y1 - 1), P(x0 + 10, y1 - 1),
               P(x0 + 1, y1 - 10)], fill=alpha(mix(color, (0, 0, 0), 0.62), 255))
    d.line(P(x0 + 8, y1 - 30, x1 - 8, y1 - 30), fill=alpha(color, 200), width=max(1, S))
    d.line(shape + [shape[0]], fill=k.GOLD_HI if it["selected"] else alpha(mix(color, k.BRONZE_DK, 0.45), 255),
           width=round((2.2 if it["selected"] else 1.4) * S), joint="curve")
    t.icon(img, it["icon"], (cx, iy), 56, mix(color, (255, 255, 255), 0.15))
    d = ImageDraw.Draw(img)
    k.gem(d, x1 - 14, y0 + 14, 5, color)
    f_name = font("Inter.ttf", 13, "Bold")
    lines = t.wrap(d, it["name"], f_name, x1 - x0 - 14)
    ny = y1 - 46 - (len(lines) - 1) * 15
    for j, line in enumerate(lines):
        t.text(d, (cx, ny + j * 15), line, f_name, k.PARCHMENT, "mm")
    t.text(d, (cx, y1 - 15), t.fit(d, it["rarity"], font("Inter.ttf", 11, "Bold"), x1 - x0 - 16),
           font("Inter.ttf", 11, "Bold"), mix(color, (255, 255, 255), 0.35), "mm")
    tag = "EQUIPPED" if it["equipped"] else ("LEARNED" if it.get("learned") else None)
    if it["qty"] > 1:
        k.chip(img, (x0 + 8, y0 + (40 if tag else 16)), f"×{it['qty']:,}", k.GOLD, size=11, fill=(8, 8, 6))
    if tag:
        f_t = font("Cinzel.ttf", 9, "Bold")
        tw = t.width(ImageDraw.Draw(img), tag, f_t) + 22
        k.ribbon(img, (x0 + 1, y0 + 10, x0 + 1 + tw, y0 + 26), tag, k.VERMILION if it["equipped"] else (40, 130, 100))


def inspect_panel(img, it, box):
    x0, y0, x1, y1 = box
    k.plaque(img, box, "Inspect", color=JADE)
    d = ImageDraw.Draw(img)
    if not it:
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2), "Pick an item to inspect it", font("Inter.ttf", 14, "Medium"),
               k.ASH, "mm")
        return
    color = t.RARITY.get(it["rarity_key"], k.ASH)
    cx = (x0 + x1) / 2
    # icon in a glowing double ring
    t.soft_glow(img, (cx - 70, y0 + 34, cx + 70, y0 + 174), alpha(color, 110), 18)
    d = ImageDraw.Draw(img)
    for rr, col, wd in ((60, k.BRONZE_DK, 5), (63, k.GOLD, 1.2), (54, alpha(color, 200), 1.2)):
        d.ellipse(P(cx - rr, y0 + 104 - rr, cx + rr, y0 + 104 + rr), outline=col, width=round(wd * S))
    d.ellipse(P(cx - 52, y0 + 52, cx + 52, y0 + 156), fill=alpha(mix(color, (0, 0, 0), 0.78), 255))
    t.icon(img, it["icon"], (cx, y0 + 104), 72, mix(color, (255, 255, 255), 0.18))
    d = ImageDraw.Draw(img)
    f_name = font("Cinzel.ttf", 19, "Bold")
    y = y0 + 190
    for line in t.wrap(d, it["name"].upper(), f_name, x1 - x0 - 30):
        t.text(d, (cx, y), line, f_name, k.GOLD_HI, "mm")
        y += 24
    rar = it["rarity"] + (f"  ·  ×{it['qty']:,}" if it["qty"] > 1 else "")
    k.chip(img, (cx, y + 4), rar, color, size=11, anchor="m")
    d = ImageDraw.Draw(img)
    t.text(d, (cx, y + 28), t.fit(d, it["kind"], font("Inter.ttf", 12, "Medium"), x1 - x0 - 30),
           font("Inter.ttf", 12, "Medium"), k.ASH, "mm")
    y += 48
    t.divider(d, x0 + 20, x1 - 20, y)
    y += 18
    f_body = font("Inter.ttf", 13, "Medium")
    for para in it["lines"]:
        for line in t.wrap(d, para, f_body, x1 - x0 - 40, lines=3):
            t.text(d, (x0 + 20, y), line, f_body, k.PARCHMENT, "lm")
            y += 19
    if it["effects"]:
        y += 8
        for eff in it["effects"]:
            k.gem(d, x0 + 26, y, 4, JADE)
            for j, line in enumerate(t.wrap(d, eff, f_body, x1 - x0 - 60, lines=2)):
                t.text(d, (x0 + 38, y + j * 17), line, f_body, k.GOLD_HI, "lm")
            y += 21 + 17 * (len(t.wrap(d, eff, f_body, x1 - x0 - 60, lines=2)) - 1)
    acts = it.get("actions") or []
    bottom = y1 - 22 - (36 if acts else 0)
    ny = max(y + 10, bottom - 24 * len(it["notes"]) + 12)
    for note, tone in it["notes"]:
        col = NOTE_COLORS.get(tone, k.ASH)
        k.chip(img, (cx, ny), t.fit(d, note, font("Inter.ttf", 11, "Bold"), x1 - x0 - 60), col, size=11, anchor="m")
        ny += 24
    if acts:
        # which buttons below the card work on this item
        d = ImageDraw.Draw(img)
        ay = y1 - 30
        d.line(P(x0 + 20, ay - 22, x1 - 20, ay - 22), fill=alpha(k.BRONZE_DK, 255), width=max(1, S))
        f_a = font("Inter.ttf", 12, "Bold")
        widths = [t.width(d, a, f_a) + 40 for a in acts]
        x = cx - (sum(widths) + 8 * (len(acts) - 1)) / 2
        for a, w in zip(acts, widths):
            danger = a == "Discard"
            col = (220, 100, 90) if danger else JADE
            d.rounded_rectangle(P(x, ay - 13, x + w, ay + 13), radius=round(6 * S),
                                fill=alpha(mix(col, (0, 0, 0), 0.72), 255), outline=alpha(col, 220), width=max(1, S))
            t.icon(img, ACTION_ICON.get(a, "star"), (x + 15, ay), 14, mix(col, (255, 255, 255), 0.3))
            d = ImageDraw.Draw(img)
            t.text(d, (x + 26, ay + 0.5), a, f_a, k.PARCHMENT, "lm")
            x += w + 8
