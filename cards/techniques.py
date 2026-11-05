"""
Character Sheet · Techniques tab (Crimson Hall theme).

render_techniques(data) draws bot.sheet.data.techniques_data: the equipped
sockets (Attack, Defense, Flex from Martial Warrior, as technique.md sets them)
and every learned technique with its effect, power, cooldown and mastery.
"""
from PIL import ImageDraw

from . import theme as t
from .profile import technique_row
from .theme import P, font

H = 790


def render_techniques(data):
    img = t.canvas(t.W, H, seed=9)
    t.tab_strip(img, "techniques")
    t.frame(img, (6, 52, t.W - 6, H - 6))
    t.gold_text(img, (40, 66), f"{data['name'].upper()}'S TECHNIQUES", font("Cinzel.ttf", 32, "Black"), glow=t.EMBER)
    d = ImageDraw.Draw(img)
    equipped = sum(1 for s in data["slots"] if s["tech"])
    t.text(d, (42, 122), f"{data['learned_count']} learned  ·  {equipped} of {data['slot_count']} slots in use  ·  "
                         f"Qi Rate +{data['qi_bonus']:.1%} from the best equipped",
           font("Inter.ttf", 14, "Medium"), t.ASH)
    t.divider(d, 30, 1170, 146)

    w = (1140 - 2 * 14) / 3
    for i, slot in enumerate(data["slots"]):
        x = 30 + i * (w + 14)
        t.panel(img, (x, 160, x + w, 262))
        technique_row(img, (x + 12, 170, x + w - 12, 254), slot)

    t.panel(img, (30, 278, 1170, H - 24), "Learned Techniques")
    cw = (1140 - 36 - 16) / 2
    for i, tech in enumerate(data["techniques"]):
        r, c = divmod(i, 2)
        x, y = 48 + c * (cw + 16), 316 + r * 140
        card(img, (x, y, x + cw, y + 128), tech)
    d = ImageDraw.Draw(img)
    t.text(d, (t.W / 2, H - 42), f"Page {data['page']} of {data['pages']}", font("Cinzel.ttf", 13, "Bold"), t.GOLD, "mm")
    return t.finish(img)


def card(img, box, tech):
    x0, y0, x1, y1 = box
    color = t.RARITY.get(tech["grade"], t.ASH)
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), fill=(12, 7, 8, 255), outline=t.BRONZE_DK, width=max(1, t.S))
    if tech["equipped"]:
        d.rectangle(P(x0, y0, x0 + 4, y1), fill=t.GOLD)
    t.medallion(img, (x0 + 44, y0 + 46), 30, t.SCHOOL_CHAR.get(tech["school"], "武"), color)
    d = ImageDraw.Draw(img)
    tx = x0 + 88
    f_name = font("Inter.ttf", 18, "Bold")
    t.text(d, (tx, y0 + 22), t.fit(d, tech["name"], f_name, x1 - tx - 110), f_name, t.PARCHMENT, "lm")
    t.text(d, (tx, y0 + 44), f"{tech['grade']} Grade · {tech['school']} · {tech['type'].title()}",
           font("Inter.ttf", 12, "SemiBold"), color, "lm")
    if tech["equipped"]:
        f_t = font("Cinzel.ttf", 10, "Bold")
        tw = t.width(d, "EQUIPPED", f_t) + 14
        d.rectangle(P(x1 - tw - 12, y0 + 12, x1 - 12, y0 + 30), fill=t.CRIMSON, outline=t.GOLD, width=max(1, t.S // 2))
        t.text(d, (x1 - 12 - tw / 2, y0 + 21), "EQUIPPED", f_t, t.GOLD_HI, "mm")
    f_b = font("Inter.ttf", 13, "Medium")
    t.text(d, (tx, y0 + 66), t.fit(d, tech["effect"], f_b, x1 - tx - 14), f_b, t.GOLD_HI, "lm")
    cd = f"rests {tech['cooldown']} turn{'s' if tech['cooldown'] > 1 else ''}"
    t.text(d, (tx, y0 + 86), t.fit(d, f"{tech['power']}  ·  {tech['passive']}  ·  {cd}", f_b, x1 - tx - 14), f_b,
           t.ASH, "lm")
    # mastery
    t.diamonds(d, x0 + 20, y0 + 110, tech["stage"] + 1, 5, 4.5)
    if tech["cap"]:
        frac = tech["exp"] / tech["cap"]
        label = f"{tech['stage_name']}  ·  {tech['exp']:,} / {tech['cap']:,}"
    else:
        frac, label = 1, f"{tech['stage_name']}  ·  final stage"
    t.bar(img, (tx, y0 + 103, x1 - 14, y0 + 117), frac, t.GOLD if tech["trial_ready"] else t.EMBER,
          ("Trial ready (/spar)  ·  " if tech["trial_ready"] else "") + label)
