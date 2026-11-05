"""
Character Sheet · Equipment tab (Crimson Hall theme).

render_equipment(data) draws bot.sheet.data.equipment_data: the one weapon
slot equipment.md defines (armor and artifacts are not designed yet), how
every attribute goes from base to final and where each buff comes from, and
the spare weapons in the bag.
"""
from PIL import ImageDraw

from . import theme as t
from .theme import P, font

H = 640


def render_equipment(data):
    img = t.canvas(t.W, H, seed=13)
    t.tab_strip(img, "equipment")
    t.frame(img, (6, 52, t.W - 6, H - 6))
    t.gold_text(img, (40, 66), f"{data['name'].upper()}'S ARMS", font("Cinzel.ttf", 32, "Black"), glow=t.EMBER)
    d = ImageDraw.Draw(img)
    t.text(d, (42, 122), "Weapons only give stat buffs. They never limit which techniques you can use.",
           font("Inter.ttf", 14, "Medium"), t.ASH)
    t.divider(d, 30, 1170, 146)
    weapon_panel(img, data, (30, 162, 470, H - 26))
    stats_panel(img, data, (486, 162, 1170, H - 26))
    return t.finish(img)


def weapon_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Weapon Slot")
    w = data["weapon"]
    cx = (x0 + x1) / 2
    color = t.RARITY.get(w["tier"]) if w else t.ASH_DK
    t.soft_glow(img, (cx - 90, y0 + 60, cx + 90, y0 + 230), t.alpha(color, 90 if w else 30), 20)
    t.socket(img, (cx - 70, y0 + 74, cx + 70, y0 + 214), color, filled=bool(w), tint=False)
    t.icon(img, w["type"] if w else "fist", (cx, y0 + 144), 96 if w else 70,
           t.mix(color, (255, 255, 255), 0.2) if w else t.ASH_DK)
    d = ImageDraw.Draw(img)
    y = y0 + 248
    if w:
        f = font("Cinzel.ttf", 20, "Bold")
        for line in t.wrap(d, w["name"].upper(), f, x1 - x0 - 30):
            t.text(d, (cx, y), line, f, t.GOLD_HI, "mm")
            y += 25
        t.text(d, (cx, y + 2), f"{w['tier'].title()} tier {w['type']}  ·  needs {w['requires']}",
               font("Inter.ttf", 13, "SemiBold"), color, "mm")
        y += 30
        t.text(d, (cx, y), "  ·  ".join(w["buffs"]) or "No buffs", font("Inter.ttf", 16, "Bold"), t.PARCHMENT, "mm")
    else:
        t.text(d, (cx, y), "BARE HANDS", font("Cinzel.ttf", 20, "Bold"), t.PARCHMENT, "mm")
        t.text(d, (cx, y + 28), "Weapons drop from chests found in /explore", font("Inter.ttf", 13, "Medium"),
               t.ASH, "mm")
    y = y1 - 74
    t.heading(img, (x0 + 18, y), "In your bag", x1 - 18)
    d = ImageDraw.Draw(img)
    if data["spare_count"]:
        names = ", ".join(s["name"] for s in data["spare"][:2])
        more = data["spare_count"] - min(2, len(data["spare"]))
        line = f"{names}" + (f" and {more} more" if more > 0 else "")
        t.text(d, (x0 + 20, y + 26), t.fit(d, line, font("Inter.ttf", 13, "Medium"), x1 - x0 - 40),
               font("Inter.ttf", 13, "Medium"), t.PARCHMENT, "lm")
        t.text(d, (x0 + 20, y + 46), "Use the menu below to swap", font("Inter.ttf", 12, "Medium"), t.ASH, "lm")
    else:
        t.text(d, (x0 + 20, y + 26), "No spare weapons", font("Inter.ttf", 13, "Medium"), t.ASH, "lm")


def stats_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Attributes: base to final")
    y = y0 + 76
    f_lab = font("Cinzel.ttf", 16, "Bold")
    f_num = font("Inter.ttf", 24, "Bold")
    f_src = font("Inter.ttf", 13, "Medium")
    for a in data["attributes"]:
        t.medallion(img, (x0 + 42, y), 22, a["icon"], a["color"], cjk_char=False)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 76, y - 10), a["label"].upper(), f_lab, t.PARCHMENT, "lm")
        src = "  ·  ".join(f"{name} +{pct:.1%}".replace(".0%", "%") for name, pct in a["sources"]) or "No buffs"
        for j, line in enumerate(t.wrap(d, src, f_src, x1 - x0 - 330)):
            t.text(d, (x0 + 76, y + 13 + j * 17), line, f_src, t.ASH, "lm")
        t.text(d, (x1 - 200, y), f"{a['base']:,}", font("Inter.ttf", 18, "SemiBold"), t.ASH, "rm")
        ax = x1 - 172
        d.line(P(ax - 9, y, ax + 5, y), fill=t.BRONZE, width=round(2 * t.S))
        d.polygon([P(ax + 10, y), P(ax + 3, y - 6), P(ax + 3, y + 6)], fill=t.GOLD)
        t.text(d, (x1 - 24, y), f"{a['final']:,}", f_num, t.GOLD_HI, "rm")
        d.line(P(x0 + 20, y + 40, x1 - 20, y + 40), fill=t.BRONZE_DK, width=max(1, t.S))
        y += 92
    d = ImageDraw.Draw(img)
    t.text(d, ((x0 + x1) / 2, y1 - 24), "All % buffs of a stat add together, then apply once (stats.md)",
           font("Inter.ttf", 12, "Medium"), t.ASH_DK, "mm")
