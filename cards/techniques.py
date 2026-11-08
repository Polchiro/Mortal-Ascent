"""
Character Sheet · Techniques tab ("Scripture Pavilion", Night Ink theme with a violet accent: cards/ink.py).

render_techniques(data) draws bot.sheet.data.techniques_data:
- the three stances (Attack, Defense, and Flex from Martial Warrior, as technique.md sets them): equipped
  technique in a medallion with its mastery arc, an empty socket, or a locked one with what opens it;
- every learned technique as an unrolled scroll: grade seal, name, grade · school · type, power, passive
  and rest turns, its special effect, and mastery (stage beads, EXP bar, "Trial ready" when the bar is full).
  Equipped scrolls carry a vermilion ribbon; the others are marked Ready to equip.
"""
from PIL import ImageDraw

from . import ink as k
from . import theme as t
from .emblems import empty_slot
from .theme import P, S, alpha, font, mix

W, H = 1200, 790
VIOLET = k.accent("techniques")
EMPTY_SCHOOL = {"Attack": "Fist", "Defense": "Body", "Flex": "Palm"}


def render_techniques(data):
    img = k.canvas(W, H, "techniques", seed=9)
    k.sheet_frame(img, "techniques")
    k.title(img, (40, 66), f"{data['name']}'s Techniques", VIOLET)
    equipped = sum(1 for s in data["slots"] if s["tech"])
    x = 1160
    for label in (f"Qi Rate +{data['qi_bonus']:.1%}".replace(".0%", "%"),
                  f"{equipped} / {data['slot_count']} stances", f"{data['learned_count']} learned"):
        x -= k.chip(img, (x, 90), label, VIOLET, size=12, anchor="r") + 8
    stances(img, data, (30, 136, 1170, 266))
    k.heading(img, (40, 298), "Learned Scrolls", 1160, VIOLET)
    cw, chh, gx, gy = 562, 136, 16, 11
    for i, tech in enumerate(data["techniques"]):
        r, c = divmod(i, 2)
        x0, y0 = 30 + c * (cw + gx), 316 + r * (chh + gy)
        scroll(img, (x0, y0, x0 + cw, y0 + chh), tech)
    if not data["techniques"]:
        d = ImageDraw.Draw(img)
        t.text(d, (W / 2, 470), "No techniques learned yet. Manuals drop from chests.", font("Inter.ttf", 15, "Medium"),
               k.ASH, "mm")
    k.page_dots(img, (W / 2, H - 20), data["page"], data["pages"], VIOLET)
    return t.finish(img)


# ── Stances ───────────────────────────────────────────────────────────

def stances(img, data, box):
    x0, y0, x1, y1 = box
    n = len(data["slots"])
    gap = 16
    w = (x1 - x0 - gap * (n - 1)) / n
    for i, slot in enumerate(data["slots"]):
        sx = x0 + i * (w + gap)
        stance(img, (sx, y0, sx + w, y1), slot)


def mastery_arc(img, center, r, stage, color):
    cx, cy = center
    d = ImageDraw.Draw(img)
    for i in range(5):
        a0 = -90 - 80 + i * 32
        d.arc(P(cx - r, cy - r, cx + r, cy + r), a0, a0 + 26, fill=color if i <= stage else (40, 34, 52),
              width=round(3.2 * S))


def stance(img, box, slot):
    x0, y0, x1, y1 = box
    tech = slot["tech"]
    color = t.RARITY.get(tech["grade"], k.ASH) if tech else k.ASH_DK
    k.plaque(img, box, fill=mix(color, k.PANEL, 0.9) if tech else k.PANEL, cut=14)
    cy = (y0 + y1) / 2
    mx = x0 + 70
    r = 40
    if tech:
        t.soft_glow(img, (mx - r - 10, cy - r - 10, mx + r + 10, cy + r + 10), alpha(color, 120), 10)
    d = ImageDraw.Draw(img)
    d.ellipse(P(mx - r, cy - r, mx + r, cy + r), fill=(8, 8, 14, 255), outline=k.BRONZE_DK, width=round(4 * S))
    d.ellipse(P(mx - r + 4, cy - r + 4, mx + r - 4, cy + r - 4), outline=k.GOLD if tech else k.ASH_DK,
              width=round(1.4 * S))
    if tech:
        d.ellipse(P(mx - r + 8, cy - r + 8, mx + r - 8, cy + r - 8), fill=alpha(mix(color, (0, 0, 0), 0.55), 255))
        t.icon(img, tech.get("icon") or "school:" + tech["school"], (mx, cy), 50, (250, 244, 232))
        mastery_arc(img, (mx, cy), r + 6, tech["stage"], VIOLET)
    elif slot["locked"]:
        t.icon(img, "lock", (mx, cy), 28, k.ASH_DK)
    else:
        empty_slot(img, "school:" + EMPTY_SCHOOL.get(slot["slot"], "Palm"), (mx, cy), 44)
    d = ImageDraw.Draw(img)
    tx = mx + r + 22
    t.spaced(d, (tx, y0 + 30), f"{slot['slot'].upper()} STANCE", font("Cinzel.ttf", 10, "Bold"), k.BRONZE, 2)
    if tech:
        f_n = font("Inter.ttf", 18, "Bold")
        t.text(d, (tx, cy - 4), t.fit(d, tech["name"], f_n, x1 - tx - 16), f_n, k.PARCHMENT, "lm")
        t.text(d, (tx, cy + 18), f"{tech['grade']} · {tech['school']}", font("Inter.ttf", 12, "SemiBold"), color, "lm")
        t.text(d, (tx, cy + 38), t.fit(d, f"{tech['power']}  ·  {tech['stage_name']}", font("Inter.ttf", 11, "Medium"),
                                       x1 - tx - 16), font("Inter.ttf", 11, "Medium"), k.ASH, "lm")
    elif slot["locked"]:
        t.text(d, (tx, cy + 2), "Locked", font("Cinzel.ttf", 17, "Bold"), k.ASH, "lm")
        t.text(d, (tx, cy + 24), slot.get("note") or "", font("Inter.ttf", 12, "Medium"), k.ASH_DK, "lm")
    else:
        t.text(d, (tx, cy + 2), "Empty", font("Cinzel.ttf", 17, "Bold"), k.ASH, "lm")
        t.text(d, (tx, cy + 24), slot.get("note") if slot["slot"] == "Flex" else f"Any {slot['slot'].lower()} technique",
               font("Inter.ttf", 12, "Medium"), k.ASH_DK, "lm")


# ── Scrolls ───────────────────────────────────────────────────────────

def rod(d, x, y0, y1):
    """A scroll's wooden rod with gold end caps."""
    d.rounded_rectangle(P(x - 6, y0 - 4, x + 6, y1 + 4), radius=round(5 * S), fill=(70, 42, 26, 255),
                        outline=(30, 18, 10, 255), width=max(1, S))
    d.line(P(x - 2, y0, x - 2, y1), fill=(120, 80, 50, 200), width=max(1, round(1.2 * S)))
    for yy in (y0 - 6, y1 + 6):
        d.rounded_rectangle(P(x - 8, yy - 4, x + 8, yy + 4), radius=round(3 * S), fill=k.GOLD, outline=(110, 80, 30))


def grade_seal(img, center, grade, color):
    """A square vermilion chop with the grade's character (凡 黄 玄 地 天)."""
    cx, cy = center
    s = 17
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(P(cx - s, cy - s, cx + s, cy + s), radius=round(3 * S), fill=(150, 34, 28, 235),
                        outline=(236, 120, 96, 255), width=round(1.4 * S))
    d.rectangle(P(cx - s + 4, cy - s + 4, cx + s - 4, cy + s - 4), outline=(236, 140, 110, 160), width=max(1, S))
    t.text(d, (cx, cy + 1), k.GRADE_CHAR.get(grade, "武"), t.cjk(19), (255, 232, 214), "mm", shadow=False)


def scroll(img, box, tech):
    x0, y0, x1, y1 = box
    color = t.RARITY.get(tech["grade"], k.ASH)
    bx0, bx1 = x0 + 10, x1 - 10
    # silk body
    layer_fill = mix(mix(color, (30, 26, 34), 0.88), k.PANEL, 0.3)
    d = ImageDraw.Draw(img)
    d.rectangle(P(bx0, y0, bx1, y1), fill=alpha(layer_fill, 245))
    d.rectangle(P(bx0, y0, bx1, y1), outline=alpha(k.BRONZE, 220), width=max(1, round(1.2 * S)))
    d.line(P(bx0 + 4, y0 + 5, bx1 - 4, y0 + 5), fill=alpha(k.GOLD, 70), width=max(1, S))
    d.line(P(bx0 + 4, y1 - 5, bx1 - 4, y1 - 5), fill=alpha(k.GOLD, 70), width=max(1, S))
    if tech["equipped"]:
        t.soft_glow(img, (bx0, y0, bx1, y0 + 30), alpha(k.VERMILION, 50), 10, "rect")
        d = ImageDraw.Draw(img)
    rod(d, x0 + 6, y0 + 4, y1 - 4)
    rod(d, x1 - 6, y0 + 4, y1 - 4)
    # technique medallion
    mx, my = x0 + 62, y0 + 54
    t.medallion(img, (mx, my), 30, tech.get("icon") or "school:" + tech["school"], color, cjk_char=False)
    d = ImageDraw.Draw(img)
    t.diamonds(d, mx - 21, y0 + 104, tech["stage"] + 1, 5, 4.2, VIOLET)
    tx = x0 + 108
    f_n = font("Inter.ttf", 18, "Bold")
    t.text(d, (tx, y0 + 24), t.fit(d, tech["name"], f_n, bx1 - tx - 140), f_n, k.PARCHMENT, "lm")
    t.text(d, (tx, y0 + 45), f"{tech['grade']} Grade · {tech['school']} · {tech['type'].title()}",
           font("Inter.ttf", 12, "SemiBold"), color, "lm")
    grade_seal(img, (bx1 - 30, y0 + 30), tech["grade"], color)
    if tech["equipped"]:
        k.ribbon(img, (bx1 - 140, y0 + 13, bx1 - 54, y0 + 31), "EQUIPPED", k.VERMILION)
    else:
        k.chip(img, (bx1 - 56, y0 + 22), "Ready to equip", VIOLET, size=10, anchor="r")
    # stat chips
    d = ImageDraw.Draw(img)
    cd = f"Rests {tech['cooldown']} turn{'s' if tech['cooldown'] > 1 else ''}"
    x = tx
    for icon, txt in (("sword" if tech["type"] == "attack" else "shield", tech["power"]), ("star", tech["passive"]),
                      ("hourglass", cd)):
        t.icon(img, icon, (x + 7, y0 + 68), 13, k.GOLD)
        d = ImageDraw.Draw(img)
        t.text(d, (x + 18, y0 + 68), txt, font("Inter.ttf", 12, "Bold"), k.GOLD_HI, "lm")
        x += 18 + t.width(d, txt, font("Inter.ttf", 12, "Bold")) + 16
    eff = tech["effect"]
    if eff and eff != "No special effect":
        t.text(d, (tx, y0 + 88), t.fit(d, eff, font("Inter.ttf", 12, "Medium"), bx1 - tx - 16),
               font("Inter.ttf", 12, "Medium"), mix(VIOLET, (255, 255, 255), 0.35), "lm")
    # mastery bar
    if tech["cap"]:
        frac = tech["exp"] / tech["cap"]
        label = f"{tech['stage_name']}  ·  {tech['exp']:,} / {tech['cap']:,}"
    else:
        frac, label = 1, f"{tech['stage_name']}  ·  final stage"
    if tech["trial_ready"]:
        label = "Trial ready (/spar)  ·  " + label
    k.slim_bar(img, (tx, y0 + 106, bx1 - 18, y0 + 120), frac, k.GOLD if tech["trial_ready"] else VIOLET, label)
