"""
/profession: the Alchemist and Blacksmith ranks side by side on the night sky.

  ┌ PROFESSIONS, the player's name
  ├ two glass panels (alchemy in ember orange, the forge in steel blue), each with:
  │   the painting (cauldron / finished blade), a rank seal 一品 … 九品, "3rd Grade Alchemist",
  │   nine rank pips, an EXP bar to the next rank, what you can make now, and what the next rank opens
  └ where the EXP comes from

render_profession(data) takes bot.profession.card_data(player).
"""
import os
from functools import lru_cache

from PIL import Image, ImageDraw

from . import theme as T
from .compendium import EDGE, SOFT, TEXT, _glass, _sky
from .theme import P, S, alpha, cjk, font, mix

W, H = T.W, 930
PAD = 28
GAP = 24
TOP = 132
COLOR = {"alchemy": ((255, 170, 90), (190, 80, 30)), "forge": ((150, 200, 255), (60, 110, 190))}


@lru_cache(maxsize=4)
def _art(name, height):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "scenes", name)
    if not os.path.exists(path):
        return None
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox() or (0, 0, *im.size))
    k = height * S / im.size[1]
    return im.resize((max(1, round(im.size[0] * k)), round(height * S)), Image.LANCZOS)


def render_profession(data):
    img = _sky(H)
    T.gold_text(img, (W / 2, 56), "PROFESSIONS", font("Cinzel.ttf", 54, "Black"), "mm", glow=alpha(T.GOLD, 100))
    d = ImageDraw.Draw(img)
    T.text(d, (W / 2, 104), data["name"], font("Inter.ttf", 27, "SemiBold"), SOFT, "mm")
    pw = (W - 2 * PAD - GAP) / 2
    for i, side in enumerate(data["sides"]):
        x = PAD + i * (pw + GAP)
        _panel(img, (x, TOP, x + pw, H - 30), side)
    ImageDraw.Draw(img).rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(EDGE, 220),
                                          width=round(2 * S))
    return T.finish(img)


def _panel(img, box, s):
    x0, y0, x1, y1 = box
    hi, lo = COLOR[s["key"]]
    cx = (x0 + x1) / 2
    T.soft_glow(img, (x0 + 40, y0 + 10, x1 - 40, y0 + 300), alpha(hi, 70), 40)
    _glass(img, box, edge=mix(hi, EDGE, 0.5), a=170, r=18, width=2)
    # painting and rank seal
    art = _art(s["art"], 210)
    if art is not None:
        img.alpha_composite(art, (round(cx * S - art.size[0] / 2), round((y0 + 20) * S)))
    sx, sy = x1 - 70, y0 + 70
    d = ImageDraw.Draw(img)
    d.ellipse(P(sx - 48, sy - 48, sx + 48, sy + 48), fill=alpha(mix(lo, (0, 0, 0), 0.45), 240), outline=hi,
              width=round(3 * S))
    d.ellipse(P(sx - 40, sy - 40, sx + 40, sy + 40), outline=alpha(hi, 140), width=max(1, S))
    T.text(d, (sx, sy - 2), s["seal"], cjk(32), mix(hi, (255, 255, 255), 0.5), "mm")
    # title and rank
    ty = y0 + 262
    T.text(d, (cx, ty), s["title"].upper(), font("Cinzel.ttf", 24, "Bold"), SOFT, "mm")
    T.gold_text(img, (cx, ty + 44), s["label"], font("Cinzel.ttf", 36, "Black"), "mm",
                top=mix(hi, (255, 255, 255), 0.5), bottom=lo, glow=alpha(hi, 90))
    # nine pips
    d = ImageDraw.Draw(img)
    n, gap = s["max_rank"], 34
    px0 = cx - gap * (n - 1) / 2
    for k in range(n):
        x, y, r = px0 + k * gap, ty + 96, 9
        if k < s["rank"]:
            d.ellipse(P(x - r, y - r, x + r, y + r), fill=hi, outline=mix(hi, (255, 255, 255), 0.5))
        else:
            d.ellipse(P(x - r, y - r, x + r, y + r), fill=(12, 16, 30), outline=alpha(EDGE, 160), width=max(1, S))
    # EXP bar
    by = ty + 146
    bx0, bx1 = x0 + 36, x1 - 36
    d.rounded_rectangle(P(bx0, by - 12, bx1, by + 12), radius=12 * S, fill=(8, 12, 24, 235), outline=alpha(EDGE, 150),
                        width=max(1, S))
    frac = 1.0 if not s["next"] else (s["into"] / s["span"] if s["span"] else 1.0)
    if frac > 0:
        d.rounded_rectangle(P(bx0 + 3, by - 9, bx0 + 3 + (bx1 - bx0 - 6) * min(1, frac), by + 9), radius=9 * S, fill=hi)
    f = font("Inter.ttf", 24, "SemiBold")
    if s["next"]:
        T.text(d, (bx0, by + 36), f"{s['exp']:,} EXP", f, TEXT, "lm")
        T.text(d, (bx1, by + 36), f"{s['to_next']:,} to {s['next']}", f, mix(hi, (255, 255, 255), 0.4), "rm")
    else:
        T.text(d, (cx, by + 36), f"{s['exp']:,} EXP · the highest grade", f, mix(hi, (255, 255, 255), 0.4), "mm")
    # can make now / next rank opens
    y = by + 96
    d.line(P(x0 + 30, y - 22, x1 - 30, y - 22), fill=alpha(EDGE, 90), width=max(1, S))
    hf, lf = font("Inter.ttf", 22, "Bold"), font("Inter.ttf", 24, "Medium")
    T.text(d, (x0 + 36, y), f"CAN {'CRAFT' if s['key'] == 'alchemy' else 'FORGE'}", hf, SOFT, "lm")
    text = _summary(s)
    for k, line in enumerate(T.wrap(d, text, lf, x1 - x0 - 72, lines=3)):
        T.text(d, (x0 + 36, y + 34 + k * 31), line, lf, TEXT, "lm")
    y += 116
    if s["upcoming"]:
        rank, items = s["upcoming"]
        T.text(d, (x0 + 36, y), f"AT {rank.upper()}", hf, mix(hi, (255, 255, 255), 0.3), "lm")
        nxt = ", ".join(items) + (" gear" if s["key"] == "forge" else "")
        for k, line in enumerate(T.wrap(d, nxt, lf, x1 - x0 - 72, lines=2)):
            T.text(d, (x0 + 36, y + 34 + k * 31), line, lf, mix(hi, (255, 255, 255), 0.55), "lm")
    T.text(d, (cx, y1 - 32), f"Raise it with {s['command']}", font("Inter.ttf", 23, "SemiBold"), SOFT, "mm")


def _summary(s):
    """'Mortal and Yellow: Qi, Mending, Qi Burst …' kept short: the grades and kinds open now."""
    if s["key"] == "forge":
        return ", ".join(s["can"]) + " gear"
    by_grade = {}
    for item in s["can"]:
        grade, kind = item.split(" ", 1)
        by_grade.setdefault(grade, []).append(kind)
    every = len(PILL_KINDS)
    parts = [f"{g}: all pills" if len(k) == every else f"{g}: {', '.join(k)}" for g, k in by_grade.items()]
    return " · ".join(parts)


PILL_KINDS = ("Qi", "Qi Burst", "Mending", "Cleansing", "Breakthrough")
