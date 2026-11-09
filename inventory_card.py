"""
/inventory card — ink-wash scroll style, items shown as a grid of tiles.
render_inventory(data) returns a PIL Image.
"""
import os
import random
from PIL import Image, ImageDraw

from profile_card import (S, W, PAPER, PAPER_DARK, INK, INK_SOFT, VERMILION, JADE, GOLD,
                          GRADES, TIERS, background, font, cjk, p, text, spaced,
                          brush_stroke, seal_square, ink_wash)

H_INV = 640
CATEGORIES = [("manuals", "Manuals"), ("weapons", "Weapons"), ("pills", "Pills"),
              ("materials", "Materials"), ("chests", "Chests")]
COLS, ROWS = 4, 3
PER_PAGE = COLS * ROWS

PILL_CHAR = "丹"
MATERIAL_CHAR = "草"
CHEST_CHARS = {"common": ("木", (140, 100, 60)), "uncommon": ("铜", (160, 104, 50)), "rare": ("银", (120, 128, 140)),
               "epic": ("金", (190, 140, 50)), "legendary": ("玉", (46, 128, 104)), "mythic": ("星", (120, 80, 190))}


def wrap(d, s, f, max_w):
    words, lines, line = s.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if d.textlength(test, font=f) / S <= max_w:
            line = test
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines[:2]


def tile(img, d, x, y, w, h, item):
    d.rectangle(p(x, y, x + w, y + h), fill=PAPER_DARK + (205,))
    if item.get("highlight"):
        d.rectangle(p(x, y, x + w, y + h), outline=item["color"], width=2 * S)
    seal_square(img, item["char"], (x + 12, y + 14), 38, item["color"])
    d = ImageDraw.Draw(img)

    f_name = font("Inter.ttf", 15, "SemiBold")
    f_sub = font("Inter.ttf", 12, "Medium")
    badge = 44 if item.get("qty", 1) > 1 else 0
    lines = wrap(d, item["name"], f_name, w - 74 - badge)
    for i, line in enumerate(lines):
        text(d, (x + 62, y + 14 + i * 19), line, f_name, INK)
    text(d, (x + 12, y + h - 26), item["sub"], f_sub, item["color"])

    if item.get("qty", 1) > 1:
        q = f"×{item['qty']}"
        f_q = font("Inter.ttf", 12, "Bold")
        qw = d.textlength(q, font=f_q) / S + 12
        d.rounded_rectangle(p(x + w - qw - 8, y + 8, x + w - 8, y + 26), radius=9 * S, fill=INK)
        text(d, (x + w - 8 - qw / 2, y + 17), q, f_q, PAPER, "mm")
    if item.get("status"):
        f_st = font("Inter.ttf", 11, "Bold")
        text(d, (x + w - 12, y + h - 26), item["status"].upper(), f_st, JADE, "ra")
    return d


def render_inventory(data):
    img = background(H_INV)
    img = ink_wash(img, (110, 260), 120, random.Random(9))
    d = ImageDraw.Draw(img)

    # left: 行囊 (traveller's bag) calligraphy + seal
    f_cal = cjk(54)
    for i, ch in enumerate("行囊"):
        d.text(p(110, 160 + i * 72), ch, font=f_cal, fill=INK + (210,), anchor="mm")
    seal_square(img, "藏", (78, H_INV - 132), 60, VERMILION, rotate=-5)
    d = ImageDraw.Draw(img)
    for i in range(3):
        d.line(p(200 + i, 60, 200 + i, H_INV - 60), fill=INK + (40 + i * 30,), width=1 * S)

    x0, wcol = 236, 926

    # title
    f_title = font("Cinzel.ttf", 40, "Black")
    title = f"{data['name'].upper()}'S BAG"
    text(d, (x0, 46), title, f_title, INK)
    tw = d.textlength(title, font=f_title) / S
    brush_stroke(d, x0, x0 + tw + 8, 100, 7, VERMILION + (230,))

    # category tabs
    f_tab = font("Cinzel.ttf", 15, "Bold")
    tx = x0
    for key, label in CATEGORIES:
        count = data["counts"].get(key, 0)
        s = f"{label.upper()}  {count}"
        sw = d.textlength(s, font=f_tab) / S
        active = key == data["category"]
        spaced(d, (tx, 122), s, f_tab, VERMILION if active else INK_SOFT, 1.2)
        sw += len(s) * 1.2
        if active:
            d.rectangle(p(tx, 146, tx + sw, 149), fill=VERMILION)
        tx += sw + 34
    d.line(p(x0, 152, x0 + wcol, 152), fill=INK_SOFT + (110,), width=1 * S)

    # grid
    items = data["items"]
    page = data.get("page", 1)
    shown = items[(page - 1) * PER_PAGE: page * PER_PAGE]
    gap = 14
    tw_ = (wcol - (COLS - 1) * gap) / COLS
    th = 104
    for i, item in enumerate(shown):
        col, row = i % COLS, i // COLS
        d = tile(img, d, x0 + col * (tw_ + gap), 172 + row * (th + gap), tw_, th, item)

    # footer
    pages = max(1, -(-len(items) // PER_PAGE))
    f_foot = font("Inter.ttf", 14, "Medium")
    text(d, (x0, H_INV - 62), f"Page {page} / {pages}   ·   {len(items)} items", f_foot, INK_SOFT)
    used = sum(data["counts"].values())
    text(d, (x0 + wcol, H_INV - 62), f"Bag  {used} / {data['capacity']} slots", f_foot,
         VERMILION if used > data["capacity"] * 0.9 else INK_SOFT, "ra")

    return img.resize((W, H_INV), Image.LANCZOS).convert("RGB")


# ── item builders (turn game data into tiles) ─────────────────────────

def manual_item(tech, qty=1, learned=False):
    char, color = GRADES[tech["grade"]]
    effect = tech.get("effect")
    if effect:
        kind, val = effect
        if kind == "combo":
            eff = f"Combo {val[0]}×{int(val[1] * 100)}%"
        elif kind == "stagger" and val >= 1:
            eff = "Stagger · No Guard"
        elif kind == "unbreakable":
            eff = "Unbreakable"
        elif kind == "heavy":
            eff = f"Heavy ×{val}"
        else:
            eff = f"{kind.title()} {int(val * 100)}%"
    else:
        eff = "No effect"
    return {"char": char, "color": color, "name": tech["name"], "qty": qty,
            "sub": f"{tech['type'].title()} · {eff}", "status": "Learned" if learned else None}


def weapon_item(name, tier, buffs, equipped=False):
    char, color = TIERS[tier]
    return {"char": char, "color": color, "name": name, "sub": buffs,
            "status": "Equipped" if equipped else None, "highlight": equipped}


if __name__ == "__main__":
    from technique import TECHNIQUES
    T = TECHNIQUES
    items = [
        manual_item(T["viper_fang_finger"], learned=True),
        manual_item(T["rolling_thunder_palm"], learned=True),
        manual_item(T["golden_bell_cover"], learned=True),
        manual_item(T["thousand_shadow_palm"]),
        manual_item(T["moon_mirror_palm"], qty=2),
        manual_item(T["autumn_wind_kick"]),
        manual_item(T["fierce_tiger_claw"], learned=True),
        manual_item(T["iron_cloth_body"], qty=3),
        manual_item(T["swift_swallow_kick"]),
        manual_item(T["crane_wing_deflection"], qty=2),
        manual_item(T["iron_fist"], learned=True),
        manual_item(T["horse_stance_guard"], learned=True),
        manual_item(T["parrying_arm"]),
        manual_item(T["calm_breath_stance"], qty=4),
    ]
    sample = {
        "name": "Shoaib",
        "category": "manuals",
        "page": 1,
        "items": items,
        "counts": {"manuals": 14, "weapons": 6, "pills": 9, "materials": 23, "chests": 2},
        "capacity": 60,
    }
    here = os.path.dirname(os.path.abspath(__file__))
    render_inventory(sample).save(os.path.join(here, "inventory_preview.png"))
    print("saved inventory_preview.png")
