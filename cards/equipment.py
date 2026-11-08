"""
Character Sheet · Equipment tab ("Armory", Night Ink theme with a steel accent: cards/ink.py).

render_equipment(data) draws bot.sheet.data.equipment_data:
- four display cases for the slots equipment.md defines (weapon, armor, two artifacts): the piece on a lit
  pedestal, its tier seal (凡精灵宝神), name, kind and realm needed, its buffs or effect, and its forged passive
  sockets; an empty case shows a faint outline and where that gear comes from;
- Attributes: base → final for HP, Attack and Defense, with the bonus drawn on the bar and its sources;
- Artifact effects: what the worn artifacts (and forged artifact passives) do.
"""
from PIL import ImageDraw

from . import ink as k
from . import theme as t
from .emblems import empty_slot
from .theme import P, S, alpha, font, mix

W, H = 1200, 660
STEEL = k.accent("equipment")
EMPTY = {"weapon": ("fist", "Bare hands", "Weapons drop from chests"),
         "armor": ("shield", "No armor", "Armor drops from chests"),
         "artifact": ("star", "Empty", "Artifacts drop from chests")}


def render_equipment(data):
    img = k.canvas(W, H, "equipment", seed=13)
    k.sheet_frame(img, "equipment")
    k.title(img, (40, 66), f"{data['name']}'s Armory", STEEL)
    spare_chips(img, data, (1160, 90))
    cases = [("weapon", "Weapon", data.get("weapon")), ("armor", "Armor", data.get("armor"))]
    cases += [("artifact", f"Artifact {'I' * i}", a) for i, a in enumerate(data.get("artifacts") or [None, None], 1)]
    cw, ch, gap = 362, 238, 16
    for i, (kind, label, item) in enumerate(cases):
        r, c = divmod(i, 2)
        x, y = 30 + c * (cw + gap), 136 + r * (ch + gap)
        case(img, (x, y, x + cw, y + ch), kind, label, item)
    stats_panel(img, data, (786, 136, 1170, 462))
    effects_panel(img, data, (786, 484, 1170, 628))
    return t.finish(img)


def spare_chips(img, data, anchor):
    """What else is in the bag to swap in (the menus under the card list them)."""
    x, y = anchor
    counts = data.get("spare_counts") or {"weapons": data.get("spare_count", 0)}
    d = ImageDraw.Draw(img)
    parts = [(icon, f"{n} {one if n == 1 else many}")
             for key, icon, one, many in (("artifacts", "pearl", "artifact", "artifacts"), ("armor", "shield", "armor", "armor"),
                                          ("weapons", "sword", "weapon", "weapons"))
             if (n := counts.get(key, 0))]
    if not parts:
        t.text(d, (x, y), "No spare gear in your bag", font("Inter.ttf", 13, "Medium"), k.ASH_DK, "rm")
        return
    for icon, label in parts:
        w = k.chip(img, (x, y), label, STEEL, size=12, anchor="r")
        t.icon(img, icon, (x - w - 12, y), 16, STEEL)
        x -= w + 34
    d = ImageDraw.Draw(img)
    t.spaced(d, (x + 4, y), "IN YOUR BAG", font("Cinzel.ttf", 10, "Bold"), k.ASH, 2, "r")


def case(img, box, kind, label, item):
    x0, y0, x1, y1 = box
    color = t.RARITY.get(item["tier"], k.ASH) if item else k.ASH_DK
    k.plaque(img, box, fill=mix(color, k.PANEL, 0.9 if item else 0.97), cut=14)
    cx = (x0 + x1) / 2
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0 + 20, y0 + 24), label.upper(), font("Cinzel.ttf", 11, "Bold"), k.BRONZE if item else k.ASH_DK, 2)
    # pedestal
    py = y0 + 84
    if item:
        t.soft_glow(img, (cx - 70, py - 52, cx + 70, py + 52), alpha(color, 120), 16)
        d = ImageDraw.Draw(img)
        d.ellipse(P(cx - 70, py + 34, cx + 70, py + 50), fill=alpha(mix(color, (0, 0, 0), 0.6), 200))
    for rr, col, wd in ((46, k.BRONZE_DK, 5), (49, k.GOLD if item else k.BRONZE_DK, 1.2),
                        (41, alpha(color, 200 if item else 80), 1)):
        d.ellipse(P(cx - rr, py - rr, cx + rr, py + rr), outline=col, width=round(wd * S))
    d.ellipse(P(cx - 40, py - 40, cx + 40, py + 40), fill=alpha(mix(color, (0, 0, 0), 0.8 if item else 0.92), 255))
    if item:
        t.icon(img, item.get("icon") or item.get("type"), (cx, py), 58, mix(color, (255, 255, 255), 0.2))
        # tier seal, top right
        t.medallion(img, (x1 - 32, y0 + 32), 18, k.TIER_CHAR.get(item["tier"], "凡"), color)
    elif kind in ("armor", "artifact"):
        empty_slot(img, kind, (cx, py), 46)
    else:
        t.icon(img, EMPTY[kind][0], (cx, py), 34, k.ASH_DK)
    d = ImageDraw.Draw(img)
    if not item:
        t.text(d, (cx, y0 + 156), EMPTY[kind][1], font("Cinzel.ttf", 18, "Bold"), k.ASH, "mm")
        t.text(d, (cx, y0 + 180), EMPTY[kind][2], font("Inter.ttf", 12, "Medium"), k.ASH_DK, "mm")
        return
    f_name = font("Inter.ttf", 17, "Bold")
    t.text(d, (cx, y0 + 150), t.fit(d, item["name"], f_name, x1 - x0 - 30), f_name, k.GOLD_HI, "mm")
    if kind == "weapon":
        what = item["type"].title()
    elif kind == "armor":
        what = item["type_label"]
    else:
        what = item["group_label"]
    sub = f"{item['tier'].title()} {what}" + (f"  ·  needs {item['requires']}" if item.get("requires") else "")
    t.text(d, (cx, y0 + 170), t.fit(d, sub, font("Inter.ttf", 11, "SemiBold"), x1 - x0 - 30),
           font("Inter.ttf", 11, "SemiBold"), mix(color, (255, 255, 255), 0.3), "mm")
    # buffs or the artifact's effect
    bits = item["buffs"] if kind in ("weapon", "armor") else [item.get("effect_short") or item["effect"]]
    bits = bits or ["No buffs"]
    f_c = font("Inter.ttf", 12, "Bold")
    widths = [t.width(d, b, f_c) + 14 for b in bits]
    x = cx - (sum(widths) + 6 * (len(bits) - 1)) / 2
    for b, w in zip(bits, widths):
        k.chip(img, (x, y0 + 194), b, k.GOLD, size=12)
        x += w + 6
    passive_sockets(img, item.get("passives") or [], (x0 + 16, y0 + 220, x1 - 16))


def passive_sockets(img, slots, box):
    """Forged passive slots (docs/forge.md): a rarity emblem and name each, or a hollow socket."""
    import forge
    x0, y, x1 = box
    if not slots:
        return
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 11, "Bold")
    w = (x1 - x0) / len(slots)
    for i, p in enumerate(slots):
        cx = x0 + w * i + w / 2
        if p:
            color = forge.RARITY_COLORS[p["rarity"]]
            name = t.fit(d, p["name"], f, w - 26)
            tw = t.width(d, name, f) + 20
            t.icon(img, f"passive:{p['rarity']}", (cx - tw / 2 + 7, y), 15, color)
            d = ImageDraw.Draw(img)
            t.text(d, (cx - tw / 2 + 18, y), name, f, color, "lm")
        else:
            d.ellipse(P(cx - 34, y - 5, cx - 24, y + 5), outline=k.ASH_DK, width=max(1, round(1.4 * S)))
            t.text(d, (cx - 18, y), "Empty socket", font("Inter.ttf", 11, "Medium"), k.ASH_DK, "lm")


def stats_panel(img, data, box):
    x0, y0, x1, y1 = box
    k.plaque(img, box, "Attributes", color=STEEL)
    y = y0 + 48
    step = (y1 - y0 - 56) / max(1, len(data["attributes"]))
    for a in data["attributes"]:
        col = a["color"]
        t.medallion(img, (x0 + 38, y + 8), 19, a["icon"], col, cjk_char=False)
        d = ImageDraw.Draw(img)
        t.spaced(d, (x0 + 66, y - 2), a["label"].upper(), font("Cinzel.ttf", 13, "Bold"), k.PARCHMENT, 1.6)
        t.text(d, (x0 + 66, y + 18), f"{a['base']:,}", font("Inter.ttf", 13, "SemiBold"), k.ASH, "lm")
        bw = t.width(d, f"{a['base']:,}", font("Inter.ttf", 13, "SemiBold"))
        d.line(P(x0 + 72 + bw, y + 18, x0 + 84 + bw, y + 18), fill=k.BRONZE, width=round(1.6 * S))
        d.polygon([P(x0 + 90 + bw, y + 18), P(x0 + 84 + bw, y + 13), P(x0 + 84 + bw, y + 23)], fill=k.GOLD)
        t.gold_text(img, (x1 - 22, y + 8), f"{a['final']:,}", font("Cinzel.ttf", 26, "Black"), anchor="rm")
        # bar: base part dim, bonus part bright
        bx0, bx1, by = x0 + 22, x1 - 22, y + 40
        total = max(1, a["final"])
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(P(bx0, by - 3, bx1, by + 3), radius=round(3 * S), fill=(3, 5, 10, 255),
                            outline=alpha(k.BRONZE_DK, 255), width=max(1, S))
        bm = bx0 + (bx1 - bx0) * a["base"] / total
        d.rounded_rectangle(P(bx0, by - 3, bm, by + 3), radius=round(3 * S), fill=mix(col, (0, 0, 0), 0.45))
        if a["final"] > a["base"]:
            d.rounded_rectangle(P(bm, by - 3, bx1, by + 3), radius=round(3 * S), fill=col)
        src = "  ·  ".join(f"{n} +{p:.1%}".replace(".0%", "%") for n, p in a["sources"]) or "No buffs"
        t.text(d, (bx0, by + 15), t.fit(d, src, font("Inter.ttf", 11, "Medium"), bx1 - bx0 - 60),
               font("Inter.ttf", 11, "Medium"), k.ASH, "lm")
        if a["bonus"]:
            t.text(d, (bx1, by + 15), f"+{a['bonus']:.1%}".replace(".0%", "%"), font("Inter.ttf", 12, "Bold"),
                   mix(col, (255, 255, 255), 0.3), "rm")
        y += step


def effects_panel(img, data, box):
    x0, y0, x1, y1 = box
    k.plaque(img, box, "Artifact Effects", color=STEEL)
    effects = data.get("effects") or []
    d = ImageDraw.Draw(img)
    if not effects:
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 6), "No artifacts worn", font("Cinzel.ttf", 16, "Bold"), k.ASH, "mm")
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 30), "Two artifact slots are open from the start",
               font("Inter.ttf", 12, "Medium"), k.ASH_DK, "mm")
        return
    y = y0 + 46
    room = max(1, int((y1 - y0 - 40) // 44))
    shown = effects if len(effects) <= room else effects[:room - 1]
    for e in shown:
        color = e.get("color") or t.RARITY.get(e["tier"], k.ASH)
        t.medallion(img, (x0 + 34, y + 6), 17, e.get("icon") or "seal:" + e["seal"], color, cjk_char=False)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 60, y - 3), t.fit(d, e["effect"], font("Inter.ttf", 14, "Bold"), x1 - x0 - 80),
               font("Inter.ttf", 14, "Bold"), k.GOLD_HI, "lm")
        sub = e["name"] + (f"  ·  {e['duel']}" if e.get("duel") else "")
        t.text(d, (x0 + 60, y + 16), t.fit(d, sub, font("Inter.ttf", 11, "Medium"), x1 - x0 - 80),
               font("Inter.ttf", 11, "Medium"), k.ASH, "lm")
        y += 44
    if len(shown) < len(effects):
        d = ImageDraw.Draw(img)
        left = len(effects) - len(shown)
        t.text(d, (x0 + 60, y), f"+ {left} more forged passive{'s' if left > 1 else ''}", font("Inter.ttf", 12, "Medium"),
               k.ASH, "lm")
