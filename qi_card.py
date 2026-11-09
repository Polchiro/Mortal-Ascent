"""
/qi card: the player's dantian. Same ink-wash scroll style as the profile and balance cards.
render_qi(data) returns a PIL Image. The data dict is built by bot/qi.py:qi_data.
"""
import os
import random
from PIL import Image, ImageDraw

from profile_card import (S, W, PAPER, PAPER_DARK, INK, INK_SOFT, VERMILION, JADE, JADE_LIGHT, GOLD,
                          TALENT_COLORS, background, font, cjk, short, ordinal, p, text, spaced,
                          brush_stroke, seal_square, ink_wash)

H_QI = 712
FADED = (168, 158, 144)
TONES = {"jade": JADE, "gold": GOLD, "red": VERMILION}


def tint(color, amount=0.85):
    """Mix a colour toward the paper (the card is flattened to RGB, so no alpha blending)."""
    return tuple(round(c + (pc - c) * amount) for c, pc in zip(color, PAPER))


def fmt_qi(n):
    if n >= 10000:
        return short(n)
    return f"{n:,.0f}" if n >= 100 else f"{n:,.1f}".removesuffix(".0")


def fit(d, s, f, width):
    """Cut s with an ellipsis so it fits in `width` (card pixels)."""
    if d.textlength(s, font=f) / S <= width:
        return s
    while s and d.textlength(s + "…", font=f) / S > width:
        s = s[:-1]
    return s.rstrip(" ·,") + "…"


def qi_bar(img, x, y, w, h, qi, need, pending):
    """Ink-outlined meridian bar: banked Qi in jade, gathered-but-uncollected Qi hatched after it."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(p(x, y, x + w, y + h), radius=h / 2 * S, fill=PAPER_DARK + (255,),
                        outline=INK + (200,), width=2 * S)
    filled = w * min(1.0, qi / need) if need else w
    extra = w * min(1.0 - filled / w, pending / need) if need else 0
    if extra > 1:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle(p(x + 2, y + 2, x + filled + extra - 2, y + h - 2), radius=(h / 2 - 2) * S,
                             fill=JADE_LIGHT + (255,))
        for hx in range(int(x + filled), int(x + filled + extra) + h, 9):
            ld.line(p(hx, y + h, hx + h * 0.8, y), fill=JADE + (120,), width=2 * S)
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(p(x + 2, y + 2, x + filled + extra - 2, y + h - 2),
                                               radius=(h / 2 - 2) * S, fill=255)
        img.alpha_composite(Image.composite(layer, Image.new("RGBA", img.size, (0, 0, 0, 0)), mask))
        d = ImageDraw.Draw(img)
    if filled > 2:
        d.rounded_rectangle(p(x + 2, y + 2, x + max(h - 4, filled - 2), y + h - 2), radius=(h / 2 - 2) * S, fill=JADE)
        # brushed highlight along the top of the fill
        d.line(p(x + h / 2, y + 6, x + max(h / 2, filled - h / 2), y + 6), fill=(255, 255, 255, 70), width=2 * S)
    # quarter ticks, like marks on a measuring rod
    for q in (0.25, 0.5, 0.75):
        tx = x + w * q
        d.line(p(tx, y + h + 3, tx, y + h + 9), fill=INK_SOFT + (180,), width=1 * S)


def tile(d, x, y, w, h, label, value, note, accent):
    d.rectangle(p(x, y, x + w, y + h), fill=PAPER_DARK + (215,))
    d.line(p(x, y + h, x + w, y + h), fill=accent, width=3 * S)
    spaced(d, (x + 18, y + 14), label, font("Cinzel.ttf", 13, "Bold"), INK_SOFT, 1.6)
    f_val = font("Inter.ttf", 26, "Bold")
    text(d, (x + 18, y + 34), fit(d, value, f_val, w - 36), f_val, accent)
    f_note = font("Inter.ttf", 13, "Medium")
    text(d, (x + 18, y + 68), fit(d, note, f_note, w - 36), f_note, INK_SOFT)


def source_row(img, x, y, w, row):
    active, warn = row["active"], row.get("warn")
    color = VERMILION if warn else (JADE if active else FADED)
    seal_square(img, row["seal"], (x, y + 4), 30, color)
    d = ImageDraw.Draw(img)
    f_val = font("Inter.ttf", 18, "Bold")
    text(d, (x + w, y + 10), row["value"], f_val, color if (active or warn) else FADED, "ra")
    room = w - 44 - d.textlength(row["value"], font=f_val) / S - 12
    f_lab = font("Inter.ttf", 15, "SemiBold")
    text(d, (x + 44, y + 2), fit(d, row["label"], f_lab, room), f_lab, INK if active else INK_SOFT)
    f_det = font("Inter.ttf", 12, "Medium")
    text(d, (x + 44, y + 22), fit(d, row["detail"], f_det, room), f_det, INK_SOFT if active else FADED)


def render_qi(data):
    img = background(H_QI)
    img = ink_wash(img, (110, 250), 130, random.Random(11))
    d = ImageDraw.Draw(img)

    # left: vertical calligraphy 丹田 (dantian) and a 气 seal
    f_cal = cjk(54)
    for i, ch in enumerate("丹田"):
        d.text(p(110, 150 + i * 72), ch, font=f_cal, fill=INK + (210,), anchor="mm")
    seal_square(img, "气", (78, 340), 60, VERMILION, rotate=4)
    d = ImageDraw.Draw(img)
    for i in range(3):
        d.line(p(200 + i, 60, 200 + i, H_QI - 60), fill=INK + (40 + i * 30,), width=1 * S)

    x0, wcol = 236, 926

    # title
    f_title = font("Cinzel.ttf", 40, "Black")
    title = f"{data['name'].upper()}'S DANTIAN"
    title = fit(d, title, f_title, 690)
    text(d, (x0, 50), title, f_title, INK)
    tw = d.textlength(title, font=f_title) / S
    brush_stroke(d, x0, x0 + tw + 8, 104, 7, JADE + (220,))
    f_sub = font("Inter.ttf", 15, "Medium")
    sub = f"{data['realm']}  ·  {data['phase']}  ·  {ordinal(data['layer'])} Layer  ·  "
    text(d, (x0, 118), sub, f_sub, INK_SOFT)
    text(d, (x0 + d.textlength(sub, font=f_sub) / S, 118), f"{data['talent']} Talent",
         font("Inter.ttf", 15, "SemiBold"), TALENT_COLORS.get(data["talent"], INK))

    # internal Qi: label + status tag, numbers, bar
    y = 160
    spaced(d, (x0, y), "INTERNAL QI", font("Cinzel.ttf", 14, "Bold"), INK_SOFT, 1.8)
    tone = TONES[data["status_tone"]]
    f_tag = font("Inter.ttf", 13, "SemiBold")
    tag = data["status"]
    tag_w = d.textlength(tag, font=f_tag) / S + 38
    tx = x0 + wcol - tag_w
    d.rounded_rectangle(p(tx, y - 5, x0 + wcol, y + 21), radius=13 * S, fill=tint(tone), outline=tone, width=1 * S)
    d.ellipse(p(tx + 12, y + 3, tx + 22, y + 13), fill=tone)
    text(d, (tx + 28, y + 8), tag, f_tag, tone, "lm")

    pct = data["qi"] / data["qi_needed"] if data["qi_needed"] else 1.0
    f_big = font("Inter.ttf", 44, "Bold")
    qi_s = fmt_qi(data["qi"])
    text(d, (x0, 186), qi_s, f_big, INK)
    text(d, (x0 + d.textlength(qi_s, font=f_big) / S + 10, 206), f"/ {fmt_qi(data['qi_needed'])} Qi",
         font("Inter.ttf", 22, "Medium"), INK_SOFT)
    text(d, (x0 + wcol, 186), f"{pct * 100:.1f}%", font("Cinzel.ttf", 40, "Bold"), VERMILION, "ra")

    qi_bar(img, x0, 246, wcol, 22, data["qi"], data["qi_needed"], data["pending"])
    d = ImageDraw.Draw(img)
    f_small = font("Inter.ttf", 13, "Medium")
    if data["pending"] >= 0.05:
        text(d, (x0, 284), f"+{fmt_qi(data['pending'])} Qi {data['pending_label']}", f_small, JADE)
    text(d, (x0 + wcol, 284), f"A perfect /train gives about {fmt_qi(data['train_qi'])} Qi",
         f_small, INK_SOFT, "ra")

    # three tiles
    y, th, gap = 314, 92, 20
    tw3 = (wcol - 2 * gap) / 3
    rate_note = f"×{data['mult']:.2f} total"
    tile(d, x0, y, tw3, th, "QI RATE", f"{fmt_qi(data['rate'])} / hour", rate_note, JADE)
    tile(d, x0 + tw3 + gap, y, tw3, th, "FULL BAR IN", data["eta"], "at your current Qi Rate", GOLD)
    tile(d, x0 + 2 * (tw3 + gap), y, tw3, th, "NEXT GATE", data["gate"], data["gate_note"], VERMILION)

    # sources ledger
    y = 432
    rows = data["sources"]
    per_col = (len(rows) + 1) // 2
    ph = 50 + per_col * 46
    d.rectangle(p(x0, y, x0 + wcol, y + ph), fill=PAPER + (225,), outline=INK_SOFT + (120,), width=1 * S)
    spaced(d, (x0 + 20, y + 16), "SOURCES OF QI", font("Cinzel.ttf", 14, "Bold"), INK_SOFT, 1.8)
    f_form = font("Inter.ttf", 13, "Medium")
    text(d, (x0 + wcol - 20, y + 17), fit(d, data["formula"], f_form, wcol - 260), f_form, INK, "ra")
    cw = (wcol - 40 - 40) / 2
    for i, row in enumerate(rows):
        col, r = divmod(i, per_col)
        cx = x0 + 20 + col * (cw + 40)
        source_row(img, cx, y + 46 + r * 46, cw, row)
    d = ImageDraw.Draw(img)
    d.line(p(x0 + 20 + cw + 20, y + 50, x0 + 20 + cw + 20, y + ph - 12), fill=INK_SOFT + (90,), width=1 * S)

    return img.resize((W, H_QI), Image.LANCZOS).convert("RGB")


def _row(seal, label, detail, value, active, warn=False):
    return {"seal": seal, "label": label, "detail": detail, "value": value, "active": active, "warn": warn}


SAMPLE = {
    "name": "Shoaib", "realm": "Martial King", "phase": "Late Phase", "layer": 8, "talent": "Genius",
    "qi": 38210.4, "qi_needed": 53760, "pending": 4120.0, "pending_label": "gathered, not yet banked",
    "rate": 913.92, "mult": 2.86, "eta": "12h 30m",
    "gate": "9th Layer", "gate_note": "opens on its own",
    "status": "Gathering on its own", "status_tone": "jade", "train_qi": 3655.7,
    "sources": [
        _row("根", "Realm base", "Martial King", "320 Qi/h", True),
        _row("才", "Talent", "Genius", "+20%", True),
        _row("功", "Technique", "Flowing Cloud Palm · Pure Flame", "+18%", True),
        _row("福", "Heavenly Blessing", "Bright Moon · 12d left", "+30%", True),
        _row("丹", "Qi Pill", "Mystic · 2h 14m left", "×1.70", True),
        _row("地", "Blessed Land", "None · found in /explore", "×1", False),
        _row("毒", "Pill toxicity", "4 · Next pill at 50% strength", "50%", True, True),
    ],
    "formula": "320 × (1 + 0.2 + 0.18 + 0.3) × 1.70 = 913.92 Qi/h",
}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    render_qi(SAMPLE).save(os.path.join(here, "qi_preview.png"))
    print("saved qi_preview.png")
