"""
/internal qi card · the dantian, in the Crimson Hall theme of the Character Sheet.

render_dantian(data) draws the dict built by bot/qi.py:qi_data: the dantian orb,
the Qi bar (banked Qi, plus Qi gathered but not yet banked), Qi Rate, time to a
full bar, the next gate, the cultivation status and every Qi Rate source with
the full formula.
"""
from PIL import ImageDraw

from . import theme as t
from .theme import P, font, short

H = 760
TONES = {"jade": t.JADE, "gold": t.GOLD_HI, "red": t.GLOW}


def fmt_qi(n):
    if n >= 10000:
        return short(n)
    return f"{n:,.0f}" if n >= 100 else f"{n:,.1f}".removesuffix(".0")


def render_dantian(data):
    img = t.canvas(t.W, H, seed=17)
    t.banner(img, (0, 0, t.W, 46))
    d = ImageDraw.Draw(img)
    t.spaced(d, (t.W / 2, 23), "INTERNAL QI  ·  DANTIAN", font("Cinzel.ttf", 15, "Bold"), t.GOLD_HI, 3, "m")
    t.frame(img, (6, 52, t.W - 6, H - 6))

    need = data["qi_needed"]
    frac = min(1.0, data["qi"] / need) if need else 1.0
    orb_panel(img, data, frac, (30, 70, 370, 440))
    header(img, data, (390, 70, 1170, 150))
    qi_bar(img, data, frac, (390, 156, 1170, 250))
    stat_boxes(img, data, (390, 284, 1170, 440))
    sources_panel(img, data, (30, 458, 1170, H - 24))
    return t.finish(img)


def orb_panel(img, data, frac, box):
    x0, y0, x1, y1 = box
    t.panel(img, box)
    cx = (x0 + x1) / 2
    t.orb(img, (cx, y0 + 150), 104, frac, f"{frac * 100:.1f}%".replace(".0%", "%"))
    d = ImageDraw.Draw(img)
    t.text(d, (cx, y0 + 288), "丹田", t.cjk(30), t.EMBER, "mm")
    color = TONES.get(data["status_tone"], t.JADE)
    f = font("Inter.ttf", 13, "Bold")
    status = t.fit(d, data["status"], f, x1 - x0 - 60)
    w = t.width(d, status, f) + 36
    d.rounded_rectangle(P(cx - w / 2, y0 + 318, cx + w / 2, y0 + 346), radius=round(14 * t.S),
                        fill=t.mix(color, (0, 0, 0), 0.78) + (255,), outline=color, width=max(1, t.S))
    d.ellipse(P(cx - w / 2 + 12, y0 + 328, cx - w / 2 + 20, y0 + 336), fill=color)
    t.text(d, (cx + 6, y0 + 332), status, f, t.mix(color, (255, 255, 255), 0.3), "mm")


def header(img, data, box):
    x0, y0, x1, y1 = box
    t.gold_text(img, (x0 + 4, y0 + 2), f"{data['name'].upper()}'S DANTIAN", font("Cinzel.ttf", 34, "Black"),
                glow=t.EMBER)
    d = ImageDraw.Draw(img)
    sub = f"{data['realm']}  ·  {data['phase']}  ·  {t.ordinal(data['layer'])} Layer"
    f = font("Inter.ttf", 15, "Medium")
    t.text(d, (x0 + 6, y0 + 62), sub, f, t.ASH, "lm")
    tx = x0 + 6 + t.width(d, sub, f) + 16
    color = t.TALENT.get(data["talent"], t.ASH)
    t.text(d, (tx, y0 + 62), f"{data['talent']} Talent", font("Inter.ttf", 15, "Bold"), color, "lm")


def qi_bar(img, data, frac, box):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0 + 4, y0 + 10), "INTERNAL QI", font("Cinzel.ttf", 13, "Bold"), t.GOLD, 2)
    f_big = font("Cinzel.ttf", 34, "Black")
    big = fmt_qi(data["qi"])
    t.text(d, (x0 + 4, y0 + 44), big, f_big, t.GOLD_HI, "lm")
    t.text(d, (x0 + 14 + t.width(d, big, f_big), y0 + 49), f"/ {fmt_qi(data['qi_needed'])} Qi",
           font("Inter.ttf", 18, "Medium"), t.ASH, "lm")
    t.text(d, (x1, y0 + 44), f"{frac * 100:.1f}%", font("Cinzel.ttf", 30, "Black"), t.GLOW, "rm")

    by0, by1 = y0 + 66, y0 + 84
    need = data["qi_needed"]
    pending = min(1.0 - frac, data["pending"] / need) if need else 0
    if pending > 0.002:
        px0 = x0 + (x1 - x0) * frac
        px1 = x0 + (x1 - x0) * (frac + pending)
        d.rectangle(P(px0, by0 + 1, px1, by1 - 1), fill=t.alpha(t.mix(t.EMBER, t.VOID, 0.55), 255))
    t.bar(img, (x0, by0, x1, by1), frac, t.EMBER)
    d = ImageDraw.Draw(img)
    if pending > 0.002:
        px0 = x0 + (x1 - x0) * frac
        px1 = x0 + (x1 - x0) * (frac + pending)
        x = px0 + 4
        while x < px1 - 2:
            d.line(P(x, by1 - 3, min(px1 - 2, x + 8), by0 + 3), fill=t.alpha(t.GLOW, 170), width=max(1, t.S))
            x += 9
    for q in (0.25, 0.5, 0.75):
        qx = x0 + (x1 - x0) * q
        d.line(P(qx, by1 + 3, qx, by1 + 8), fill=t.BRONZE, width=max(1, t.S))
    f = font("Inter.ttf", 13, "Medium")
    if data["pending"] >= 0.05:
        t.text(d, (x0, by1 + 18), f"+{fmt_qi(data['pending'])} Qi {data['pending_label']}", f, t.GLOW, "lm")
    t.text(d, (x1, by1 + 18), f"A perfect /train gives about {fmt_qi(data['train_qi'])} Qi", f, t.ASH, "rm")


def stat_boxes(img, data, box):
    x0, y0, x1, y1 = box
    gap = 14
    w = (x1 - x0 - 2 * gap) / 3
    boxes = [
        ("flame", "Qi Rate", f"{fmt_qi(data['rate'])} / hour", f"×{data['mult']:.2f} total", t.GLOW),
        ("hourglass", "Full bar in", data["eta"], "at your current Qi Rate", t.GOLD_HI),
        ("star", "Next gate", data["gate"], data["gate_note"], t.LOTUS),
    ]
    for i, (ic, label, value, sub, color) in enumerate(boxes):
        bx = x0 + i * (w + gap)
        t.panel(img, (bx, y0, bx + w, y1))
        t.medallion(img, (bx + 40, y0 + 46), 22, ic, color, cjk_char=False)
        d = ImageDraw.Draw(img)
        t.spaced(d, (bx + 74, y0 + 46), label.upper(), font("Cinzel.ttf", 13, "Bold"), t.GOLD, 1.6)
        f_v = font("Inter.ttf", 26, "Bold")
        t.text(d, (bx + 20, y0 + 96), t.fit(d, value, f_v, w - 40), f_v, color, "lm")
        f_s = font("Inter.ttf", 13, "Medium")
        t.text(d, (bx + 20, y0 + 128), t.fit(d, sub, f_s, w - 40), f_s, t.ASH, "lm")


def sources_panel(img, data, box):
    x0, y0, x1, y1 = box
    t.panel(img, box)
    d = ImageDraw.Draw(img)
    f_f = font("Inter.ttf", 13, "SemiBold")
    formula = t.fit(d, data["formula"], f_f, 560)
    t.text(d, (x1 - 20, y0 + 22), formula, f_f, t.PARCHMENT, "rm")
    t.heading(img, (x0 + 18, y0 + 22), "Sources of Qi", x1 - 40 - t.width(d, formula, f_f))
    d = ImageDraw.Draw(img)
    rows = data["sources"]
    half = (len(rows) + 1) // 2
    col_w = (x1 - x0 - 60) / 2
    step = (y1 - y0 - 64) / max(1, half)
    for i, r in enumerate(rows):
        c, k = divmod(i, half)
        x = x0 + 20 + c * (col_w + 20)
        y = y0 + 64 + k * step + step / 2 - 6
        warn = r.get("warn")
        color = t.GLOW if warn else (t.EMBER if r["active"] else t.ASH_DK)
        t.medallion(img, (x + 20, y), 18, r["seal"], color)
        d = ImageDraw.Draw(img)
        name_c = t.PARCHMENT if r["active"] else t.ASH
        t.text(d, (x + 50, y - 9), r["label"], font("Inter.ttf", 15, "Bold"), name_c, "lm")
        t.text(d, (x + 50, y + 11), t.fit(d, r["detail"], font("Inter.ttf", 12, "Medium"), col_w - 170),
               font("Inter.ttf", 12, "Medium"), t.ASH if r["active"] else t.ASH_DK, "lm")
        val_c = t.GLOW if warn else (t.GOLD_HI if r["active"] else t.ASH_DK)
        t.text(d, (x + col_w - 6, y), r["value"], font("Inter.ttf", 18, "Bold"), val_c, "rm")
    mid = x0 + 20 + col_w + 10
    d.line(P(mid, y0 + 56, mid, y1 - 16), fill=t.BRONZE_DK, width=max(1, t.S))
