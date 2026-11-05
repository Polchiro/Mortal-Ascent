"""
Character Sheet · Profile tab (Crimson Hall theme).

render_profile(data) draws cards built by bot.sheet.data.profile_data:
header (name, talent, realm, phase, layer pips), attributes, Internal Qi,
the portrait, equipped technique sockets, the weapon, and a footer with
deeds, the dantian orb and the purse.
"""
from PIL import ImageDraw

from . import theme as t
from .theme import P, font, short

H = 800


def render_profile(data):
    img = t.canvas(t.W, H)
    t.tab_strip(img, "profile")
    t.frame(img, (6, 52, t.W - 6, H - 6), corners=True)
    header(img, data)
    attributes_panel(img, data, (30, 186, 412, 628))
    t.portrait(img, (428, 180, 772, 628), data.get("avatar_bytes"), data["name"], data["realm"],
               t.TALENT.get(data["talent"], t.EMBER))
    techniques_panel(img, data, (788, 186, 1170, 628))
    footer(img, data, (30, 662, 1170, 774))
    return t.finish(img)


def header(img, data):
    d = ImageDraw.Draw(img)
    f_name = font("Cinzel.ttf", 38, "Black")
    name = t.fit(d, data["name"].upper(), f_name, 400)
    t.gold_text(img, (40, 66), name, f_name, glow=t.EMBER)
    d = ImageDraw.Draw(img)
    color = t.TALENT.get(data["talent"], t.ASH)
    f_sub = font("Inter.ttf", 15, "Medium")
    x = 42
    if data.get("username"):
        s = f"@{data['username']}"
        t.text(d, (x, 130), s, f_sub, t.ASH)
        x += t.width(d, s, f_sub) + 14
    badge = f"{data['talent'].upper()} TALENT"
    f_b = font("Cinzel.ttf", 13, "Bold")
    bw = t.width(d, badge, f_b) + 26
    d.rounded_rectangle(P(x, 120, x + bw, 142), radius=round(4 * t.S), fill=t.mix(color, (0, 0, 0), 0.7) + (255,),
                        outline=color, width=max(1, t.S))
    t.text(d, (x + bw / 2, 131.5), badge, f_b, t.mix(color, (255, 255, 255), 0.3), "mm")

    t.medallion(img, (600, 108), 42, t.REALM_CHAR.get(data["realm"], "武"), t.EMBER)

    f_realm = font("Cinzel.ttf", 32, "Black")
    realm = data["realm"].upper()
    rw = t.width(d, realm, f_realm)
    f_realm = f_realm if rw <= 420 else font("Cinzel.ttf", 26, "Black")
    t.gold_text(img, (1160, 66), realm, f_realm, anchor="ra")
    d = ImageDraw.Draw(img)
    t.spaced(d, (1160, 116), f"{data['phase'].upper()}  ·  {t.ordinal(data['layer']).upper()} LAYER",
             font("Cinzel.ttf", 13, "Bold"), t.GLOW, 1.6, "r")
    total = data["max_layer"]
    gap = 17
    t.pips(d, 1160 - (total - 1) * gap - 6, 142, data["layer"], total, r=5.5, gap=gap)
    t.divider(d, 30, 1170, 166)


def attributes_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Attributes")
    d = ImageDraw.Draw(img)
    f_label = font("Cinzel.ttf", 16, "Bold")
    f_val = font("Inter.ttf", 26, "Bold")
    f_small = font("Inter.ttf", 12, "Medium")
    y = y0 + 64
    for a in data["attributes"]:
        t.medallion(img, (x0 + 40, y), 19, a["icon"], a["color"], cjk_char=False)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 70, y - 10), a["label"].upper(), f_label, t.PARCHMENT, "lm")
        sub = f"Base {a['base']:,}" + (f"  ·  +{a['bonus']:.0%} buffs" if a["bonus"] else "")
        t.text(d, (x0 + 70, y + 12), sub, f_small, t.ASH, "lm")
        t.text(d, (x1 - 20, y), f"{a['final']:,}", f_val, t.GOLD_HI, "rm")
        d.line(P(x0 + 20, y + 30, x1 - 20, y + 30), fill=t.alpha(t.BRONZE_DK, 255), width=max(1, t.S))
        y += 62

    qi = data["qi"]
    y += 4
    t.heading(img, (x0 + 18, y), "Internal Qi", x1 - 18)
    d = ImageDraw.Draw(img)
    y += 24
    frac = qi["qi"] / qi["capacity"] if qi["capacity"] else 0
    t.bar(img, (x0 + 20, y, x1 - 20, y + 20), frac, t.EMBER, f"{short(qi['qi'])} / {short(qi['capacity'])}")
    d = ImageDraw.Draw(img)
    y += 36
    rows = [("flame", "Qi Rate", f"{qi['rate']:,.1f}/h  ×{qi['mult']:.2f}".replace(".0/h", "/h")),
            ("hourglass", "Bar full in", qi["eta"]),
            ("star", "Next", f"{qi['gate']}  ·  {qi['gate_note']}")]
    if qi["pending"] >= 0.05:
        rows.insert(1, ("pill", "Waiting", f"+{short(qi['pending'])} {qi['pending_label']}"))
    f_k = font("Inter.ttf", 13, "SemiBold")
    f_v = font("Inter.ttf", 13, "Medium")
    for ic, k, v in rows[:4]:
        t.icon(img, ic, (x0 + 30, y), 13, t.GLOW)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 46, y), k, f_k, t.ASH, "lm")
        t.text(d, (x1 - 20, y), t.fit(d, v, f_v, x1 - x0 - 150), f_v, t.PARCHMENT, "rm")
        y += 22


def techniques_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Equipped Techniques")
    y = y0 + 50
    for slot in data["slots"]:
        technique_row(img, (x0 + 16, y, x1 - 16, y + 80), slot)
        y += 90
    t.heading(img, (x0 + 18, y + 6), "Weapon", x1 - 18)
    weapon_row(img, (x0 + 16, y + 26, x1 - 16, y + 98), data["weapon"])
    d = ImageDraw.Draw(img)
    t.text(d, ((x0 + x1) / 2, y1 - 16), f"{data['learned_count']} techniques learned  ·  see the Techniques tab",
           font("Inter.ttf", 12, "Medium"), t.ASH, "mm")


def technique_row(img, box, slot):
    x0, y0, x1, y1 = box
    tech = slot["tech"]
    size = y1 - y0 - 12
    sx0, sy0 = x0, y0 + 4
    color = t.RARITY.get(tech["grade"]) if tech else t.ASH_DK
    t.socket(img, (sx0, sy0, sx0 + size, sy0 + size), color, filled=bool(tech), locked=slot["locked"])
    d = ImageDraw.Draw(img)
    cx, cy = sx0 + size / 2, sy0 + size / 2
    tx = sx0 + size + 14
    f_slot = font("Cinzel.ttf", 11, "Bold")
    t.spaced(d, (tx, y0 + 10), f"{slot['slot'].upper()} SLOT", f_slot, t.BRONZE, 1.6)
    if tech:
        t.text(d, (cx, cy + 1), t.SCHOOL_CHAR.get(tech["school"], "武"), t.cjk(30), t.mix(color, (255, 255, 255), 0.2), "mm")
        f_name = font("Inter.ttf", 17, "Bold")
        t.text(d, (tx, y0 + 30), t.fit(d, tech["name"], f_name, x1 - tx), f_name, t.PARCHMENT, "lm")
        sub = f"{tech['grade']} · {tech['school']} · {tech['type'].title()}"
        t.text(d, (tx, y0 + 50), sub, font("Inter.ttf", 12, "SemiBold"), color, "lm")
        t.diamonds(d, tx + 5, y0 + 68, tech["stage"] + 1, 5, 4.5)
        t.text(d, (tx + 72, y0 + 68), t.fit(d, tech["stage_name"], font("Inter.ttf", 12, "Medium"), x1 - tx - 72),
               font("Inter.ttf", 12, "Medium"), t.ASH, "lm")
    else:
        msg = slot.get("note") if slot["locked"] else "Empty"
        t.text(d, (tx, y0 + 38), msg, font("Inter.ttf", 15, "Medium"), t.ASH_DK if slot["locked"] else t.ASH, "lm")


def weapon_row(img, box, weapon):
    x0, y0, x1, y1 = box
    size = y1 - y0 - 8
    color = t.RARITY.get(weapon["tier"]) if weapon else t.ASH_DK
    t.socket(img, (x0, y0 + 4, x0 + size, y0 + 4 + size), color, filled=bool(weapon))
    d = ImageDraw.Draw(img)
    tx = x0 + size + 14
    if weapon:
        t.icon(img, weapon["type"], (x0 + size / 2, y0 + 4 + size / 2), size * 0.6, t.mix(color, (255, 255, 255), 0.2))
        d = ImageDraw.Draw(img)
        f_name = font("Inter.ttf", 17, "Bold")
        t.text(d, (tx, y0 + 18), t.fit(d, weapon["name"], f_name, x1 - tx), f_name, t.PARCHMENT, "lm")
        t.text(d, (tx, y0 + 38), f"{weapon['tier'].title()} tier {weapon['type']}", font("Inter.ttf", 12, "SemiBold"),
               color, "lm")
        t.text(d, (tx, y0 + 58), "  ·  ".join(weapon["buffs"]) or "No buffs", font("Inter.ttf", 13, "SemiBold"),
               t.GOLD_HI, "lm")
    else:
        t.icon(img, "fist", (x0 + size / 2, y0 + 4 + size / 2), size * 0.5, t.ASH_DK)
        d = ImageDraw.Draw(img)
        t.text(d, (tx, y0 + 26), "Bare hands", font("Inter.ttf", 17, "Bold"), t.PARCHMENT, "lm")
        t.text(d, (tx, y0 + 48), "Weapons drop from chests", font("Inter.ttf", 12, "Medium"), t.ASH, "lm")


def footer(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box)
    d = ImageDraw.Draw(img)
    cy = (y0 + y1) / 2
    if data.get("status"):
        t.text(d, (t.W / 2, y0 - 16), t.fit(d, data["status"], font("Inter.ttf", 13, "SemiBold"), 900),
               font("Inter.ttf", 13, "SemiBold"), t.GLOW, "mm")
    deeds = [("skull", "Beasts", f"{data['beasts']:,}"), ("herb", "Herbs", f"{data.get('herbs', 0):,}"),
             ("flame", "Breakthroughs", f"{data['breakthroughs']:,}"), ("star", "Rank", f"#{data['rank']}")]
    f_k = font("Cinzel.ttf", 11, "Bold")
    f_v = font("Inter.ttf", 20, "Bold")
    for i, (ic, k, v) in enumerate(deeds):
        x = x0 + 24 + (0, 112, 224, 392)[i]
        t.icon(img, ic, (x + 10, cy - 12), 16, t.BRONZE)
        d = ImageDraw.Draw(img)
        t.spaced(d, (x + 26, cy - 12), k.upper(), f_k, t.ASH, 1.2)
        t.text(d, (x + 2, cy + 16), v, f_v, t.PARCHMENT, "lm")

    qi = data["qi"]
    frac = qi["qi"] / qi["capacity"] if qi["capacity"] else 0
    t.orb(img, (t.W / 2, cy), 44, frac, f"{frac:.0%}")
    d = ImageDraw.Draw(img)

    if data.get("coins") is not None:
        purse = [("lotus", "Lotus Coins", data["coins"], t.LOTUS), ("pearl", "Moon Pearls", data["pearls"], t.MOON)]
        for i, (ic, k, v, col) in enumerate(purse):
            x = x1 - 330 + i * 170
            t.medallion(img, (x + 22, cy), 20, ic, col, cjk_char=False)
            d = ImageDraw.Draw(img)
            t.spaced(d, (x + 52, cy - 12), k.upper(), f_k, t.ASH, 1.2)
            t.text(d, (x + 50, cy + 12), short(v), f_v, col, "lm")
    else:
        t.text(d, (x1 - 30, cy), "Purse kept private", font("Inter.ttf", 13, "Medium"), t.ASH_DK, "rm")
