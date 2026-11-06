"""
Character Sheet · Equipment tab (Crimson Hall theme).

render_equipment(data) draws bot.sheet.data.equipment_data: the four gear slots equipment.md defines
(one weapon, one armor, two artifacts) with full details, how every attribute goes from base to final
(weapon + armor + technique buffs) and where each buff comes from, and the worn artifacts' effects in
their own list.
"""
from PIL import ImageDraw

from . import theme as t
from .theme import P, font

H = 780
EMPTY = {"weapon": ("fist", "BARE HANDS", "Weapons drop from chests found in /explore"),
         "armor": ("shield", "NO ARMOR", "Armor drops from chests found in /explore"),
         "artifact": ("star", "EMPTY ARTIFACT SLOT", "Artifacts drop from chests found in /explore")}


def render_equipment(data):
    img = t.canvas(t.W, H, seed=13)
    t.tab_strip(img, "equipment")
    t.frame(img, (6, 52, t.W - 6, H - 6))
    t.gold_text(img, (40, 66), f"{data['name'].upper()}'S ARMS", font("Cinzel.ttf", 32, "Black"), glow=t.EMBER)
    d = ImageDraw.Draw(img)
    t.text(d, (42, 122), "Weapons and armor give stat buffs; each artifact adds one effect. "
                         "Gear never limits which techniques you can use.", font("Inter.ttf", 14, "Medium"), t.ASH)
    t.divider(d, 30, 1170, 146)
    slots_panel(img, data, (30, 162, 560, H - 26))
    stats_panel(img, data, (576, 162, 1170, 482))
    effects_panel(img, data, (576, 496, 1170, H - 26))
    return t.finish(img)


def slots_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Gear Slots")
    rows = [("weapon", "Weapon", data.get("weapon")), ("armor", "Armor", data.get("armor"))]
    rows += [("artifact", f"Artifact {i}", a) for i, a in enumerate(data.get("artifacts") or [None, None], 1)]
    y = y0 + 46
    rh = 122
    for kind, label, item in rows:
        slot_row(img, (x0 + 16, y, x1 - 16, y + rh - 10), kind, label, item)
        y += rh
    d = ImageDraw.Draw(img)
    counts = data.get("spare_counts") or {"weapons": data.get("spare_count", 0)}
    spare = [f"{n} {name if n == 1 else plural}" for key, name, plural in
             (("weapons", "weapon", "weapons"), ("armor", "armor", "armor"), ("artifacts", "artifact", "artifacts"))
             if (n := counts.get(key, 0))]
    line = ("In your bag: " + ", ".join(spare) + ". Use the menus below to swap.") if spare else \
        "No spare gear in your bag."
    t.text(d, ((x0 + x1) / 2, y1 - 18), t.fit(d, line, font("Inter.ttf", 13, "Medium"), x1 - x0 - 30),
           font("Inter.ttf", 13, "Medium"), t.ASH, "mm")


def slot_row(img, box, kind, label, item):
    x0, y0, x1, y1 = box
    size = y1 - y0 - 8
    color = t.RARITY.get(item["tier"]) if item else t.ASH_DK
    sy = y0 + 4
    t.soft_glow(img, (x0 - 4, sy - 4, x0 + size + 4, sy + size + 4), t.alpha(color, 70 if item else 20), 10, "rect")
    t.socket(img, (x0, sy, x0 + size, sy + size), color, filled=bool(item), tint=False)
    center = (x0 + size / 2, sy + size / 2)
    if item:
        icon = item.get("icon") or item.get("type")
        t.icon(img, icon, center, size * 0.6, t.mix(color, (255, 255, 255), 0.2))
    else:
        t.icon(img, EMPTY[kind][0], center, size * 0.45, t.ASH_DK)
    d = ImageDraw.Draw(img)
    tx = x0 + size + 18
    t.spaced(d, (tx, y0 + 10), f"{label.upper()} SLOT", font("Cinzel.ttf", 11, "Bold"), t.BRONZE, 1.6)
    if not item:
        t.text(d, (tx, y0 + 38), EMPTY[kind][1], font("Cinzel.ttf", 18, "Bold"), t.PARCHMENT, "lm")
        t.text(d, (tx, y0 + 64), EMPTY[kind][2], font("Inter.ttf", 13, "Medium"), t.ASH, "lm")
        return
    f_name = font("Inter.ttf", 19, "Bold")
    t.text(d, (tx, y0 + 34), t.fit(d, item["name"], f_name, x1 - tx), f_name, t.GOLD_HI, "lm")
    if kind == "weapon":
        what = f"{item['type'].title()}"
        line = "  ·  ".join(item["buffs"]) or "No buffs"
    elif kind == "armor":
        what = item["type_label"]
        line = "  ·  ".join(item["buffs"]) or "No buffs"
    else:
        what = f"{item['family'].title()} · {item['group_label']}"
        line = item["effect"]
    sub = f"{item['tier'].title()} {what}  ·  needs {item['requires']}"
    f_sub = font("Inter.ttf", 13, "SemiBold")
    t.text(d, (tx, y0 + 58), t.fit(d, sub, f_sub, x1 - tx), f_sub, color, "lm")
    f_line = font("Inter.ttf", 15, "Bold")
    t.text(d, (tx, y0 + 84), t.fit(d, line, f_line, x1 - tx), f_line, t.PARCHMENT, "lm")


def stats_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Attributes: base to final")
    y = y0 + 70
    f_lab = font("Cinzel.ttf", 16, "Bold")
    f_num = font("Inter.ttf", 24, "Bold")
    f_src = font("Inter.ttf", 12, "Medium")
    for a in data["attributes"]:
        t.medallion(img, (x0 + 40, y), 21, a["icon"], a["color"], cjk_char=False)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 72, y - 18), a["label"].upper(), f_lab, t.PARCHMENT, "lm")
        src = "  ·  ".join(f"{name} +{pct:.1%}".replace(".0%", "%") for name, pct in a["sources"]) or "No buffs"
        for j, line in enumerate(t.wrap(d, src, f_src, x1 - x0 - 318, lines=3)):
            t.text(d, (x0 + 72, y + 2 + j * 14), line, f_src, t.ASH, "lm")
        t.text(d, (x1 - 172, y), f"{a['base']:,}", font("Inter.ttf", 18, "SemiBold"), t.ASH, "rm")
        ax = x1 - 146
        d.line(P(ax - 9, y, ax + 5, y), fill=t.BRONZE, width=round(2 * t.S))
        d.polygon([P(ax + 10, y), P(ax + 3, y - 6), P(ax + 3, y + 6)], fill=t.GOLD)
        t.text(d, (x1 - 22, y), f"{a['final']:,}", f_num, t.GOLD_HI, "rm")
        d.line(P(x0 + 20, y + 38, x1 - 20, y + 38), fill=t.BRONZE_DK, width=max(1, t.S))
        y += 82
    d = ImageDraw.Draw(img)
    t.text(d, ((x0 + x1) / 2, y1 - 18), "Weapon, armor and technique % buffs of a stat add together, then apply once",
           font("Inter.ttf", 12, "Medium"), t.ASH_DK, "mm")


def effects_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Artifact effects")
    effects = data.get("effects") or []
    d = ImageDraw.Draw(img)
    if not effects:
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 10), "No artifacts worn. Two slots are open from the start.",
               font("Inter.ttf", 14, "Medium"), t.ASH, "mm")
        return
    y = y0 + 72
    for e in effects:
        color = t.RARITY.get(e["tier"], t.ASH)
        t.medallion(img, (x0 + 40, y), 22, e["seal"], color)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 74, y - 12), t.fit(d, e["effect"], font("Inter.ttf", 17, "Bold"), x1 - x0 - 100),
               font("Inter.ttf", 17, "Bold"), t.GOLD_HI, "lm")
        sub = e["name"] + (f"  ·  {e['duel']}" if e.get("duel") else "")
        t.text(d, (x0 + 74, y + 12), t.fit(d, sub, font("Inter.ttf", 13, "Medium"), x1 - x0 - 100),
               font("Inter.ttf", 13, "Medium"), t.ASH, "lm")
        y += 64
    t.text(d, ((x0 + x1) / 2, y1 - 18), "Two of the same family can't be worn together",
           font("Inter.ttf", 12, "Medium"), t.ASH_DK, "mm")
