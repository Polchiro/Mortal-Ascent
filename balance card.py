"""
/balance card — same ink-wash scroll style as the profile card.
render_balance(data) returns a PIL Image.
"""
import math
import os
import random
from PIL import Image, ImageDraw

from profile_card import (S, W, PAPER, PAPER_DARK, INK, INK_SOFT, VERMILION, JADE, GOLD,
                          TALENT_COLORS, background, font, cjk, short, p, text, spaced,
                          brush_stroke, seal_square, ink_wash)

H_BAL = 500
MOON = (88, 104, 150)
MOON_LIGHT = (214, 220, 236)


def lotus_icon(d, cx, cy, size, color):
    """Lotus flower: almond-shaped petals fanned from one base point."""
    def petal(angle, length, width, fill):
        pts = []
        for i in range(21):
            t = i / 20
            pts.append((-width * math.sin(math.pi * t), -length * t))
        for i in range(20, -1, -1):
            t = i / 20
            pts.append((width * math.sin(math.pi * t), -length * t))
        a = math.radians(angle)
        rot = [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]
        d.polygon([p(x, y) for x, y in rot], fill=fill)

    light = tuple(min(255, c + 60) for c in color)
    for ang, ln in ((-68, 0.72), (68, 0.72)):
        petal(ang, size * ln, size * 0.2, light)
    for ang, ln in ((-38, 0.9), (38, 0.9)):
        petal(ang, size * ln, size * 0.24, light)
    petal(0, size * 1.05, size * 0.27, color)
    for ang in (-18, 18):
        petal(ang, size * 0.95, size * 0.22, color)
    d.ellipse(p(cx - size * 0.55, cy - size * 0.08, cx + size * 0.55, cy + size * 0.12), fill=color)


def moon_icon(d, cx, cy, r, bg):
    """Crescent moon with a small pearl."""
    d.ellipse(p(cx - r, cy - r, cx + r, cy + r), fill=MOON)
    d.ellipse(p(cx - r + r * 0.55, cy - r - r * 0.15, cx + r + r * 0.55, cy + r - r * 0.15), fill=bg)
    pr = r * 0.32
    px_, py_ = cx + r * 0.55, cy + r * 0.35
    d.ellipse(p(px_ - pr, py_ - pr, px_ + pr, py_ + pr), fill=MOON_LIGHT, outline=MOON, width=2 * S)


def currency_panel(d, x, y, w, h, label, value, exact, accent, draw_icon):
    d.rectangle(p(x, y, x + w, y + h), fill=PAPER_DARK + (210,))
    d.rectangle(p(x, y, x + 5, y + h), fill=accent)
    draw_icon(x + 62, y + h / 2)
    spaced(d, (x + 122, y + 26), label, font("Cinzel.ttf", 14, "Bold"), INK_SOFT, 1.6)
    text(d, (x + 122, y + 50), short(value), font("Inter.ttf", 42, "Bold"), accent)
    text(d, (x + 122, y + 104), exact, font("Inter.ttf", 14, "Medium"), INK_SOFT)


def render_balance(data):
    img = background(H_BAL)
    img = ink_wash(img, (110, 230), 120, random.Random(5))
    d = ImageDraw.Draw(img)

    # left: vertical calligraphy 钱囊 (money pouch)
    f_cal = cjk(54)
    for i, ch in enumerate("钱囊"):
        d.text(p(110, 140 + i * 72), ch, font=f_cal, fill=INK + (210,), anchor="mm")
    seal_square(img, "财", (78, 330), 60, VERMILION, rotate=-5)
    d = ImageDraw.Draw(img)

    for i in range(3):
        d.line(p(200 + i, 60, 200 + i, H_BAL - 60), fill=INK + (40 + i * 30,), width=1 * S)

    x0, wcol = 236, 926

    # title
    f_title = font("Cinzel.ttf", 40, "Black")
    title = f"{data['name'].upper()}'S PURSE"
    text(d, (x0, 50), title, f_title, INK)
    tw = d.textlength(title, font=f_title) / S
    brush_stroke(d, x0, x0 + tw + 8, 104, 7, VERMILION + (230,))
    sub = f"{data['realm']}  ·  {data['talent']} Talent"
    text(d, (x0, 118), sub, font("Inter.ttf", 15, "Medium"), INK_SOFT)

    # currency panels
    pw = (wcol - 20) / 2
    currency_panel(d, x0, 156, pw, 132, "LOTUS COINS", data["coins"], f"{data['coins']:,} coins",
                   GOLD, lambda cx, cy: lotus_icon(d, cx, cy + 22, 38, GOLD))
    currency_panel(d, x0 + pw + 20, 156, pw, 132, "MOON PEARLS", data["pearls"], f"{data['pearls']:,} pearls",
                   MOON, lambda cx, cy: moon_icon(d, cx, cy, 30, PAPER_DARK))

    # heavenly blessing
    y = 310
    b = data.get("blessing")
    d.rectangle(p(x0, y, x0 + wcol, y + 104), fill=PAPER_DARK + (150,), outline=INK_SOFT + (120,), width=1 * S)
    f_lab = font("Cinzel.ttf", 14, "Bold")
    if b:
        spaced(d, (x0 + 20, y + 16), "HEAVENLY BLESSING", f_lab, INK_SOFT, 1.6)
        text(d, (x0 + 20, y + 38), b["tier"], font("Cinzel.ttf", 26, "Bold"), JADE)
        text(d, (x0 + 20, y + 76), b["perks"], font("Inter.ttf", 13, "Medium"), INK_SOFT)
        # days-left bar
        bx, by, bw = x0 + wcol - 320, y + 56, 296
        text(d, (bx + bw, y + 18), f"{b['days_left']} of 30 days left", font("Inter.ttf", 14, "SemiBold"), INK, "ra")
        d.rounded_rectangle(p(bx, by, bx + bw, by + 12), radius=6 * S, fill=(214, 226, 216))
        d.rounded_rectangle(p(bx, by, bx + bw * b["days_left"] / 30, by + 12), radius=6 * S, fill=JADE)
    else:
        spaced(d, (x0 + 20, y + 22), "HEAVENLY BLESSING", f_lab, INK_SOFT, 1.6)
        text(d, (x0 + 20, y + 48), "No active blessing  ·  /blessing to view tiers",
             font("Inter.ttf", 17, "Medium"), INK_SOFT)

    # footer hint
    text(d, (x0 + wcol, H_BAL - 66), "/recharge  ·  Moon Pearl Pavilion", font("Inter.ttf", 13, "Medium"),
         VERMILION, "ra")

    return img.resize((W, H_BAL), Image.LANCZOS).convert("RGB")


SAMPLE = {
    "name": "Shoaib",
    "realm": "Martial King",
    "talent": "Genius",
    "coins": 128450,
    "pearls": 1240,
    "blessing": {"tier": "Bright Moon", "days_left": 12,
                 "perks": "+30% Qi Rate  ·  +10% Lotus Coins  ·  +5% Mastery EXP"},
}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    render_balance(SAMPLE).save(os.path.join(here, "balance_preview.png"))
    print("saved balance_preview.png")
